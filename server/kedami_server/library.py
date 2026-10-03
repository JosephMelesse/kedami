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
    error: str | None = None


def add_ready_lesson(conn: sqlite3.Connection, lesson: Lesson) -> None:
    """Index a lesson that already exists on disk. Does nothing if it is already indexed."""
    conn.execute(
        "INSERT OR IGNORE INTO lessons (id, title, subject, status, current_stage, schema_version, created)"
        " VALUES (?, ?, ?, 'ready', NULL, ?, ?)",
        (lesson.id, lesson.title, lesson.subject, lesson.schema_version, _now()),
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()


def create_generating(conn: sqlite3.Connection, lesson_id: str, subject: str, schema_version: int) -> None:
    """Index a lesson whose generation is starting. The title arrives with the plan."""
    conn.execute(
        "INSERT INTO lessons (id, title, subject, status, current_stage, schema_version, created)"
        " VALUES (?, 'New lesson', ?, 'generating', NULL, ?, ?)",
        (lesson_id, subject, schema_version, _now()),
    )


def set_stage(conn: sqlite3.Connection, lesson_id: str, stage: int) -> None:
    conn.execute("UPDATE lessons SET current_stage = ? WHERE id = ?", (stage, lesson_id))


def set_title(conn: sqlite3.Connection, lesson_id: str, title: str) -> None:
    conn.execute("UPDATE lessons SET title = ? WHERE id = ?", (title, lesson_id))


def set_ready(conn: sqlite3.Connection, lesson_id: str) -> None:
    conn.execute("UPDATE lessons SET status = 'ready', current_stage = NULL, error = NULL WHERE id = ?", (lesson_id,))


def set_failed(conn: sqlite3.Connection, lesson_id: str, error: str) -> None:
    conn.execute("UPDATE lessons SET status = 'failed', error = ? WHERE id = ?", (error, lesson_id))


def fail_interrupted(conn: sqlite3.Connection) -> None:
    """Generation runs inside the server process, so a restart ends any run in progress."""
    conn.execute(
        "UPDATE lessons SET status = 'failed', error = 'Generation was interrupted when the app closed.'"
        " WHERE status = 'generating'"
    )


def add_material(conn: sqlite3.Connection, lesson_id: str, filename: str, role: str) -> None:
    conn.execute(
        "INSERT INTO materials (lesson_id, filename, role) VALUES (?, ?, ?)", (lesson_id, filename, role)
    )


def list_lessons(conn: sqlite3.Connection) -> list[LessonRow]:
    rows = conn.execute("SELECT * FROM lessons ORDER BY created, id").fetchall()
    return [LessonRow(**row) for row in rows]


def get_lesson_row(conn: sqlite3.Connection, lesson_id: str) -> LessonRow | None:
    row = conn.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
    return LessonRow(**row) if row else None


def problem_ids(lesson: Lesson) -> list[str]:
    return [block.id for section in lesson.sections for block in section.blocks if isinstance(block, ProblemBlock)]
