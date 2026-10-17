"""Running and comparing SQL for SQL lessons. See architecture/sql-lessons.md.

SQL from the student, the exercise bank, and the model runs here, on the server, so every query runs in a
fresh in-memory copy of its database, loaded from the database's bytes: never in the database file, never in
kedami.db. An authorizer allows reading only, one statement runs, a progress handler stops a query after a
time limit, and a length limit keeps any one string or blob small. Course databases come from uploads, so
every connection also runs in SQLite's defensive mode and doesn't trust the schema.
"""

import math
import sqlite3
import time
from dataclasses import dataclass

TIME_LIMIT_S = 2.0
MAX_ROWS = 1000
# Longest string or blob a query may build, which keeps functions such as randomblob() from using much memory.
MAX_LENGTH = 1_000_000
MAX_QUERY_LENGTH = 20_000
# Reals are compared to this many significant digits, so 0.1 + 0.2 equals 0.3.
DIGITS = 12

SQLITE_HEADER = b"SQLite format 3\x00"

# Statements that aren't queries, refused by their first word before they are prepared, since SQLite doesn't
# ask the authorizer about every statement (REINDEX with no name, for one). Any other first word is left to
# SQLite, so a typo such as "SELEC" gets its syntax error, and the authorizer stands behind this.
_NOT_QUERIES = {
    "ALTER", "ANALYZE", "ATTACH", "BEGIN", "COMMIT", "CREATE", "DELETE", "DETACH", "DROP", "END", "EXPLAIN",
    "INSERT", "PRAGMA", "REINDEX", "RELEASE", "REPLACE", "ROLLBACK", "SAVEPOINT", "UPDATE", "VACUUM",
}
_REFUSED = "Only queries that read the tables can run here."

# What reading needs. Everything else, including writes, schema changes, transactions, ATTACH (which
# VACUUM also uses), and PRAGMA (which pragma table functions also use), is denied.
_ALLOWED = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}


class QueryError(ValueError):
    """A query that can't run, with a message fit to show the student."""


@dataclass(frozen=True)
class Result:
    columns: list[str]
    rows: list[tuple]
    # True when the query returned more than MAX_ROWS rows; only the first MAX_ROWS are kept.
    truncated: bool = False


def run(image: bytes, query: str, time_limit: float = TIME_LIMIT_S) -> Result:
    """Run one read-only query against a fresh in-memory copy of the database whose bytes are `image`."""
    if not query.strip():
        raise QueryError("Write a query.")
    if len(query) > MAX_QUERY_LENGTH:
        raise QueryError(f"The query is longer than {MAX_QUERY_LENGTH:,} characters.")
    first = next((word.upper() for word, _ in _words(query)), None)
    if first in _NOT_QUERIES:
        raise QueryError(_REFUSED)
    conn = open_copy(image)
    try:
        conn.set_authorizer(_authorize)
        deadline = time.monotonic() + time_limit
        conn.set_progress_handler(lambda: time.monotonic() > deadline, 1000)
        try:
            cursor = conn.execute(query)
            rows = cursor.fetchmany(MAX_ROWS + 1)
        except sqlite3.ProgrammingError as error:
            if "one statement at a time" in str(error):
                raise QueryError("Write one query at a time.") from None
            raise QueryError(str(error)) from None
        except sqlite3.DatabaseError as error:
            if time.monotonic() > deadline:
                raise QueryError(f"The query took longer than {time_limit:g} seconds.") from None
            if "not authorized" in str(error) or "authorization denied" in str(error):
                raise QueryError(_REFUSED) from None
            raise QueryError(str(error)) from None
        if cursor.description is None:
            raise QueryError("Write a query that returns rows, such as a SELECT.")
        columns = [d[0] for d in cursor.description]
    finally:
        conn.close()
    return Result(columns, rows[:MAX_ROWS], truncated=len(rows) > MAX_ROWS)


def open_copy(image: bytes) -> sqlite3.Connection:
    """A fresh in-memory database holding a copy of `image`, hardened for a schema that may be untrusted."""
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, True)
    conn.setconfig(sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA, False)
    conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_LENGTH)
    conn.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, MAX_QUERY_LENGTH + 1000)
    conn.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
    conn.deserialize(rollback_journal(image))
    return conn


def rollback_journal(image: bytes) -> bytes:
    """The image marked as a rollback-journal database. An in-memory copy can't use write-ahead logging, and a
    database saved in that mode says so in two header bytes, so they are reset."""
    if image[:16] == SQLITE_HEADER and image[18:20] == b"\x02\x02":
        return image[:18] + b"\x01\x01" + image[20:]
    return image


def _authorize(action: int, arg1, arg2, database, trigger) -> int:
    if action not in _ALLOWED:
        return sqlite3.SQLITE_DENY
    # Reads come only from the database itself.
    if action == sqlite3.SQLITE_READ and database not in ("main", None):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


# SQL features, for choosing practice exercises. See the exercise bank in architecture/sql-lessons.md.

FEATURES = (
    "selecting", "filtering", "sorting", "limiting", "distinct", "aggregates", "grouping", "having", "joins",
    "subqueries", "set operations", "patterns",
)
_AGGREGATES = {"COUNT", "SUM", "AVG", "MIN", "MAX"}
_FEATURE_WORDS = {
    "WHERE": "filtering", "ORDER": "sorting", "LIMIT": "limiting", "DISTINCT": "distinct", "GROUP": "grouping",
    "HAVING": "having", "JOIN": "joins", "UNION": "set operations", "INTERSECT": "set operations",
    "EXCEPT": "set operations", "LIKE": "patterns",
}


def features(query: str) -> frozenset[str]:
    """The SQL features a query uses, anywhere in it. Every query selects; a SELECT inside parentheses is a
    subquery, while one joined by UNION, INTERSECT, or EXCEPT is not."""
    words = [(word.upper(), depth) for word, depth in _words(query)]
    found = {"selecting"} | {_FEATURE_WORDS[w] for w, _ in words if w in _FEATURE_WORDS}
    if any(w in _AGGREGATES for w, _ in words):
        found.add("aggregates")
    if any(w == "SELECT" and depth > 0 for w, depth in words):
        found.add("subqueries")
    return frozenset(found)


# Comparing results


def compare(expected: Result, got: Result, ordered: bool) -> str | None:
    """None when the results match, otherwise the first reason they don't.

    Columns are compared by position and their names ignored. Rows are compared as lists when the order
    matters, otherwise as multisets. Values follow `_key`.
    """
    if len(got.columns) != len(expected.columns):
        return f"Expected {_count(len(expected.columns), 'column')}, got {len(got.columns)}."
    if got.truncated:
        return f"Expected {_count(len(expected.rows), 'row')}, got more than {MAX_ROWS:,}."
    if len(got.rows) != len(expected.rows):
        return f"Expected {_count(len(expected.rows), 'row')}, got {len(got.rows)}."
    want = [_row_key(row) for row in expected.rows]
    have = [_row_key(row) for row in got.rows]
    if have == want:
        return None
    if sorted(have) == sorted(want):
        return None if not ordered else "The right rows, in the wrong order."
    return "The rows differ."


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _row_key(row: tuple) -> tuple:
    return tuple(_key(value) for value in row)


def _key(value) -> tuple:
    """A sortable key under which equal values are equal: null equals null, an integer equals a real of the
    same value, reals match to DIGITS significant digits, and text and blobs match exactly."""
    if value is None:
        return (0, 0)
    if isinstance(value, int | float):
        if isinstance(value, float):
            if not math.isfinite(value):
                return (1, 0, str(value))
            value = float(f"{value:.{DIGITS}g}")
            if value.is_integer() and abs(value) < 2**53:
                value = int(value)
        return (1, value, "")
    if isinstance(value, str):
        return (2, value)
    return (3, bytes(value))


# Whether a query's row order matters


def is_ordered(query: str) -> bool:
    """True when the query has an ORDER BY outside any parentheses, so it orders its own result. An ORDER BY
    inside a window, a subquery, or a CTE doesn't order the result."""
    words = [word.upper() for word, depth in _words(query) if depth == 0]
    return any(a == "ORDER" and b == "BY" for a, b in zip(words, words[1:]))


def _words(query: str):
    """Each bare word with its parenthesis depth, skipping strings, quoted names, and comments."""
    depth, i, n = 0, 0, len(query)
    while i < n:
        c = query[i]
        if c in "'\"`[":
            close = "]" if c == "[" else c
            i += 1
            while i < n:
                if query[i] == close:
                    # A doubled quote inside a string or name stands for the quote itself.
                    if close != "]" and i + 1 < n and query[i + 1] == close:
                        i += 2
                        continue
                    break
                i += 1
            i += 1
        elif query.startswith("--", i):
            end = query.find("\n", i)
            i = n if end == -1 else end + 1
        elif query.startswith("/*", i):
            end = query.find("*/", i + 2)
            i = n if end == -1 else end + 2
        elif c == "(":
            depth += 1
            i += 1
        elif c == ")":
            depth = max(depth - 1, 0)
            i += 1
        elif c.isalpha() or c == "_":
            start = i
            while i < n and (query[i].isalnum() or query[i] == "_"):
                i += 1
            yield query[start:i], depth
        else:
            i += 1
