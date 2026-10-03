"""Per-simulation state kept apart from the lesson JSON: regenerated code and load failures.

A row's code, when set, replaces the block's code from the lesson JSON. A rerun replaces
the lesson, so it clears these rows.
"""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class SimulationState:
    code: str | None
    flagged: bool
    error: str | None


def load(conn: sqlite3.Connection, lesson_id: str, block_id: str) -> SimulationState:
    row = conn.execute(
        "SELECT code, flagged, error FROM simulations WHERE lesson_id = ? AND block_id = ?", (lesson_id, block_id)
    ).fetchone()
    if row is None:
        return SimulationState(code=None, flagged=False, error=None)
    return SimulationState(code=row["code"], flagged=bool(row["flagged"]), error=row["error"])


def save_code(conn: sqlite3.Connection, lesson_id: str, block_id: str, code: str) -> None:
    """Store regenerated code. New code has not failed yet, so the flag is cleared."""
    conn.execute(
        "INSERT INTO simulations (lesson_id, block_id, code, flagged, error, updated) VALUES (?, ?, ?, 0, NULL, ?)"
        " ON CONFLICT (lesson_id, block_id) DO UPDATE SET code = excluded.code, flagged = 0, error = NULL,"
        " updated = excluded.updated",
        (lesson_id, block_id, code, _now()),
    )


def set_status(conn: sqlite3.Connection, lesson_id: str, block_id: str, ok: bool, error: str | None) -> None:
    conn.execute(
        "INSERT INTO simulations (lesson_id, block_id, code, flagged, error, updated) VALUES (?, ?, NULL, ?, ?, ?)"
        " ON CONFLICT (lesson_id, block_id) DO UPDATE SET flagged = excluded.flagged, error = excluded.error,"
        " updated = excluded.updated",
        (lesson_id, block_id, int(not ok), None if ok else error, _now()),
    )


def clear(conn: sqlite3.Connection, lesson_id: str) -> None:
    conn.execute("DELETE FROM simulations WHERE lesson_id = ?", (lesson_id,))


def _now() -> str:
    return datetime.now(UTC).isoformat()
