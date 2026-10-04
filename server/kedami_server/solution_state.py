"""Step-by-step solutions kept apart from the lesson JSON, keyed by block and part ID.

A solution is written the first time the student asks and served from here after that. A
rerun replaces the lesson, so it clears these rows.
"""

import json
import sqlite3
from datetime import UTC, datetime


def load(conn: sqlite3.Connection, lesson_id: str, block_id: str, part_id: str) -> dict | None:
    """The stored solution as sent to the renderer, or None if none has been written."""
    row = conn.execute(
        "SELECT solution, matches FROM solutions WHERE lesson_id = ? AND block_id = ? AND part_id = ?",
        (lesson_id, block_id, part_id),
    ).fetchone()
    if row is None:
        return None
    return {"solution": json.loads(row["solution"]), "matches": None if row["matches"] is None else bool(row["matches"])}


def save(
    conn: sqlite3.Connection, lesson_id: str, block_id: str, part_id: str, solution: dict, matches: bool | None
) -> None:
    conn.execute(
        "INSERT INTO solutions (lesson_id, block_id, part_id, solution, matches, updated) VALUES (?, ?, ?, ?, ?, ?)"
        " ON CONFLICT (lesson_id, block_id, part_id) DO UPDATE SET solution = excluded.solution,"
        " matches = excluded.matches, updated = excluded.updated",
        (lesson_id, block_id, part_id, json.dumps(solution), None if matches is None else int(matches), _now()),
    )


def clear(conn: sqlite3.Connection, lesson_id: str) -> None:
    conn.execute("DELETE FROM solutions WHERE lesson_id = ?", (lesson_id,))


def _now() -> str:
    return datetime.now(UTC).isoformat()
