"""Lesson files in the app data folder."""

import re
import shutil
from pathlib import Path

from . import db
from .ids import ID_PATTERN
from .lesson import Lesson
from .library import add_ready_lesson

SAMPLE_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample-lesson.json"


def lessons_dir(data_dir: Path) -> Path:
    return data_dir / "lessons"


SAMPLE_SEEDED = "sample_seeded"


def seed_sample(data_dir: Path) -> None:
    """Add the hand-written sample lesson on the first start only, so a deleted sample stays deleted."""
    with db.connect(data_dir) as conn:
        if db.get_setting(conn, SAMPLE_SEEDED):
            return
        target = lessons_dir(data_dir) / "sample.json"
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SAMPLE_FIXTURE, target)
        add_ready_lesson(conn, Lesson.model_validate_json(SAMPLE_FIXTURE.read_text()))
        db.set_setting(conn, SAMPLE_SEEDED, "1")


def delete_lesson_files(data_dir: Path, lesson_id: str) -> None:
    """Remove a lesson's JSON, uploaded files, and stage outputs."""
    if not re.fullmatch(ID_PATTERN, lesson_id):
        raise ValueError(f"not a lesson id: {lesson_id!r}")
    (lessons_dir(data_dir) / f"{lesson_id}.json").unlink(missing_ok=True)
    for folder in (data_dir / "materials" / lesson_id, data_dir / "work" / lesson_id):
        shutil.rmtree(folder, ignore_errors=True)


def load_lesson(data_dir: Path, lesson_id: str) -> Lesson | None:
    if not re.fullmatch(ID_PATTERN, lesson_id):
        return None
    path = lessons_dir(data_dir) / f"{lesson_id}.json"
    if not path.is_file():
        return None
    return Lesson.model_validate_json(path.read_text())
