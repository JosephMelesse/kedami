"""Where a lesson's files and stage outputs live, and how they are read and written.

Each stage of a build saves its output under work/{lesson_id}/, so the draft can be inspected and a
step saved again replaces the later ones. See architecture/agent-mode.md and storage-and-api.md.
"""

import json
import shutil
from pathlib import Path

from pydantic import BaseModel, ValidationError

from ..storage import lessons_dir
from .plan import SectionPlan
from .schemas import Plan

STAGES = (1, 2, 3, 4)
NORMALIZED = "normalized"
PROBLEM_SET_FILE = "problem-set.md"
REFERENCE_FILE = "reference.md"


def materials_dir(data_dir: Path, lesson_id: str) -> Path:
    return data_dir / "materials" / lesson_id


def work_dir(data_dir: Path, lesson_id: str) -> Path:
    return data_dir / "work" / lesson_id


def lesson_path(data_dir: Path, lesson_id: str) -> Path:
    return lessons_dir(data_dir) / f"{lesson_id}.json"


def clear_from(work: Path, stage: int) -> None:
    """Remove the outputs of a stage and every one after it, so none are left over from a longer earlier build."""
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


def write_output(path: Path, model: BaseModel) -> None:
    write_json(path, model.model_dump(mode="json"))


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
