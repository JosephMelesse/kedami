"""Stages 1 to 4: from uploaded files to a lesson. See architecture/pipeline.md.

Each stage writes its output under work/{lesson_id}/, so a rerun can start at any stage
whose inputs are on disk. A stage whose reply is rejected (a schema or rule violation)
is retried with the reason; a failed section is retried alone.
"""

import json
import logging
import shutil
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import asdict
from datetime import UTC, datetime
from itertools import count
from pathlib import Path

from pydantic import BaseModel, ValidationError

from .. import databases, db, library, progress, run_log, simulation_state, solution_state, test_flags, usage
from ..lesson import QueryAnswer, Section
from ..model import ModelError, call_model
from ..practice import choose, load_bank
from ..sql_chapters import BOOK_CREDIT
from ..storage import lessons_dir
from ..usage_table import RunTable
from . import prompts
from .assemble import assemble_lesson, assemble_section
from .hints import add_hints
from .ingest import Material, Normalized, ingest
from .plan import SectionPlan, place_problems
from .recommended import RecommendedProblem, bank_databases, parse_recommended
from .recommended import build_extraction as build_recommended
from .retry import ATTEMPTS, GenerationError, retrying
from .leetcode import ProblemListError, build_extraction, find_in_dataset, parse_problem_list
from .schemas import ConceptMap, Extraction, Plan, ProblemsAndConcepts, SectionDraft
from .sql import add_practice, refuse_queries, settle_queries
from .verify import verify_section

log = logging.getLogger(__name__)

STAGES = (1, 2, 3, 4)
STAGE_NAMES = {1: "ingest", 2: "extract", 3: "plan", 4: "generate"}
NORMALIZED = "normalized"
PROBLEM_SET_FILE = "problem-set.md"
REFERENCE_FILE = "reference.md"

Call = Callable[..., BaseModel]


def materials_dir(data_dir: Path, lesson_id: str) -> Path:
    return data_dir / "materials" / lesson_id


def work_dir(data_dir: Path, lesson_id: str) -> Path:
    return data_dir / "work" / lesson_id


def normalized_materials(data_dir: Path, lesson_id: str, subject: str) -> list[dict]:
    """The cached opening of model requests for a lesson, or nothing if stage 1 output is missing."""
    folder = work_dir(data_dir, lesson_id) / NORMALIZED
    if not (folder / PROBLEM_SET_FILE).exists():
        return []
    reference = folder / REFERENCE_FILE
    return prompts.materials(
        subject, (folder / PROBLEM_SET_FILE).read_text(), reference.read_text() if reference.exists() else ""
    )


def lesson_path(data_dir: Path, lesson_id: str) -> Path:
    return lessons_dir(data_dir) / f"{lesson_id}.json"


def start(data_dir: Path, lesson_id: str, subject: str, start_stage: int = 1) -> threading.Thread:
    thread = threading.Thread(
        target=run, args=(data_dir, lesson_id, subject, start_stage), daemon=True, name=f"lesson-{lesson_id}"
    )
    thread.start()
    return thread


def available_stages(data_dir: Path, lesson_id: str, has_materials: bool) -> list[int]:
    """Stages a rerun can start from. Stage 1 needs the uploaded files; stage k needs the
    saved outputs of stages 1 to k-1."""
    work = work_dir(data_dir, lesson_id)
    outputs = [
        (work / NORMALIZED / PROBLEM_SET_FILE).exists(),
        load_output(work / "extraction.json", Extraction) is not None,
        load_output(work / "plan.json", Plan) is not None,
    ]
    return [stage for stage in STAGES if (has_materials if stage == 1 else all(outputs[: stage - 1]))]


def run(data_dir: Path, lesson_id: str, subject: str, start_stage: int = 1, call: Call = call_model) -> None:
    """Generate the lesson and record the outcome in the index. Never raises.

    If a previous version of the lesson exists, a failure leaves it in place.
    Model calls made by the run go to the lesson's usage log, and the server's terminal
    shows a table of what the run has taken so far. When it ends, the run is added to the run log.
    """
    had_lesson = lesson_path(data_dir, lesson_id).exists()
    started, began = datetime.now(UTC).isoformat(), time.monotonic()
    error: str | None = None

    def fail(message: str) -> None:
        nonlocal error
        error = message
        if had_lesson:
            _record(data_dir, lambda conn: library.set_rerun_failed(conn, lesson_id, message))
        else:
            _record(data_dir, lambda conn: library.set_failed(conn, lesson_id, message))

    table = RunTable()
    with usage.recording(data_dir, lesson_id, STAGE_NAMES[start_stage], on_call=table.update) as recorded:
        table.start()
        try:
            _generate(data_dir, lesson_id, subject, start_stage, call, rerun=had_lesson)
        except (GenerationError, ModelError) as failure:
            fail(str(failure))
        except Exception as failure:
            log.exception("lesson %s failed", lesson_id)
            fail(f"Unexpected error: {failure}")
    wall = time.monotonic() - began
    table.finish(f"lesson {'ready' if error is None else 'failed'} in {usage.duration(wall)}", recorded.stages)
    run_log.write(
        data_dir,
        lesson_id,
        subject,
        work=work_dir(data_dir, lesson_id),
        started=started,
        wall_seconds=wall,
        start_stage=start_stage,
        rerun=had_lesson,
        error=error,
        recorded=recorded,
    )


def _generate(data_dir: Path, lesson_id: str, subject: str, start_stage: int, call: Call, rerun: bool) -> None:
    work = work_dir(data_dir, lesson_id)
    work.mkdir(parents=True, exist_ok=True)
    clear_from(work, start_stage)
    with db.connect(data_dir) as conn:
        materials = library.list_materials(conn, lesson_id)
        row = library.get_lesson_row(conn, lesson_id)
    domain = row.domain if row else None
    sql = subject == "computer_science" and domain == "sql"
    # A SQL chapter lesson's problem set is the problems recommended for the chapter.
    chapter = row.chapter if row and sql else None
    image_for = lambda database: databases.image_for(data_dir, materials_dir(data_dir, lesson_id), database)  # noqa: E731
    # A SQL lesson's course database, if it has one: its name and bytes.
    course = None
    if sql:
        names = databases.course_databases(materials_dir(data_dir, lesson_id))
        if names:
            course = (names[0], image_for(f"course/{names[0]}"))

    if start_stage <= 1:
        _set_stage(data_dir, lesson_id, 1)
        source = [Material(m.filename, m.role, m.force_transcription) for m in materials]
        normalized, pages = ingest(materials_dir(data_dir, lesson_id), source, call)
        (work / NORMALIZED).mkdir(exist_ok=True)
        (work / NORMALIZED / PROBLEM_SET_FILE).write_text(normalized.problem_set)
        (work / NORMALIZED / REFERENCE_FILE).write_text(normalized.reference)
        write_json(work / "pages.json", [asdict(p) for p in pages])
    else:
        normalized = Normalized(
            (work / NORMALIZED / PROBLEM_SET_FILE).read_text(), (work / NORMALIZED / REFERENCE_FILE).read_text()
        )
    if not normalized.problem_set.strip():
        raise GenerationError("No text could be read from the problem set.")
    recommended = _recommended(data_dir, normalized) if chapter is not None else None
    database = prompts.course_database(course[0], databases.tables(course[1])) if course else None
    problem_databases = _problem_databases(recommended, image_for) if recommended else None
    context = prompts.materials(subject, normalized.problem_set, normalized.reference, database, problem_databases)

    if start_stage <= 2:
        _set_stage(data_dir, lesson_id, 2)
        if recommended is not None:
            extraction = _extract_recommended(recommended, context, call)
        else:
            extraction = _extract(data_dir, subject, domain, normalized, context, call)
        write_output(work / "extraction.json", extraction)
    else:
        extraction = load_output(work / "extraction.json", Extraction)

    if start_stage <= 3:
        _set_stage(data_dir, lesson_id, 3)

        def plan_attempt(feedback: str | None) -> tuple[Plan, list[SectionPlan]]:
            plan = call(
                "generate",
                system=prompts.PLAN_SYSTEM + (prompts.SQL_PLAN_RULES if sql else ""),
                prompt=context + [prompts.plan_request(extraction, feedback)],
                output=Plan,
            )
            return plan, place_problems(plan, extraction)

        plan, outline = retrying("Planning", plan_attempt)
        write_output(work / "plan.json", plan)
        write_json(work / "outline.json", outline_json(plan, outline))
        _record(data_dir, lambda conn: library.set_title(conn, lesson_id, plan.title))
    else:
        plan = load_output(work / "plan.json", Plan)
        outline = place_problems(plan, extraction)

    _set_stage(data_dir, lesson_id, 4)
    section_rules = {"computer_science": prompts.CS_SECTION_RULES, "general": prompts.GENERAL_SECTION_RULES}
    if sql:
        rules = prompts.sql_section_rules(course[0] if course else None, chapter=chapter is not None)
    else:
        rules = section_rules.get(subject, "")
    section_system = prompts.SECTION_SYSTEM + rules
    # Practice exercises from the bank, chosen by the features each section teaches, never a problem set's.
    practice = [[] for _ in outline]
    if sql:
        assigned = {a.exercise for a in extraction.answers.values() if isinstance(a, QueryAnswer)}
        bank = [e for e in load_bank(data_dir) if e.id not in assigned]
        practice = choose(bank, [set(s.sql_features) for s in outline])
    sections: list[Section] = []
    for number, section_plan in enumerate(outline, start=1):
        tries = count(1)

        def section_attempt(
            feedback: str | None, section_plan: SectionPlan = section_plan, tries: Iterator[int] = tries
        ) -> Section:
            # A diagram still laid out badly on the last attempt is dropped, so a figure never fails the lesson.
            last = next(tries) == ATTEMPTS
            draft = call(
                "generate",
                system=section_system,
                prompt=context + [prompts.section_request(section_plan, outline, feedback)],
                output=SectionDraft,
            )
            section = assemble_section(section_plan, draft, extraction.answers, drop_bad_diagrams=last)
            if sql:
                return settle_queries(section, course)
            refuse_queries(section)
            return section

        section = retrying(f"Section {number} ({section_plan.title})", section_attempt)
        section = retrying(f"Hints for section {number}", lambda _feedback, s=section: add_hints(s, context, call))
        try:
            section, results = retrying(
                f"Verification for section {number}",
                lambda _feedback, s=section: verify_section(s, context, call, image_for),
            )
            write_json(work / f"verification-{number}.json", [asdict(r) for r in results])
        except GenerationError as error:
            # Unverified is the safe state, so a verification pass that keeps failing leaves it there.
            write_json(work / f"verification-{number}.json", {"error": str(error)})
        # Practice comes from the bank whole, so it is added after the model's hints and verification.
        section = add_practice(section, practice[number - 1])
        write_output(work / f"section-{number}.json", section)
        sections.append(section)

    credits = [BOOK_CREDIT] if chapter is not None else []
    filenames = [m.filename for m in materials]
    lesson = assemble_lesson(lesson_id, plan.title, subject, filenames, sections, domain, credits)
    target = lesson_path(data_dir, lesson_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    write_output(target, lesson)
    with db.connect(data_dir) as conn:
        if rerun:
            progress.carry_over(conn, lesson_id, lesson)
            test_flags.carry_over(conn, lesson_id, lesson)
            simulation_state.clear(conn, lesson_id)
            solution_state.clear(conn, lesson_id)
        library.set_ready(conn, lesson_id, rerun=rerun)


def _recommended(data_dir: Path, normalized: Normalized) -> list[RecommendedProblem]:
    try:
        return parse_recommended(normalized.problem_set, load_bank(data_dir))
    except ProblemListError as error:
        raise GenerationError(str(error)) from error


def _problem_databases(recommended: list[RecommendedProblem], image_for: Callable[[str], bytes]) -> str | None:
    """The tables of the bank databases a chapter lesson's problems use, as the model sees them."""
    shown = []
    for database in bank_databases(recommended):
        try:
            image = image_for(database)
        except databases.DatabaseMissing as error:
            raise GenerationError(f"A problem's database is missing: {error}. Import Spider again.") from error
        shown.append(prompts.course_database(database.partition("/")[2], databases.tables(image)))
    return "\n\n".join(shown) or None


def _extract_recommended(recommended: list[RecommendedProblem], context: list[dict], call: Call) -> Extraction:
    # The server lists the problems; the model only says which concepts each needs.
    return retrying(
        "Extraction",
        lambda feedback: build_recommended(
            recommended,
            call(
                "generate",
                system=prompts.SQL_EXTRACT_SYSTEM,
                prompt=context + [prompts.sql_extract_request(recommended, feedback)],
                output=ConceptMap,
            ),
        ),
    )


def _extract(
    data_dir: Path, subject: str, domain: str | None, normalized: Normalized, context: list[dict], call: Call
) -> Extraction:
    # Only DSA lessons have a LeetCode problem list; a computer science lesson with no domain is DSA.
    if subject != "computer_science" or domain == "sql":
        draft = retrying(
            "Extraction",
            lambda feedback: call(
                "generate",
                system=prompts.EXTRACT_SYSTEM,
                prompt=context + [prompts.extract_request(feedback)],
                output=ProblemsAndConcepts,
            ),
        )
        return Extraction.model_validate(draft.model_dump())

    # The server lists the problems; the model only says which concepts each needs.
    try:
        listed = parse_problem_list(normalized.problem_set)
        found = find_in_dataset(data_dir, listed)
    except ProblemListError as error:
        raise GenerationError(str(error)) from error
    descriptions = {number: problem.description for number, problem in found.items()}
    return retrying(
        "Extraction",
        lambda feedback: build_extraction(
            listed,
            call(
                "generate",
                system=prompts.CS_EXTRACT_SYSTEM,
                prompt=context + [prompts.cs_extract_request(listed, descriptions, feedback)],
                output=ConceptMap,
            ),
            found,
        ),
    )


def clear_from(work: Path, stage: int) -> None:
    """Remove outputs of the stages a run will redo, so none are left over from a longer earlier run."""
    outputs = {
        1: ["pages.json", NORMALIZED],
        2: ["extraction.json"],
        3: ["plan.json", "outline.json"],
        4: ["section-*.json", "verification-*.json"],
    }
    for s in STAGES:
        if s < stage:
            continue
        for pattern in outputs[s]:
            for path in work.glob(pattern):
                shutil.rmtree(path) if path.is_dir() else path.unlink()


def outline_json(plan: Plan, outline: list[SectionPlan]) -> dict:
    return {
        "title": plan.title,
        "sections": [
            {
                "id": s.id,
                "title": s.title,
                "goal": s.goal,
                "concepts": [c.id for c in s.concepts],
                "problems": [p.source_ref for p in s.problems],
            }
            for s in outline
        ],
    }


def load_output(path: Path, model: type[BaseModel]):
    """A saved stage output, or None if it is missing or no longer matches its schema."""
    try:
        return model.model_validate_json(path.read_text())
    except (OSError, ValidationError):
        return None


def _set_stage(data_dir: Path, lesson_id: str, stage: int) -> None:
    _record(data_dir, lambda conn: library.set_stage(conn, lesson_id, stage))
    usage.set_stage(STAGE_NAMES[stage])


def _record(data_dir: Path, update: Callable) -> None:
    with db.connect(data_dir) as conn:
        update(conn)


def write_output(path: Path, model: BaseModel) -> None:
    write_json(path, model.model_dump(mode="json"))


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
