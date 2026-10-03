"""SQLite database in the app data folder: the lesson index and progress."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lessons (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    subject TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('generating', 'ready', 'failed')),
    current_stage INTEGER,
    schema_version INTEGER NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    created TEXT NOT NULL,
    error TEXT,
    folder_id INTEGER REFERENCES folders (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS simulations (
    lesson_id TEXT NOT NULL REFERENCES lessons (id) ON DELETE CASCADE,
    block_id TEXT NOT NULL,
    code TEXT,
    flagged INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    updated TEXT NOT NULL,
    PRIMARY KEY (lesson_id, block_id)
);

CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY,
    lesson_id TEXT NOT NULL REFERENCES lessons (id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('problem_set', 'reference')),
    force_transcription INTEGER NOT NULL DEFAULT 0
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
        _add_missing_columns(conn)


# Columns added after a table was first created. CREATE TABLE IF NOT EXISTS skips existing tables.
ADDED_COLUMNS = {
    "lessons": {"error": "TEXT", "folder_id": "INTEGER REFERENCES folders (id) ON DELETE SET NULL"},
}


def _add_missing_columns(conn: sqlite3.Connection) -> None:
    for table, columns in ADDED_COLUMNS.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


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


def get_setting(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
