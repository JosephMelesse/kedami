"""Lesson files in the app data folder."""

import re
import shutil
from pathlib import Path

from .ids import ID_PATTERN
from .lesson import Lesson

SAMPLE_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample-lesson.json"


def lessons_dir(data_dir: Path) -> Path:
    return data_dir / "lessons"


def seed_sample(data_dir: Path) -> None:
    """Copy the hand-written sample lesson into the data folder if it isn't there yet."""
    target = lessons_dir(data_dir) / "sample.json"
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SAMPLE_FIXTURE, target)


def load_lesson(data_dir: Path, lesson_id: str) -> Lesson | None:
    if not re.fullmatch(ID_PATTERN, lesson_id):
        return None
    path = lessons_dir(data_dir) / f"{lesson_id}.json"
    if not path.is_file():
        return None
    return Lesson.model_validate_json(path.read_text())
