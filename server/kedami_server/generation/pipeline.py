"""Stages 1 to 4: from uploaded files to a lesson. See architecture/pipeline.md.

Each stage writes its output under work/{lesson_id}/, so a rerun can start at any stage
whose inputs are on disk. A stage whose reply is rejected (a schema or rule violation)
is retried with the reason; a failed section is retried alone.
"""

import json
import logging
import shutil
import threading
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from pydantic import BaseModel, ValidationError

from .. import db, library, progress, simulation_state
from ..lesson import Section
from ..model import ModelError, call_model
from ..storage import lessons_dir
from . import prompts
from .assemble import assemble_lesson, assemble_section
from .hints import add_hints
from .ingest import Material, Normalized, ingest
from .plan import SectionPlan, place_problems
from .retry import GenerationError, retrying
from .schemas import Extraction, Plan, SectionDraft
from .simulations import write_code
from .verify import verify_section

log = logging.getLogger(__name__)

STAGES = (1, 2, 3, 4)
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
        _load(work / "extraction.json", Extraction) is not None,
        _load(work / "plan.json", Plan) is not None,
    ]
    return [stage for stage in STAGES if (has_materials if stage == 1 else all(outputs[: stage - 1]))]


def run(data_dir: Path, lesson_id: str, subject: str, start_stage: int = 1, call: Call = call_model) -> None:
    """Generate the lesson and record the outcome in the index. Never raises.

    If a previous version of the lesson exists, a failure leaves it in place.
    """
    had_lesson = lesson_path(data_dir, lesson_id).exists()

    def fail(message: str) -> None:
        if had_lesson:
            _record(data_dir, lambda conn: library.set_rerun_failed(conn, lesson_id, message))
        else:
            _record(data_dir, lambda conn: library.set_failed(conn, lesson_id, message))

    try:
        _generate(data_dir, lesson_id, subject, start_stage, call, rerun=had_lesson)
    except (GenerationError, ModelError) as error:
        fail(str(error))
    except Exception as error:
        log.exception("lesson %s failed", lesson_id)
        fail(f"Unexpected error: {error}")


def _generate(data_dir: Path, lesson_id: str, subject: str, start_stage: int, call: Call, rerun: bool) -> None:
    work = work_dir(data_dir, lesson_id)
    work.mkdir(parents=True, exist_ok=True)
    _clear_from(work, start_stage)
    with db.connect(data_dir) as conn:
        materials = library.list_materials(conn, lesson_id)

    if start_stage <= 1:
        _set_stage(data_dir, lesson_id, 1)
        source = [Material(m.filename, m.role, m.force_transcription) for m in materials]
        normalized, pages = ingest(materials_dir(data_dir, lesson_id), source, call)
        (work / NORMALIZED).mkdir(exist_ok=True)
        (work / NORMALIZED / PROBLEM_SET_FILE).write_text(normalized.problem_set)
        (work / NORMALIZED / REFERENCE_FILE).write_text(normalized.reference)
        _write_json(work / "pages.json", [asdict(p) for p in pages])
    else:
        normalized = Normalized(
            (work / NORMALIZED / PROBLEM_SET_FILE).read_text(), (work / NORMALIZED / REFERENCE_FILE).read_text()
        )
    if not normalized.problem_set.strip():
        raise GenerationError("No text could be read from the problem set.")
    context = prompts.materials(subject, normalized.problem_set, normalized.reference)

    if start_stage <= 2:
        _set_stage(data_dir, lesson_id, 2)
        extraction = retrying(
            "Extraction",
            lambda feedback: call(
                "generate",
                system=prompts.EXTRACT_SYSTEM,
                prompt=context + [prompts.extract_request(feedback)],
                output=Extraction,
            ),
        )
        _write(work / "extraction.json", extraction)
    else:
        extraction = _load(work / "extraction.json", Extraction)

    if start_stage <= 3:
        _set_stage(data_dir, lesson_id, 3)

        def plan_attempt(feedback: str | None) -> tuple[Plan, list[SectionPlan]]:
            plan = call(
                "generate", system=prompts.PLAN_SYSTEM, prompt=context + [prompts.plan_request(extraction, feedback)], output=Plan
            )
            return plan, place_problems(plan, extraction)

        plan, outline = retrying("Planning", plan_attempt)
        _write(work / "plan.json", plan)
        _write_json(work / "outline.json", _outline_json(plan, outline))
        _record(data_dir, lambda conn: library.set_title(conn, lesson_id, plan.title))
    else:
        plan = _load(work / "plan.json", Plan)
        outline = place_problems(plan, extraction)

    _set_stage(data_dir, lesson_id, 4)
    sections: list[Section] = []
    for number, section_plan in enumerate(outline, start=1):

        def section_attempt(feedback: str | None, section_plan: SectionPlan = section_plan) -> Section:
            draft = call(
                "generate",
                system=prompts.SECTION_SYSTEM,
                prompt=context + [prompts.section_request(section_plan, outline, feedback)],
                output=SectionDraft,
            )
            return assemble_section(section_plan, draft)

        section = retrying(f"Section {number} ({section_plan.title})", section_attempt)
        section = write_code(section, section_plan.simulation, context, call)
        section = retrying(f"Hints for section {number}", lambda _feedback, s=section: add_hints(s, context, call))
        try:
            section, results = retrying(
                f"Verification for section {number}", lambda _feedback, s=section: verify_section(s, context, call)
            )
            _write_json(work / f"verification-{number}.json", [asdict(r) for r in results])
        except GenerationError as error:
            # Unverified is the safe state, so a verification pass that keeps failing leaves it there.
            _write_json(work / f"verification-{number}.json", {"error": str(error)})
        _write(work / f"section-{number}.json", section)
        sections.append(section)

    lesson = assemble_lesson(lesson_id, plan.title, subject, [m.filename for m in materials], sections)
    target = lesson_path(data_dir, lesson_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    _write(target, lesson)
    with db.connect(data_dir) as conn:
        if rerun:
            progress.carry_over(conn, lesson_id, lesson)
            simulation_state.clear(conn, lesson_id)
        library.set_ready(conn, lesson_id, rerun=rerun)


def _clear_from(work: Path, stage: int) -> None:
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


def _outline_json(plan: Plan, outline: list[SectionPlan]) -> dict:
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


def _load(path: Path, model: type[BaseModel]):
    """A saved stage output, or None if it is missing or no longer matches its schema."""
    try:
        return model.model_validate_json(path.read_text())
    except (OSError, ValidationError):
        return None


def _set_stage(data_dir: Path, lesson_id: str, stage: int) -> None:
    _record(data_dir, lambda conn: library.set_stage(conn, lesson_id, stage))


def _record(data_dir: Path, update: Callable) -> None:
    with db.connect(data_dir) as conn:
        update(conn)


def _write(path: Path, model: BaseModel) -> None:
    _write_json(path, model.model_dump(mode="json"))


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
