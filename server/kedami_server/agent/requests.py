"""Solutions and simulations Claude Code writes when the student asks for one.
See architecture/agent-mode.md, Solutions and simulations.

A solution's request never shows the stored answer, and its final answer is compared with it.
Simulation code is checked and stored apart from the lesson JSON. They work on any ready math,
physics, or general lesson, including ones the old API pipeline made.
"""

from pathlib import Path

from pydantic import ValidationError

from .. import db, simulation_state, solution_state
from ..generation import prompts, stages
from ..generation.schemas import SimulationCode
from ..generation.solutions import OUTPUTS, Steps, has_solution
from ..generation.verify import agrees, answer_format
from ..lesson import Lesson, Part, ProblemBlock, SimulationBlock
from ..storage import load_lesson
from .draft import NotFound, OutOfOrder, Rejected


def solution_request(data_dir: Path, lesson_id: str, block_id: str, part_id: str) -> dict:
    lesson, block, part = _part(data_dir, lesson_id, block_id, part_id)
    _unsolved(data_dir, lesson_id, block_id, part_id)
    compared = part.answer.kind != "self_check"
    return {
        "subject": lesson.subject,
        "problem": block.source_ref,
        "shared_text": block.prompt,
        "parts": [{"label": p.label, "text": p.prompt} for p in block.parts],
        "solve_part": part.label,
        "answer": answer_format(part.answer) if compared else {"format": "shown"},
        "materials": _materials(data_dir, lesson_id),
    }


def save_solution(
    data_dir: Path, lesson_id: str, block_id: str, part_id: str, steps: dict, after_disagreement: bool
) -> dict:
    """Store a solution whose final answer agrees with the stored one. The first disagreement is sent
    back with the stored answer, unsaved; after it, the solution is stored as not matching."""
    lesson, _, part = _part(data_dir, lesson_id, block_id, part_id)
    _unsolved(data_dir, lesson_id, block_id, part_id)
    try:
        written: Steps = OUTPUTS[lesson.subject].model_validate(steps)
    except ValidationError as error:
        raise Rejected(str(error)) from error
    matches = None if part.answer.kind == "self_check" else agrees(part.answer, written.final)
    if matches is False and not after_disagreement:
        return {"saved": False, "matches": False, "disagreement": prompts.disagreement(part.answer, written.final)}
    with db.connect(data_dir) as conn:
        solution_state.save(conn, lesson_id, block_id, part_id, {"format": lesson.subject, **written.model_dump()}, matches)
    return {"saved": True, "matches": matches}


def simulation_request(data_dir: Path, lesson_id: str, block_id: str) -> dict:
    lesson, block = _simulation(data_dir, lesson_id, block_id)
    section = next(s for s in lesson.sections if any(b.id == block_id for b in s.blocks))
    with db.connect(data_dir) as conn:
        state = simulation_state.load(conn, lesson_id, block_id)
    return {
        "section": section.title,
        "goal": section.goal,
        "brief": block.brief,
        "caption": block.caption,
        "teaching": [b.body for b in section.blocks if b.type == "explanation"],
        "failure": state.error if state.flagged else None,
        "materials": _materials(data_dir, lesson_id),
    }


def save_simulation(data_dir: Path, lesson_id: str, block_id: str, code: str) -> dict:
    _simulation(data_dir, lesson_id, block_id)
    try:
        checked = SimulationCode.model_validate({"code": code})
    except ValidationError as error:
        raise Rejected(str(error)) from error
    with db.connect(data_dir) as conn:
        simulation_state.save_code(conn, lesson_id, block_id, checked.code)
    return {"saved": True}


def _lesson(data_dir: Path, lesson_id: str) -> Lesson:
    with db.connect(data_dir) as conn:
        row = conn.execute("SELECT status FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
    lesson = load_lesson(data_dir, lesson_id) if row and row["status"] == "ready" else None
    if lesson is None:
        raise NotFound("lesson not found or not ready")
    return lesson


def _part(data_dir: Path, lesson_id: str, block_id: str, part_id: str) -> tuple[Lesson, ProblemBlock, Part]:
    lesson = _lesson(data_dir, lesson_id)
    block = lesson.find_block(block_id)
    part = next((p for p in block.parts if p.id == part_id), None) if isinstance(block, ProblemBlock) else None
    if part is None or not has_solution(lesson.subject, part):
        raise NotFound("This part has no solution.")
    return lesson, block, part


def _unsolved(data_dir: Path, lesson_id: str, block_id: str, part_id: str) -> None:
    with db.connect(data_dir) as conn:
        if solution_state.load(conn, lesson_id, block_id, part_id) is not None:
            raise OutOfOrder("This part already has a solution.")


def _simulation(data_dir: Path, lesson_id: str, block_id: str) -> tuple[Lesson, SimulationBlock]:
    lesson = _lesson(data_dir, lesson_id)
    block = lesson.find_block(block_id)
    if not isinstance(block, SimulationBlock):
        raise NotFound("simulation block not found")
    return lesson, block


def _materials(data_dir: Path, lesson_id: str) -> list[str]:
    """The lesson's normalized course material, as files Claude Code can read. Empty for a lesson with none."""
    folder = stages.work_dir(data_dir, lesson_id) / stages.NORMALIZED
    return [str(folder / name) for name in (stages.PROBLEM_SET_FILE, stages.REFERENCE_FILE) if (folder / name).exists()]
