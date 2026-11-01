"""Table changes a plain ALTER TABLE can't make, applied when the server starts. See storage-and-api.md."""

import sqlite3
from collections.abc import Callable
from pathlib import Path


class MigrationError(RuntimeError):
    pass


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def _folders_are_flat(conn: sqlite3.Connection) -> bool:
    columns = _columns(conn, "folders")
    return bool(columns) and "parent_id" not in columns


def _nest_folders(conn: sqlite3.Connection) -> None:
    """Replace the name's column-level UNIQUE, which can't be dropped. Every folder starts at the top level."""
    conn.execute(
        """
        CREATE TABLE folders_new (
            id INTEGER PRIMARY KEY,
            parent_id INTEGER REFERENCES folders (id) DEFERRABLE INITIALLY DEFERRED,
            name TEXT NOT NULL COLLATE NOCASE,
            created TEXT NOT NULL,
            CHECK (parent_id IS NULL OR parent_id <> id)
        )
        """
    )
    conn.execute("INSERT INTO folders_new (id, parent_id, name, created) SELECT id, NULL, name, created FROM folders")
    conn.execute("DROP TABLE folders")
    # Rename the new table, never the old one: renaming the old one would repoint the references to it.
    conn.execute("ALTER TABLE folders_new RENAME TO folders")


# The columns the rebuilt `lessons` table has. Older databases may lack some, and differ in order, so copy by name.
_LESSON_COLUMNS = (
    "id",
    "title",
    "custom_title",
    "subject",
    "status",
    "current_stage",
    "schema_version",
    "revision",
    "created",
    "error",
    "folder_id",
    "reading_block",
    "day_starts",
    "active",
    "domain",
    "chapter",
    "due_date",
)


def _lessons_lack_placeholders(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'lessons'").fetchone()
    return row is not None and "'placeholder'" not in row[0]


def _allow_placeholders(conn: sqlite3.Connection) -> None:
    """Add the status to its check and let a placeholder have no subject. Neither can be changed with ALTER TABLE."""
    conn.execute(
        """
        CREATE TABLE lessons_new (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            custom_title TEXT,
            subject TEXT,
            status TEXT NOT NULL CHECK (status IN ('placeholder', 'generating', 'ready', 'failed')),
            current_stage INTEGER,
            schema_version INTEGER NOT NULL,
            revision INTEGER NOT NULL DEFAULT 1,
            created TEXT NOT NULL,
            error TEXT,
            folder_id INTEGER REFERENCES folders (id) ON DELETE SET NULL,
            reading_block TEXT,
            day_starts TEXT,
            active INTEGER NOT NULL DEFAULT 0,
            domain TEXT,
            chapter INTEGER,
            due_date TEXT,
            CHECK (subject IS NOT NULL OR status = 'placeholder')
        )
        """
    )
    existing = set(_columns(conn, "lessons"))
    columns = ", ".join(column for column in _LESSON_COLUMNS if column in existing)
    conn.execute(f"INSERT INTO lessons_new ({columns}) SELECT {columns} FROM lessons")
    conn.execute("DROP TABLE lessons")
    conn.execute("ALTER TABLE lessons_new RENAME TO lessons")


# In order: a name for the saved copy, whether this database needs it, and the change.
Migration = tuple[str, Callable[[sqlite3.Connection], bool], Callable[[sqlite3.Connection], None]]
MIGRATIONS: list[Migration] = [
    ("subfolders", _folders_are_flat, _nest_folders),
    ("placeholders", _lessons_lack_placeholders, _allow_placeholders),
]


def _row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'").fetchall()
    return {name: conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for (name,) in tables}


def _save_copy(conn: sqlite3.Connection, path: Path, name: str) -> None:
    """Keep the database as it was. A run that failed partway has already saved it, so an existing copy stays."""
    copy_path = path.with_name(f"{path.name}.before-{name}")
    if copy_path.exists():
        return
    copy = sqlite3.connect(copy_path)
    try:
        conn.backup(copy)
    finally:
        copy.close()


def _apply(conn: sqlite3.Connection, name: str, change: Callable[[sqlite3.Connection], None]) -> None:
    """All of the change or none of it, refused if it loses a row or breaks a reference."""
    counts = _row_counts(conn)
    broken = len(conn.execute("PRAGMA foreign_key_check").fetchall())
    conn.execute("BEGIN IMMEDIATE")
    try:
        change(conn)
        after = _row_counts(conn)
        lost = [table for table, count in counts.items() if after.get(table) != count]
        if lost:
            raise MigrationError(f"Migration {name} changed the rows of: {', '.join(lost)}.")
        if len(conn.execute("PRAGMA foreign_key_check").fetchall()) > broken:
            raise MigrationError(f"Migration {name} broke a reference between tables.")
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def run(path: Path) -> None:
    """Bring an existing database up to date. A new database gets the current tables from the schema instead.

    This uses its own connection with foreign keys off, which can't be changed inside a transaction. Dropping a
    table with them on applies the references to it: every lesson would leave its folder, and dropping `lessons`
    would delete all progress.
    """
    if not path.exists():
        return
    conn = sqlite3.connect(path, isolation_level=None)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        for name, needed, change in MIGRATIONS:
            if needed(conn):
                _save_copy(conn, path, name)
                _apply(conn, name, change)
    finally:
        conn.close()
