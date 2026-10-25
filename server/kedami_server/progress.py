"""Per-part progress: state transitions and storage.

Progress lives apart from the lesson JSON, keyed by block and part ID. Checkpoints have
no part, stored as an empty part ID. See architecture/completion-and-verification.md.
"""

import json
import sqlite3
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from .lesson import Lesson, ProblemBlock

NOT_STARTED = "not_started"
IN_PROGRESS = "in_progress"
CORRECT = "correct"
MARKED_DONE = "marked_done"
DONE = (CORRECT, MARKED_DONE)

class Conflict(ValueError):
    """The request doesn't apply to the part's current state."""


@dataclass(frozen=True)
class Record:
    block_id: str
    part_id: str | None
    status: str = NOT_STARTED
    last_response: Any = None
    attempts: int = 0
    hints_used: int = 0
    updated: str | None = None


# Transitions. Each returns a new record and never touches storage.


def after_check(record: Record, correct: bool, response: Any) -> Record:
    if record.status in DONE:
        raise Conflict(f"this part is already {record.status.replace('_', ' ')}")
    return replace(
        record,
        status=CORRECT if correct else IN_PROGRESS,
        last_response=response,
        attempts=record.attempts + 1,
    )


def after_hints(record: Record, count: int, available: int) -> Record:
    """Reveal hints up to `count`. Repeating a request changes nothing."""
    if not 1 <= count <= available:
        raise Conflict(f"there are {available} hints")
    status = IN_PROGRESS if record.status == NOT_STARTED else record.status
    return replace(record, status=status, hints_used=max(record.hints_used, count))


def after_mark_done(record: Record, done: bool) -> Record:
    if record.part_id is None:
        raise Conflict("checkpoints can't be marked done")
    if done:
        if record.status == CORRECT:
            raise Conflict("this part is already correct")
        return replace(record, status=MARKED_DONE)
    if record.status != MARKED_DONE:
        return record
    # Undo returns to the state before marking. A correct part can't be marked, so any
    # recorded response was wrong.
    touched = record.last_response is not None or record.hints_used > 0
    return replace(record, status=IN_PROGRESS if touched else NOT_STARTED)


def problems_done(lesson: Lesson, records: list[Record]) -> int:
    done = {(r.block_id, r.part_id) for r in records if r.status in DONE}
    return sum(
        all((block.id, part.id) in done for part in block.parts)
        for section in lesson.sections
        for block in section.blocks
        if isinstance(block, ProblemBlock)
    )


# Storage


def load(conn: sqlite3.Connection, lesson_id: str, block_id: str, part_id: str | None) -> Record:
    row = conn.execute(
        "SELECT * FROM progress WHERE lesson_id = ? AND block_id = ? AND part_id = ?",
        (lesson_id, block_id, part_id or ""),
    ).fetchone()
    return _from_row(row) if row else Record(block_id=block_id, part_id=part_id)


def load_all(conn: sqlite3.Connection, lesson_id: str) -> list[Record]:
    rows = conn.execute(
        "SELECT * FROM progress WHERE lesson_id = ? ORDER BY block_id, part_id", (lesson_id,)
    ).fetchall()
    return [_from_row(row) for row in rows]


def save(conn: sqlite3.Connection, lesson_id: str, record: Record) -> Record:
    saved = replace(record, updated=datetime.now(UTC).isoformat())
    conn.execute(
        "INSERT INTO progress (lesson_id, block_id, part_id, status, last_response, attempts, hints_used, updated)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        " ON CONFLICT (lesson_id, block_id, part_id) DO UPDATE SET"
        " status = excluded.status, last_response = excluded.last_response, attempts = excluded.attempts,"
        " hints_used = excluded.hints_used, updated = excluded.updated",
        (
            lesson_id,
            saved.block_id,
            saved.part_id or "",
            saved.status,
            None if saved.last_response is None else json.dumps(saved.last_response),
            saved.attempts,
            saved.hints_used,
            saved.updated,
        ),
    )
    return saved


def _from_row(row: sqlite3.Row) -> Record:
    return Record(
        block_id=row["block_id"],
        part_id=row["part_id"] or None,
        status=row["status"],
        last_response=None if row["last_response"] is None else json.loads(row["last_response"]),
        attempts=row["attempts"],
        hints_used=row["hints_used"],
        updated=row["updated"],
    )
