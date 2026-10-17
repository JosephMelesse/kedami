"""Course databases from uploads, and reading database files. See architecture/sql-lessons.md."""

import sqlite3

import pytest

from kedami_server import databases
from kedami_server.databases import DatabaseFileError, from_upload, read, tables
from kedami_server.queries import run

SCRIPT = b"""
BEGIN TRANSACTION;
CREATE TABLE student (id INTEGER PRIMARY KEY, name TEXT NOT NULL, year INTEGER);
CREATE TABLE enrolled (student_id INTEGER REFERENCES student (id), course TEXT);
INSERT INTO student VALUES (1, 'Ada', 2), (2, 'Grace', 3);
INSERT INTO enrolled VALUES (1, 'CS101'), (2, 'CS101'), (2, 'DB200');
CREATE INDEX by_course ON enrolled (course);
CREATE VIEW seniors AS SELECT name FROM student WHERE year >= 3;
CREATE TRIGGER no_op AFTER INSERT ON student BEGIN SELECT 1; END;
COMMIT;
"""


def sqlite_file(script: str) -> bytes:
    conn = sqlite3.connect(":memory:")
    conn.executescript(script)
    data = conn.serialize()
    conn.close()
    return data


# SQL scripts


def test_a_script_builds_a_database_that_queries_run_against():
    image = from_upload("course.sql", SCRIPT)
    assert run(image, "SELECT s.name FROM student s JOIN enrolled e ON e.student_id = s.id WHERE e.course = 'DB200'").rows == [
        ("Grace",)
    ]
    assert run(image, "SELECT * FROM seniors").rows == [("Grace",)]


def test_a_script_with_a_byte_order_mark_runs():
    assert run(from_upload("course.sql", b"\xef\xbb\xbf" + SCRIPT), "SELECT count(*) FROM student").rows == [(2,)]


@pytest.mark.parametrize(
    "script",
    [
        "ATTACH DATABASE 'kedami.db' AS k; CREATE TABLE t (x);",
        "CREATE TABLE t (x); PRAGMA writable_schema = ON;",
        "CREATE TABLE t (x); VACUUM INTO 'copy.db';",
        "CREATE TABLE t (x); SELECT load_extension('/tmp/x.so');",
        "CREATE TABLE t (x); DETACH DATABASE main;",
    ],
)
def test_a_script_cant_reach_outside_its_database(script, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kedami.db").write_bytes(b"")
    with pytest.raises(DatabaseFileError, match="failed"):
        from_upload("course.sql", script.encode())
    assert sorted(p.name for p in tmp_path.iterdir()) == ["kedami.db"]
    assert (tmp_path / "kedami.db").read_bytes() == b""


def test_a_runaway_script_is_stopped(monkeypatch):
    monkeypatch.setattr(databases, "SCRIPT_TIME_LIMIT_S", 0.2)
    forever = b"CREATE TABLE t (x); WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n) INSERT INTO t SELECT i FROM n;"
    with pytest.raises(DatabaseFileError, match="took longer than 0.2 seconds"):
        from_upload("course.sql", forever)


def test_a_script_cant_build_a_database_over_the_limit(monkeypatch):
    monkeypatch.setattr(databases, "_MAX_PAGES", 50)
    big = b"CREATE TABLE t (x); WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < 400) INSERT INTO t SELECT randomblob(1000) FROM n;"
    with pytest.raises(DatabaseFileError, match="builds a database over"):
        from_upload("course.sql", big)


@pytest.mark.parametrize(
    "name, data, message",
    [
        ("course.sql", b"CREATE TABLE (", "failed: "),
        ("course.sql", b"\xff\xfe\x00", "isn't UTF-8 text"),
        ("course.sql", b"-- nothing here", "has no tables"),
        ("course.sql", b"CREATE VIEW v AS SELECT 1;", "has no tables"),
        ("course.txt", SCRIPT, "isn't a SQLite file"),
        ("course.sql", b"x" * (databases.MAX_UPLOAD + 1), "over 20 MB"),
    ],
)
def test_a_bad_script_is_refused_with_a_reason(name, data, message):
    with pytest.raises(DatabaseFileError, match=message):
        from_upload(name, data)


# SQLite files


def test_a_sqlite_file_is_kept_and_queried():
    image = from_upload("course.sqlite", sqlite_file("CREATE TABLE t (x); INSERT INTO t VALUES (1), (2);"))
    assert run(image, "SELECT sum(x) FROM t").rows == [(3,)]
    assert run(from_upload("COURSE.DB", image), "SELECT count(*) FROM t").rows == [(2,)]


def test_a_sqlite_file_saved_with_write_ahead_logging_is_kept(tmp_path):
    path = tmp_path / "wal.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript("CREATE TABLE t (x); INSERT INTO t VALUES (5);")
    conn.close()
    assert run(from_upload("wal.sqlite", path.read_bytes()), "SELECT x FROM t").rows == [(5,)]


@pytest.mark.parametrize(
    "data, message",
    [
        (b"not a database at all", "isn't a SQLite database"),
        (b"", "isn't a SQLite database"),
    ],
)
def test_a_file_that_isnt_sqlite_is_refused(data, message):
    with pytest.raises(DatabaseFileError, match=message):
        from_upload("course.sqlite", data)


def test_a_damaged_sqlite_file_is_refused():
    good = sqlite_file("CREATE TABLE t (x); " + " ".join(f"INSERT INTO t VALUES ({i});" for i in range(2000)))
    damaged = good[:4096] + b"\x00" * 4096 + good[8192:]
    with pytest.raises(DatabaseFileError, match="damaged|can't be read"):
        from_upload("course.sqlite", damaged)


def test_a_database_with_a_table_that_cant_be_read_is_refused():
    # A virtual table whose module this SQLite doesn't have, written straight into the schema.
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE t (x);
        PRAGMA writable_schema = ON;
        INSERT INTO sqlite_schema VALUES ('table', 'v', 'v', 0, 'CREATE VIRTUAL TABLE v USING no_such_module()');
    """)
    unreadable = conn.serialize()
    conn.close()
    with pytest.raises(DatabaseFileError, match="can't be read"):
        from_upload("course.sqlite", unreadable)


def test_a_sqlite_file_with_no_tables_is_refused():
    with pytest.raises(DatabaseFileError, match="has no tables"):
        from_upload("course.sqlite", sqlite_file("CREATE VIEW v AS SELECT 1;"))


# Showing tables


def test_tables_show_columns_first_rows_and_counts():
    image = from_upload("course.sql", SCRIPT)
    shown = tables(image, rows=1)
    assert [t["name"] for t in shown] == ["student", "enrolled"]
    assert shown[0] == {"name": "student", "columns": ["id", "name", "year"], "rows": [[1, "Ada", 2]], "count": 2}
    assert shown[1]["count"] == 3


def test_tables_with_awkward_names_are_shown():
    image = from_upload("course.sql", b'CREATE TABLE "order items" ("the ""qty""" INTEGER); INSERT INTO "order items" VALUES (2);')
    assert tables(image) == [{"name": "order items", "columns": ['the "qty"'], "rows": [[2]], "count": 1}]


# Reading files


def test_reading_a_file_is_cached_until_it_changes(tmp_path):
    path = tmp_path / "a.sqlite"
    path.write_bytes(sqlite_file("CREATE TABLE t (x);"))
    first = read(path)
    assert read(path) is first
    path.write_bytes(sqlite_file("CREATE TABLE t (x); CREATE TABLE u (y);"))
    assert read(path) != first
