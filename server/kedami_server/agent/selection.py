"""The block or section the student selected for Claude Code. See architecture/agent-mode.md, Selecting a block.

There is one selection in the app, kept in the settings table. get_selection shows Claude Code the selected
section as the student reads it before answering anything: each block is rebuilt field by field from a short
list, so a stored answer, hint, self-check rubric, or solution can't reach it, and nor can a field added later.
"""

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from .. import db
from ..generation.verify import answer_format
from ..lesson import (
    Answer,
    Block,
    CheckpointBlock,
    DiagramBlock,
    ExplanationBlock,
    Lesson,
    PlotBlock,
    ProblemBlock,
    Section,
    SimulationBlock,
    WorkedExampleBlock,
)
from ..storage import load_lesson
from . import requests

KEY = "selection"
NOTHING_SELECTED = (
    "Nothing is selected. Ask the student to select a block or section in Kedami with its Select control, "
    "then ask again."
)


@dataclass(frozen=True)
class Selection:
    lesson_id: str
    section_id: str | None = None
    block_id: str | None = None


class Invalid(ValueError):
    pass


def load(conn: sqlite3.Connection) -> Selection | None:
    stored = db.get_setting(conn, KEY)
    return Selection(**json.loads(stored)) if stored else None


def save(conn: sqlite3.Connection, selection: Selection | None) -> None:
    if selection is None:
        conn.execute("DELETE FROM settings WHERE key = ?", (KEY,))
    else:
        db.set_setting(conn, KEY, json.dumps(asdict(selection)))


def forget_lesson(conn: sqlite3.Connection, lesson_id: str) -> None:
    """Deleting a lesson clears the selection if it is in that lesson."""
    current = load(conn)
    if current and current.lesson_id == lesson_id:
        save(conn, None)


def check(lesson: Lesson, selection: Selection) -> Selection:
    """The selection, if it names exactly one section or block of this lesson."""
    if (selection.section_id is None) == (selection.block_id is None):
        raise Invalid("Select a section or a block, not both.")
    if selection.section_id is not None and not any(s.id == selection.section_id for s in lesson.sections):
        raise Invalid("That section isn't in this lesson.")
    if selection.block_id is not None and lesson.find_block(selection.block_id) is None:
        raise Invalid("That block isn't in this lesson.")
    return selection


def view(data_dir: Path, selection: Selection | None) -> dict:
    """What get_selection returns: the selected section as the student sees it, and which part is selected."""
    lesson = load_lesson(data_dir, selection.lesson_id) if selection else None
    if selection is None or lesson is None:
        return {"selected": None, "message": NOTHING_SELECTED}
    section = _section(lesson, selection)
    if section is None:
        return {"selected": None, "message": NOTHING_SELECTED}
    selected = {"block": selection.block_id} if selection.block_id else {"section": section.id}
    return {
        "lesson_id": lesson.id,
        "lesson_title": lesson.title,
        "subject": lesson.subject,
        "selected": selected,
        "section": {
            "id": section.id,
            "title": section.title,
            "goal": section.goal,
            "blocks": [_block(block) for block in section.blocks],
        },
        "materials": requests._materials(data_dir, lesson.id),
    }


def _section(lesson: Lesson, selection: Selection) -> Section | None:
    for section in lesson.sections:
        if section.id == selection.section_id or any(b.id == selection.block_id for b in section.blocks):
            return section
    return None


def _block(block: Block) -> dict:
    """A block as the student reads it before answering: teaching in full, questions without their answers."""
    match block:
        case ExplanationBlock():
            return {"type": block.type, "id": block.id, "body": block.body}
        case WorkedExampleBlock():
            return {"type": block.type, "id": block.id, "prompt": block.prompt, "steps": block.steps}
        case PlotBlock():
            functions = [{"expression": f.expression, "label": f.label} for f in block.functions]
            return {"type": block.type, "id": block.id, "caption": block.caption, "functions": functions}
        case DiagramBlock():
            return {"type": block.type, "id": block.id, "caption": block.caption}
        case SimulationBlock():
            return {"type": block.type, "id": block.id, "caption": block.caption, "brief": block.brief}
        case CheckpointBlock():
            return {"type": block.type, "id": block.id, "prompt": block.prompt, "answer": _answer(block.answer)}
        case ProblemBlock():
            parts = [
                {"id": p.id, "label": p.label, "prompt": p.prompt, "answer": _answer(p.answer)} for p in block.parts
            ]
            return {
                "type": block.type,
                "id": block.id,
                "source_ref": block.source_ref,
                "prompt": block.prompt,
                "parts": parts,
            }
    # A block type added later shows only that it is there until it is listed here.
    return {"type": block.type, "id": block.id}


def _answer(answer: Answer) -> dict:
    """The form an answer takes, never the answer. A self-check's rubric describes the answer, so it is left out."""
    if answer.kind == "self_check":
        return {"format": "written, then checked by the student against a rubric"}
    return answer_format(answer)
