"""Tests the student flagged as broken, kept apart from the lesson JSON.

A flag is keyed by lesson, block, part, and the test's text (arguments and expected value). See
architecture/code-problems.md, Flags.
"""

import sqlite3
from datetime import UTC, datetime

from .lesson import CodeAnswer, Lesson, ProblemBlock


def load_all(conn: sqlite3.Connection, lesson_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT block_id, part_id, args, expected FROM test_flags WHERE lesson_id = ?"
        " ORDER BY block_id, part_id, created",
        (lesson_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def set_flag(
    conn: sqlite3.Connection, lesson_id: str, block_id: str, part_id: str, args: str, expected: str, flagged: bool
) -> None:
    if flagged:
        conn.execute(
            "INSERT OR IGNORE INTO test_flags (lesson_id, block_id, part_id, args, expected, created)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (lesson_id, block_id, part_id, args, expected, datetime.now(UTC).isoformat()),
        )
    else:
        conn.execute(
            "DELETE FROM test_flags WHERE lesson_id = ? AND block_id = ? AND part_id = ? AND args = ? AND expected = ?",
            (lesson_id, block_id, part_id, args, expected),
        )


def clear(conn: sqlite3.Connection, lesson_id: str, block_id: str, part_id: str) -> None:
    conn.execute(
        "DELETE FROM test_flags WHERE lesson_id = ? AND block_id = ? AND part_id = ?", (lesson_id, block_id, part_id)
    )
