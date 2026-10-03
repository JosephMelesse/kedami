"""SQLite database in the app data folder: the lesson index and progress."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS lessons (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    subject TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('generating', 'ready', 'failed')),
    current_stage INTEGER,
    schema_version INTEGER NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS progress (
    lesson_id TEXT NOT NULL REFERENCES lessons (id) ON DELETE CASCADE,
    block_id TEXT NOT NULL,
    part_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK (status IN ('not_started', 'in_progress', 'correct', 'marked_done')),
    last_response TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    hints_used INTEGER NOT NULL DEFAULT 0,
    updated TEXT NOT NULL,
    PRIMARY KEY (lesson_id, block_id, part_id)
);
"""


def db_path(data_dir: Path) -> Path:
    return data_dir / "kedami.db"


def init(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    with connect(data_dir) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def connect(data_dir: Path) -> Iterator[sqlite3.Connection]:
    """A connection that commits on success and rolls back on error."""
    conn = sqlite3.connect(db_path(data_dir))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()
