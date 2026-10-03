"""The lesson index: one row per lesson, whatever its generation status."""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from .lesson import Lesson, ProblemBlock

STATUSES = ("generating", "ready", "failed")


@dataclass(frozen=True)
class LessonRow:
    id: str
    title: str
    subject: str
    status: str
    current_stage: int | None
    schema_version: int
    revision: int
    created: str


def add_ready_lesson(conn: sqlite3.Connection, lesson: Lesson) -> None:
    """Index a lesson that already exists on disk. Does nothing if it is already indexed."""
    conn.execute(
        "INSERT OR IGNORE INTO lessons (id, title, subject, status, current_stage, schema_version, created)"
        " VALUES (?, ?, ?, 'ready', NULL, ?, ?)",
        (lesson.id, lesson.title, lesson.subject, lesson.schema_version, datetime.now(UTC).isoformat()),
    )


def list_lessons(conn: sqlite3.Connection) -> list[LessonRow]:
    rows = conn.execute("SELECT * FROM lessons ORDER BY created, id").fetchall()
    return [LessonRow(**row) for row in rows]


def get_lesson_row(conn: sqlite3.Connection, lesson_id: str) -> LessonRow | None:
    row = conn.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
    return LessonRow(**row) if row else None


def problem_ids(lesson: Lesson) -> list[str]:
    return [block.id for section in lesson.sections for block in section.blocks if isinstance(block, ProblemBlock)]
