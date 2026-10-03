"""Stages 2 to 4: from course text to a lesson. See architecture/pipeline.md.

Each stage writes its output under work/{lesson_id}/. A stage whose reply is rejected
(a schema or rule violation) is retried with the reason; a failed section is retried alone.
"""

import json
import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from .. import db, library
from ..lesson import Section
from ..model import ModelError, call_model
from ..storage import lessons_dir
from . import prompts
from .assemble import SectionError, assemble_lesson, assemble_section
from .hints import add_hints
from .plan import PlanError, SectionPlan, place_problems
from .schemas import Extraction, Plan, SectionDraft

log = logging.getLogger(__name__)

ATTEMPTS = 3
MAX_FEEDBACK = 4000
PROBLEM_SET_FILE = "problem-set.md"
REFERENCE_FILE = "reference.md"

T = TypeVar("T")
Call = Callable[..., BaseModel]


class GenerationError(Exception):
    pass


def materials_dir(data_dir: Path, lesson_id: str) -> Path:
    return data_dir / "materials" / lesson_id


def work_dir(data_dir: Path, lesson_id: str) -> Path:
    return data_dir / "work" / lesson_id


def start(data_dir: Path, lesson_id: str, subject: str) -> threading.Thread:
    thread = threading.Thread(target=run, args=(data_dir, lesson_id, subject), daemon=True, name=f"lesson-{lesson_id}")
    thread.start()
    return thread


def run(data_dir: Path, lesson_id: str, subject: str, call: Call = call_model) -> None:
    """Generate the lesson and record the outcome in the index. Never raises."""
    try:
        _generate(data_dir, lesson_id, subject, call)
    except (GenerationError, ModelError) as error:
        _record(data_dir, lambda conn: library.set_failed(conn, lesson_id, str(error)))
    except Exception as error:
        log.exception("lesson %s failed", lesson_id)
        _record(data_dir, lambda conn: library.set_failed(conn, lesson_id, f"Unexpected error: {error}"))


def _generate(data_dir: Path, lesson_id: str, subject: str, call: Call) -> None:
    source = materials_dir(data_dir, lesson_id)
    problem_set = (source / PROBLEM_SET_FILE).read_text()
    reference_path = source / REFERENCE_FILE
    reference = reference_path.read_text() if reference_path.exists() else ""
    context = prompts.materials(subject, problem_set, reference)
    work = work_dir(data_dir, lesson_id)
    work.mkdir(parents=True, exist_ok=True)

    _set_stage(data_dir, lesson_id, 2)
    extraction = _retrying(
        "Extraction",
        lambda feedback: call(
            "generate", system=prompts.EXTRACT_SYSTEM, prompt=context + [prompts.extract_request(feedback)], output=Extraction
        ),
    )
    _write(work / "extraction.json", extraction)

    _set_stage(data_dir, lesson_id, 3)

    def plan_attempt(feedback: str | None) -> tuple[Plan, list[SectionPlan]]:
        plan = call("generate", system=prompts.PLAN_SYSTEM, prompt=context + [prompts.plan_request(extraction, feedback)], output=Plan)
        return plan, place_problems(plan, extraction)

    plan, outline = _retrying("Planning", plan_attempt)
    _write_json(
        work / "plan.json",
        {
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
        },
    )
    _record(data_dir, lambda conn: library.set_title(conn, lesson_id, plan.title))

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

        section = _retrying(f"Section {number} ({section_plan.title})", section_attempt)
        section = _retrying(f"Hints for section {number}", lambda _feedback, s=section: add_hints(s, context, call))
        _write(work / f"section-{number}.json", section)
        sections.append(section)

    source_files = [PROBLEM_SET_FILE] + ([REFERENCE_FILE] if reference.strip() else [])
    lesson = assemble_lesson(lesson_id, plan.title, subject, source_files, sections)
    target = lessons_dir(data_dir) / f"{lesson_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    _write(target, lesson)
    _record(data_dir, lambda conn: library.set_ready(conn, lesson_id))


def _retrying(stage: str, attempt: Callable[[str | None], T]) -> T:
    """Run an attempt, feeding back why the last reply was rejected."""
    feedback = None
    for _ in range(ATTEMPTS):
        try:
            return attempt(feedback)
        except (ValidationError, PlanError, SectionError) as error:
            feedback = str(error)[:MAX_FEEDBACK]
    raise GenerationError(f"{stage} failed after {ATTEMPTS} attempts. Last problem: {feedback}")


def _set_stage(data_dir: Path, lesson_id: str, stage: int) -> None:
    _record(data_dir, lambda conn: library.set_stage(conn, lesson_id, stage))


def _record(data_dir: Path, update: Callable) -> None:
    with db.connect(data_dir) as conn:
        update(conn)


def _write(path: Path, model: BaseModel) -> None:
    _write_json(path, model.model_dump(mode="json"))


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
