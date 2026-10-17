"""The databases SQL queries run against: course databases uploaded with a SQL lesson, and the exercise
bank's. See architecture/sql-lessons.md, Course databases.

Every database is kept as a SQLite file and read here as bytes, which queries.run copies into memory. An
uploaded SQL script is the one SQL in Kedami that may write, so it runs in a database of its own, with
limits, and only that database's bytes are kept.
"""

import sqlite3
import time
from functools import lru_cache
from pathlib import Path

from .queries import SQLITE_HEADER, open_copy

MAX_UPLOAD = 20_000_000
SCRIPT_TIME_LIMIT_S = 10.0
# A database built from a script stops growing here; SQLite's default page is 4,096 bytes.
_MAX_PAGES = MAX_UPLOAD // 4096

DATABASE_EXTENSIONS = (".sqlite", ".db")
SCRIPT_EXTENSIONS = (".sql",)


class DatabaseFileError(ValueError):
    """An uploaded database that can't be used, with a message fit to show the student."""


def from_upload(name: str, data: bytes) -> bytes:
    """A course database's bytes, from an uploaded SQLite file or SQL script. Raises DatabaseFileError."""
    if len(data) > MAX_UPLOAD:
        raise DatabaseFileError(f"{name} is over {MAX_UPLOAD // 1_000_000} MB.")
    lower = name.lower()
    if lower.endswith(DATABASE_EXTENSIONS):
        image = _from_file(name, data)
    elif lower.endswith(SCRIPT_EXTENSIONS):
        image = _from_script(name, data)
    else:
        raise DatabaseFileError(f"{name} isn't a SQLite file (.sqlite or .db) or a SQL script (.sql).")
    _require_tables(name, image)
    try:
        tables(image, rows=1)
    except sqlite3.Error as error:
        # Such as a virtual table whose module SQLite doesn't have.
        raise DatabaseFileError(f"{name} has a table that can't be read: {error}") from None
    return image


def _from_file(name: str, data: bytes) -> bytes:
    if data[:16] != SQLITE_HEADER:
        raise DatabaseFileError(f"{name} isn't a SQLite database.")
    try:
        conn = open_copy(data)
        try:
            # Reads every page, so a damaged file is refused now rather than when a query reaches it.
            problems = [row[0] for row in conn.execute("PRAGMA quick_check")]
            image = conn.serialize()
        finally:
            conn.close()
    except sqlite3.Error as error:
        raise DatabaseFileError(f"{name} can't be read: {error}") from None
    if problems != ["ok"]:
        raise DatabaseFileError(f"{name} is damaged: {problems[0]}")
    return image


def _from_script(name: str, data: bytes) -> bytes:
    try:
        script = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise DatabaseFileError(f"{name} isn't UTF-8 text.") from None
    conn = sqlite3.connect(":memory:", isolation_level=None)
    try:
        conn.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, True)
        conn.setconfig(sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA, False)
        conn.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
        conn.execute(f"PRAGMA max_page_count = {_MAX_PAGES}")
        conn.set_authorizer(_authorize_script)
        deadline = time.monotonic() + SCRIPT_TIME_LIMIT_S
        conn.set_progress_handler(lambda: time.monotonic() > deadline, 1000)
        try:
            conn.executescript(script)
        except sqlite3.Error as error:
            if time.monotonic() > deadline:
                raise DatabaseFileError(f"{name} took longer than {SCRIPT_TIME_LIMIT_S:g} seconds to run.") from None
            if "full" in str(error):
                raise DatabaseFileError(f"{name} builds a database over {MAX_UPLOAD // 1_000_000} MB.") from None
            raise DatabaseFileError(f"{name} failed: {error}") from None
        conn.set_authorizer(None)
        conn.set_progress_handler(None, 0)
        # SQLite can't serialize a database with nothing in it, so a script that made no tables stops here.
        if conn.execute("SELECT count(*) FROM sqlite_schema WHERE type = 'table'").fetchone()[0] == 0:
            raise DatabaseFileError(f"{name} has no tables.")
        return conn.serialize()
    finally:
        conn.close()


# A script may create and fill tables, views, indexes, and triggers, and use transactions. It may not reach
# outside its own database or change how SQLite runs.
_SCRIPT_DENIED = {sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_PRAGMA}


def _authorize_script(action: int, arg1, arg2, database, trigger) -> int:
    if action in _SCRIPT_DENIED:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and arg2 == "load_extension":
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _require_tables(name: str, image: bytes) -> None:
    conn = open_copy(image)
    try:
        count = conn.execute("SELECT count(*) FROM sqlite_schema WHERE type = 'table'").fetchone()[0]
    finally:
        conn.close()
    if count == 0:
        raise DatabaseFileError(f"{name} has no tables.")


def tables(image: bytes, rows: int = 20) -> list[dict]:
    """Each table's name, columns, first `rows` rows, and row count, for showing beside an exercise."""
    conn = open_copy(image)
    try:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid"
        )]
        shown = []
        for table in names:
            quoted = '"' + table.replace('"', '""') + '"'
            cursor = conn.execute(f"SELECT * FROM {quoted} LIMIT {rows}")
            shown.append({
                "name": table,
                "columns": [d[0] for d in cursor.description],
                "rows": [list(row) for row in cursor.fetchall()],
                "count": conn.execute(f"SELECT count(*) FROM {quoted}").fetchone()[0],
            })
        return shown
    finally:
        conn.close()


def read(path: Path) -> bytes:
    """A database file's bytes, kept in memory until the file changes."""
    stat = path.stat()
    return _read(path, stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=64)
def _read(path: Path, mtime_ns: int, size: int) -> bytes:
    return path.read_bytes()
