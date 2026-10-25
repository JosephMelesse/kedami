"""Agent mode's draft lesson: what Claude Code submits through the MCP server, one step at a time.
See architecture/agent-mode.md, Building a lesson.

The draft lives in work/{lesson_id}/ under the pipeline's file names, and the checks are the
pipeline's. Each step needs the one before it, and saving a step again deletes the outputs of
the steps after it. The draft is never served: the lesson JSON is written only by `finish`.
Nothing here calls a model.
"""

import threading
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from pydantic import ValidationError

from .. import db, library
from ..generation import pipeline
from ..generation.assemble import SectionError, assemble_lesson, assemble_section
from ..generation.hints import leak_reason, targets, with_hints
from ..generation.ingest import Normalized, RoutedPage, join_pages
from ..generation.plan import PlanError, SectionPlan, place_problems
from ..generation.schemas import Extraction, Plan, ProblemsAndConcepts, SectionDraft, Solutions
from ..generation.sql import refuse_queries
from ..generation.verify import Result, agrees, answer_format, verifiable, with_verified
from ..lesson import MAX_HINTS, CheckpointBlock, ProblemBlock, Section
from ..library import LessonRow

# The subjects Claude Code can build. Computer science lessons depend on server-side lookups.
SUBJECTS = ("math", "physics", "general")
CANCELED = "Canceled."
PAGE_REASON = "Read by Claude Code"


class NotFound(LookupError):
    pass


class OutOfOrder(Exception):
    """The lesson isn't in a state for this step: not started, a step before it missing, or already over."""


class Rejected(ValueError):
    """What was submitted breaks a rule; the message says every reason."""


# Tool calls arrive one at a time, but subagents may work on one lesson at once, so each lesson's
# read-modify-write of its draft files is serialized.
_locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)


def waiting(data_dir: Path) -> list[dict]:
    with db.connect(data_dir) as conn:
        rows = library.waiting_for_agent(conn)
        return [
            {
                "id": row.id,
                "subject": row.subject,
                "created": row.created,
                "files": [m.filename for m in library.list_materials(conn, row.id)],
            }
            for row in rows
        ]


def start(data_dir: Path, lesson_id: str) -> dict:
    """Claim a waiting lesson, or resume one already started."""
    with _locks[lesson_id]:
        row = _building(data_dir, lesson_id, started=False)
        with db.connect(data_dir) as conn:
            if row.current_stage is None:
                library.set_stage(conn, lesson_id, 1)
            materials = library.list_materials(conn, lesson_id)
        folder = pipeline.materials_dir(data_dir, lesson_id)
        return {
            "id": lesson_id,
            "subject": row.subject,
            "materials": [{"filename": m.filename, "role": m.role, "path": str(folder / m.filename)} for m in materials],
            "done": _done(data_dir, lesson_id),
        }


def save_pages(data_dir: Path, lesson_id: str, files: list[tuple[str, list[str]]]) -> dict:
    """Stage 1: the normalized Markdown of each uploaded file, page by page."""
    with _locks[lesson_id]:
        _building(data_dir, lesson_id)
        with db.connect(data_dir) as conn:
            materials = {m.filename: m for m in library.list_materials(conn, lesson_id)}
        names = [name for name, _ in files]
        problems = []
        repeated = sorted({n for n in names if names.count(n) > 1})
        if repeated:
            problems.append(f"each file is given once; given more than once: {', '.join(repeated)}")
        unknown = sorted(set(names) - materials.keys())
        if unknown:
            problems.append(f"these aren't the lesson's files: {', '.join(unknown)}")
        missing = [n for n in materials if n not in names]
        if missing:
            problems.append(f"these files have no pages: {', '.join(missing)}")
        if problems:
            raise Rejected("; ".join(problems))

        pages = [
            RoutedPage(name, materials[name].role, number, "agent", PAGE_REASON, markdown)
            for name, texts in files
            for number, markdown in enumerate(texts, start=1)
        ]
        normalized = Normalized(join_pages(pages, "problem_set"), join_pages(pages, "reference"))
        if not normalized.problem_set.strip():
            raise Rejected("No text was given for the problem set.")

        work = _work(data_dir, lesson_id)
        pipeline.clear_from(work, 1)
        (work / pipeline.NORMALIZED).mkdir()
        (work / pipeline.NORMALIZED / pipeline.PROBLEM_SET_FILE).write_text(normalized.problem_set)
        (work / pipeline.NORMALIZED / pipeline.REFERENCE_FILE).write_text(normalized.reference)
        pipeline.write_json(work / "pages.json", [asdict(p) for p in pages])
        _set_stage(data_dir, lesson_id, 2)
        return {"pages": len(pages)}


def save_extraction(data_dir: Path, lesson_id: str, draft: ProblemsAndConcepts) -> dict:
    """Stage 2: problems, parts, options, concepts, and which problems need which concepts."""
    with _locks[lesson_id]:
        _building(data_dir, lesson_id)
        work = _work(data_dir, lesson_id)
        if not (work / pipeline.NORMALIZED / pipeline.PROBLEM_SET_FILE).exists():
            raise OutOfOrder("Save the pages first.")
        try:
            extraction = Extraction.model_validate(draft.model_dump())
        except ValidationError as error:
            raise Rejected(str(error)) from error
        pipeline.clear_from(work, 2)
        pipeline.write_output(work / "extraction.json", extraction)
        _set_stage(data_dir, lesson_id, 3)
        return {"problems": len(extraction.problems), "concepts": len(extraction.concepts)}


def save_plan(data_dir: Path, lesson_id: str, plan: Plan) -> dict:
    """Stage 3: the section order and each section's concepts. The server places the problems."""
    with _locks[lesson_id]:
        _building(data_dir, lesson_id)
        work = _work(data_dir, lesson_id)
        extraction = pipeline.load_output(work / "extraction.json", Extraction)
        if extraction is None:
            raise OutOfOrder("Save the extraction first.")
        try:
            outline = place_problems(plan, extraction)
        except PlanError as error:
            raise Rejected(str(error)) from error
        pipeline.clear_from(work, 3)
        pipeline.write_output(work / "plan.json", plan)
        pipeline.write_json(work / "outline.json", pipeline.outline_json(plan, outline))
        with db.connect(data_dir) as conn:
            library.set_title(conn, lesson_id, plan.title)
        _set_stage(data_dir, lesson_id, 4)
        return {"title": plan.title, "sections": [_describe(n, s) for n, s in enumerate(outline, start=1)]}


def save_section(data_dir: Path, lesson_id: str, number: int, draft: SectionDraft) -> dict:
    """Stage 4, one section. A section saved again replaces the old one and clears its verification."""
    with _locks[lesson_id]:
        _building(data_dir, lesson_id)
        work = _work(data_dir, lesson_id)
        section_plan, extraction = _section_plan(work, number)
        try:
            section = assemble_section(section_plan, draft, extraction.answers)
            refuse_queries(section)
        except (SectionError, ValidationError) as error:
            raise Rejected(str(error)) from error
        (work / f"verification-{number}.json").unlink(missing_ok=True)
        pipeline.write_output(work / f"section-{number}.json", section)
        return {
            "section": number,
            "id": section.id,
            "targets": [{"key": t.key, "question": t.question} for t in targets(section)],
        }


def save_hints(data_dir: Path, lesson_id: str, number: int, items: list[tuple[str, list[str]]]) -> dict:
    """Hints for some of a section's targets, replacing theirs. The first MAX_HINTS are kept, less any
    that contain the answer. The judge's check is the agent's to run before saving."""
    with _locks[lesson_id]:
        _building(data_dir, lesson_id)
        work = _work(data_dir, lesson_id)
        section = _section(work, number)
        by_key = {t.key: t for t in targets(section)}
        unknown = sorted({key for key, _ in items} - by_key.keys())
        if unknown:
            raise Rejected(f"these aren't targets in section {number}: {', '.join(unknown)}")
        hints = _hints(section)
        dropped = []
        for key, given in items:
            kept = []
            for hint in given[:MAX_HINTS]:
                reason = leak_reason(by_key[key].answer, hint)
                if reason:
                    dropped.append({"target": key, "hint": hint, "reason": reason})
                else:
                    kept.append(hint)
            hints[key] = kept
        pipeline.write_output(work / f"section-{number}.json", with_hints(section, hints))
        return {"dropped": dropped}


def questions(data_dir: Path, lesson_id: str, number: int) -> dict:
    """What the verifier may see: each question and the form of its answer, never the answer."""
    with _locks[lesson_id]:
        _building(data_dir, lesson_id)
        section = _section(_work(data_dir, lesson_id), number)
        return {
            "questions": [
                {"target": t.key, "question": t.question, "answer": answer_format(t.answer)} for t in verifiable(section)
            ]
        }


def save_verification(data_dir: Path, lesson_id: str, number: int, solutions: Solutions) -> dict:
    """The second solve's answers. The server compares them and sets `verified`; a target with no
    solution stays unverified."""
    with _locks[lesson_id]:
        _building(data_dir, lesson_id)
        work = _work(data_dir, lesson_id)
        section = _section(work, number)
        items = verifiable(section)
        given = [s.target for s in solutions.solutions]
        unknown = sorted(set(given) - {t.key for t in items})
        repeated = sorted({g for g in given if given.count(g) > 1})
        if unknown or repeated:
            problems = []
            if unknown:
                problems.append(f"these aren't questions in section {number}: {', '.join(unknown)}")
            if repeated:
                problems.append(f"each question is solved once; solved more than once: {', '.join(repeated)}")
            raise Rejected("; ".join(problems))
        solved = {s.target: s for s in solutions.solutions}
        results = [
            Result(
                target=t.key,
                stored=t.answer.model_dump(),
                solution=solved[t.key].model_dump() if t.key in solved else None,
                verified=t.key in solved and agrees(t.answer, solved[t.key]),
            )
            for t in items
        ]
        verified = [r.target for r in results if r.verified]
        pipeline.write_output(work / f"section-{number}.json", with_verified(section, set(verified)))
        pipeline.write_json(work / f"verification-{number}.json", [asdict(r) for r in results])
        return {"verified": verified, "unverified": [r.target for r in results if not r.verified]}


def finish(data_dir: Path, lesson_id: str) -> dict:
    """Write the lesson JSON and mark the lesson ready. Every section must be saved; verification isn't needed."""
    with _locks[lesson_id]:
        row = _building(data_dir, lesson_id)
        work = _work(data_dir, lesson_id)
        plan, outline, _ = _outline(work)
        sections = [pipeline.load_output(work / f"section-{n}.json", Section) for n in range(1, len(outline) + 1)]
        missing = [str(n) for n, s in enumerate(sections, start=1) if s is None]
        if missing:
            raise OutOfOrder(f"These sections aren't saved yet: {', '.join(missing)}")
        with db.connect(data_dir) as conn:
            filenames = [m.filename for m in library.list_materials(conn, lesson_id)]
        lesson = assemble_lesson(lesson_id, plan.title, row.subject, filenames, sections)
        target = pipeline.lesson_path(data_dir, lesson_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        pipeline.write_output(target, lesson)
        with db.connect(data_dir) as conn:
            library.set_ready(conn, lesson_id)
        return {"id": lesson_id, "title": lesson.title}


def fail(data_dir: Path, lesson_id: str, reason: str) -> dict:
    with _locks[lesson_id]:
        _building(data_dir, lesson_id, started=False)
        with db.connect(data_dir) as conn:
            library.set_failed(conn, lesson_id, reason)
        return {"id": lesson_id, "error": reason}


def cancel(data_dir: Path, lesson_id: str) -> dict:
    """The Generating screen's Cancel button."""
    return fail(data_dir, lesson_id, CANCELED)


def _building(data_dir: Path, lesson_id: str, started: bool = True) -> LessonRow:
    """The row of an agent lesson still being built, and started unless `started` is False."""
    with db.connect(data_dir) as conn:
        row = library.get_lesson_row(conn, lesson_id)
    if row is None:
        raise NotFound("lesson not found")
    if row.builder != "agent":
        raise OutOfOrder("This lesson is built by the pipeline, not Claude Code.")
    if row.status != "generating":
        raise OutOfOrder(f"This lesson is {row.status}; its build is over.")
    if started and row.current_stage is None:
        raise OutOfOrder("Start the lesson first.")
    return row


def _work(data_dir: Path, lesson_id: str) -> Path:
    work = pipeline.work_dir(data_dir, lesson_id)
    work.mkdir(parents=True, exist_ok=True)
    return work


def _set_stage(data_dir: Path, lesson_id: str, stage: int) -> None:
    with db.connect(data_dir) as conn:
        library.set_stage(conn, lesson_id, stage)


def _outline(work: Path) -> tuple[Plan, list[SectionPlan], Extraction]:
    plan = pipeline.load_output(work / "plan.json", Plan)
    extraction = pipeline.load_output(work / "extraction.json", Extraction)
    if plan is None or extraction is None:
        raise OutOfOrder("Save the plan first.")
    return plan, place_problems(plan, extraction), extraction


def _section_plan(work: Path, number: int) -> tuple[SectionPlan, Extraction]:
    _, outline, extraction = _outline(work)
    if not 1 <= number <= len(outline):
        raise NotFound(f"The plan has sections 1 to {len(outline)}; there is no section {number}.")
    return outline[number - 1], extraction


def _section(work: Path, number: int) -> Section:
    _section_plan(work, number)
    section = pipeline.load_output(work / f"section-{number}.json", Section)
    if section is None:
        raise OutOfOrder(f"Save section {number} first.")
    return section


def _hints(section: Section) -> dict[str, list[str]]:
    hints = {}
    for block in section.blocks:
        if isinstance(block, CheckpointBlock):
            hints[block.id] = list(block.hints)
        elif isinstance(block, ProblemBlock):
            for part in block.parts:
                hints[f"{block.id}/{part.id}"] = list(part.hints)
    return hints


def _done(data_dir: Path, lesson_id: str) -> dict:
    """Which steps a resumed session can skip."""
    work = pipeline.work_dir(data_dir, lesson_id)
    numbers = lambda prefix: sorted(int(p.stem.removeprefix(prefix)) for p in work.glob(f"{prefix}*.json"))  # noqa: E731
    return {
        "pages": (work / pipeline.NORMALIZED / pipeline.PROBLEM_SET_FILE).exists(),
        "extraction": (work / "extraction.json").exists(),
        "plan": (work / "plan.json").exists(),
        "sections": numbers("section-"),
        "verified": numbers("verification-"),
    }


def _describe(number: int, section: SectionPlan) -> dict:
    return {
        "number": number,
        "id": section.id,
        "title": section.title,
        "goal": section.goal,
        "concepts": [c.model_dump() for c in section.concepts],
        "problems": [p.model_dump() for p in section.problems],
        "simulation": section.simulation,
    }
