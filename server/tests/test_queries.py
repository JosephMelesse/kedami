"""Running SQL safely and comparing results. See architecture/sql-lessons.md."""

import sqlite3

import pytest

from kedami_server.queries import MAX_ROWS, QueryError, Result, compare, features, is_ordered, rollback_journal, run

def image(script: str) -> bytes:
    conn = sqlite3.connect(":memory:")
    conn.executescript(script)
    data = conn.serialize()
    conn.close()
    return data


IMAGE = image("""
    CREATE TABLE employees (id INTEGER, name TEXT, dept_id INTEGER, salary REAL);
    INSERT INTO employees VALUES (1, 'Ada', 1, 120.5), (2, 'Grace', 1, 99), (3, 'Linus', 2, NULL), (4, 'Ada', NULL, 80.0);
    CREATE TABLE depts (id INTEGER, name TEXT);
    INSERT INTO depts VALUES (1, 'Engineering'), (2, 'Research'), (3, 'Empty');
""")


def rows(query: str) -> list[tuple]:
    return run(IMAGE, query).rows


# What may run


@pytest.mark.parametrize(
    "query, expected",
    [
        ("SELECT name FROM employees WHERE id = 1", [("Ada",)]),
        ("select count(*) from employees", [(4,)]),
        ("SELECT e.name, d.name FROM employees e JOIN depts d ON d.id = e.dept_id WHERE e.id = 3", [("Linus", "Research")]),
        ("SELECT d.name FROM employees e RIGHT JOIN depts d ON d.id = e.dept_id WHERE e.id IS NULL", [("Empty",)]),
        ("SELECT count(*) FROM employees e FULL OUTER JOIN depts d ON d.id = e.dept_id", [(5,)]),
        ("SELECT name FROM employees WHERE dept_id IN (SELECT id FROM depts WHERE name LIKE 'R%')", [("Linus",)]),
        ("WITH rich AS (SELECT * FROM employees WHERE salary > 100) SELECT name FROM rich", [("Ada",)]),
        ("WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n WHERE x < 3) SELECT sum(x) FROM n", [(6,)]),
        ("SELECT id, rank() OVER (ORDER BY salary DESC) FROM employees WHERE salary IS NOT NULL ORDER BY id",
         [(1, 1), (2, 2), (4, 3)]),
        ("SELECT dept_id, count(*) FROM employees GROUP BY dept_id HAVING count(*) > 1", [(1, 2)]),
        ("SELECT name FROM employees EXCEPT SELECT name FROM employees WHERE dept_id = 1", [("Linus",)]),
        ("SELECT CASE WHEN salary IS NULL THEN 'none' ELSE 'some' END FROM employees WHERE id = 3", [("none",)]),
        ("SELECT upper(substr(name, 1, 2)), date('2024-01-31', '+1 day') FROM employees WHERE id = 2",
         [("GR", "2024-02-01")]),
        ("SELECT 1;", [(1,)]),
        ("VALUES (1, 'a'), (2, 'b')", [(1, "a"), (2, "b")]),
        ("SELECT 1; -- done", [(1,)]),
        ("/* first */ SELECT 2", [(2,)]),
    ],
)
def test_every_kind_of_read_runs(query, expected):
    assert rows(query) == expected


def test_columns_are_named_as_the_query_names_them():
    assert run(IMAGE, "SELECT name AS who, salary FROM employees LIMIT 1").columns == ["who", "salary"]


# What may not run


@pytest.mark.parametrize(
    "query",
    [
        "INSERT INTO depts VALUES (4, 'Sales')",
        "UPDATE employees SET salary = 0",
        "DELETE FROM employees",
        "REPLACE INTO depts VALUES (1, 'X')",
        "CREATE TABLE x (y)",
        "CREATE TEMP TABLE x (y)",
        "CREATE VIEW v AS SELECT 1",
        "CREATE TEMP VIEW v AS SELECT 1",
        "CREATE INDEX i ON employees (name)",
        "CREATE TRIGGER t AFTER INSERT ON depts BEGIN SELECT 1; END",
        "DROP TABLE employees",
        "ALTER TABLE employees ADD COLUMN x",
        "ATTACH DATABASE 'kedami.db' AS k",
        "ATTACH DATABASE ':memory:' AS k",
        "DETACH DATABASE main",
        "PRAGMA table_info(employees)",
        "SELECT * FROM pragma_table_info('employees')",
        "BEGIN",
        "COMMIT",
        "SAVEPOINT s",
        "ANALYZE",
        "REINDEX",
        "VACUUM",
        "VACUUM INTO 'copy.db'",
        "EXPLAIN SELECT 1",
        "WITH gone AS (SELECT 1) DELETE FROM employees",
        "WITH x AS (SELECT 1) INSERT INTO depts SELECT 9, 'Sales'",
        "WITH x AS (SELECT 1) UPDATE employees SET salary = 0",
        "SELECT * FROM pragma_database_list",
        "-- a comment first\nDELETE FROM employees",
    ],
)
def test_anything_but_reading_is_refused_by_the_authorizer(query, tmp_path, monkeypatch):
    # The authorizer refuses these before they run. The fresh in-memory copy and the limit of no attached
    # databases would also stop them, but they are the second line, not the first.
    monkeypatch.chdir(tmp_path)
    with pytest.raises(QueryError, match="Only queries that read the tables can run here"):
        run(IMAGE, query)
    assert list(tmp_path.iterdir()) == []


def test_a_refused_write_changes_nothing_for_the_next_query():
    with pytest.raises(QueryError):
        run(IMAGE, "DELETE FROM employees")
    assert rows("SELECT count(*) FROM employees") == [(4,)]


def test_extensions_cant_be_loaded():
    with pytest.raises(QueryError):
        run(IMAGE, "SELECT load_extension('/tmp/x.so')")


@pytest.mark.parametrize(
    "query, message",
    [
        ("SELECT 1; SELECT 2", "one query at a time"),
        ("SELECT 1; DELETE FROM employees", "one query at a time"),
        ("", "Write a query"),
        ("   \n ", "Write a query"),
        ("SELEC name FROM employees", "syntax error"),
        ("-- only a comment", "Write a query that returns rows"),
        ("SELECT nope FROM employees", "no such column: nope"),
        ("SELECT * FROM nowhere", "no such table: nowhere"),
        ("INSERT INTO depts VALUES (9, 'x')", "Only queries that read"),
    ],
)
def test_a_query_that_cant_run_says_why(query, message):
    with pytest.raises(QueryError, match=message):
        run(IMAGE, query)


def test_a_runaway_query_is_stopped_at_the_time_limit():
    forever = "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) SELECT max(x) FROM n"
    with pytest.raises(QueryError, match="took longer than 0.2 seconds"):
        run(IMAGE, forever, time_limit=0.2)


def test_a_huge_string_or_blob_is_refused():
    with pytest.raises(QueryError, match="too big"):
        run(IMAGE, "SELECT length(randomblob(1000000000))")
    with pytest.raises(QueryError, match="too big"):
        run(IMAGE, "SELECT length(zeroblob(2000000))")


def test_a_very_long_query_is_refused():
    with pytest.raises(QueryError, match="longer than"):
        run(IMAGE, "SELECT 1" + " " * 30_000)


def test_rows_past_the_limit_are_cut_and_flagged():
    many = f"WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n WHERE x < {MAX_ROWS + 5}) SELECT x FROM n"
    result = run(IMAGE, many)
    assert (len(result.rows), result.truncated) == (MAX_ROWS, True)
    exact = run(IMAGE, many.replace(f"{MAX_ROWS + 5}", str(MAX_ROWS)))
    assert (len(exact.rows), exact.truncated) == (MAX_ROWS, False)


def test_nothing_touches_the_apps_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kedami.db").write_bytes(b"")
    for query in ["ATTACH DATABASE 'kedami.db' AS k", "SELECT * FROM k.lessons"]:
        with pytest.raises(QueryError):
            run(IMAGE, query)
    assert (tmp_path / "kedami.db").read_bytes() == b""


# Comparing results


def result(columns: int, *row_list, truncated=False) -> Result:
    return Result([f"c{i}" for i in range(columns)], list(row_list), truncated)


@pytest.mark.parametrize(
    "got, ordered, reason",
    [
        (result(2, (1, "a"), (2, "b")), False, None),
        (result(2, (2, "b"), (1, "a")), False, None),
        (result(2, (2, "b"), (1, "a")), True, "The right rows, in the wrong order."),
        (result(1, (1,), (2,)), False, "Expected 2 columns, got 1."),
        (result(2, (1, "a")), False, "Expected 2 rows, got 1."),
        (result(2, (1, "a"), (2, "b"), (2, "b")), False, "Expected 2 rows, got 3."),
        (result(2, (1, "a"), (2, "B")), False, "The rows differ."),
        (result(2, (1, "a"), (2, "b"), truncated=True), False, "Expected 2 rows, got more than 1,000."),
    ],
)
def test_results_are_compared_by_position_count_and_rows(got, ordered, reason):
    assert compare(result(2, (1, "a"), (2, "b")), got, ordered) == reason


def test_column_names_are_ignored():
    assert compare(Result(["n"], [(1,)]), Result(["count(*)"], [(1,)]), False) is None


def test_duplicates_count():
    expected = result(1, ("a",), ("a",), ("b",))
    assert compare(expected, result(1, ("a",), ("b",), ("b",)), False) == "The rows differ."
    assert compare(expected, result(1, ("b",), ("a",), ("a",)), False) is None


@pytest.mark.parametrize(
    "want, have, same",
    [
        (None, None, True),
        (None, 0, False),
        (None, "", False),
        (2, 2.0, True),
        (0.1 + 0.2, 0.3, True),
        (1 / 3, 0.333333333333, True),
        (1 / 3, 0.3333, False),
        (2, "2", False),
        ("Ada", "ada", False),
        ("Ada", "Ada ", False),
        (b"\x00", b"\x00", True),
        (10**18, 10**18 + 1, False),
    ],
)
def test_values(want, have, same):
    assert (compare(result(1, (want,)), result(1, (have,)), False) is None) is same


def test_nulls_sort_alongside_numbers_and_text_without_error():
    expected = result(1, (None,), (1,), ("a",), (b"x",))
    assert compare(expected, result(1, (b"x",), ("a",), (1.0,), (None,)), False) is None


def test_comparing_real_query_results():
    reference = run(IMAGE, "SELECT name, salary FROM employees WHERE salary > 90 ORDER BY salary DESC")
    ordered = is_ordered("SELECT name, salary FROM employees WHERE salary > 90 ORDER BY salary DESC")
    other_order = run(IMAGE, "SELECT name, salary FROM employees WHERE salary > 90 ORDER BY salary")
    cast = run(IMAGE, "SELECT name AS n, CAST(salary AS REAL) FROM employees WHERE salary >= 99 ORDER BY 2 DESC")
    assert compare(reference, other_order, ordered) == "The right rows, in the wrong order."
    assert compare(reference, cast, ordered) is None


# Whether order matters


@pytest.mark.parametrize(
    "query, ordered",
    [
        ("SELECT name FROM employees ORDER BY name", True),
        ("select name from employees order by name desc limit 2", True),
        ("SELECT name FROM employees ORDER\n  BY name", True),
        ("SELECT a FROM x UNION SELECT a FROM y ORDER BY a", True),
        ("SELECT name FROM employees", False),
        ("SELECT name, rank() OVER (ORDER BY salary) FROM employees", False),
        ("SELECT * FROM (SELECT name FROM employees ORDER BY name)", False),
        ("WITH s AS (SELECT name FROM employees ORDER BY name) SELECT * FROM s", False),
        ("SELECT 'order by' FROM employees", False),
        ('SELECT "order by" FROM employees', False),
        ("SELECT [order by] FROM employees", False),
        ("SELECT `order by` FROM employees", False),
        ("SELECT name FROM employees -- ORDER BY name", False),
        ("SELECT name FROM employees /* ORDER BY name */", False),
        ("SELECT 'it''s (' FROM employees ORDER BY 1", True),
        ("SELECT name FROM employees WHERE note = ')' ORDER BY name", True),
        ("SELECT name AS ordered_by FROM employees", False),
    ],
)
def test_order_matters_only_for_an_order_by_outside_parentheses(query, ordered):
    assert is_ordered(query) is ordered


# The database a query runs against


def test_a_query_runs_against_a_copy_and_never_changes_the_image():
    before = bytes(IMAGE)
    with pytest.raises(QueryError):
        run(IMAGE, "WITH x AS (SELECT 1) DELETE FROM employees")
    assert IMAGE == before


def test_a_database_saved_with_write_ahead_logging_still_loads(tmp_path):
    path = tmp_path / "wal.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript("CREATE TABLE t (x); INSERT INTO t VALUES (7);")
    conn.close()
    data = path.read_bytes()
    assert data[18:20] == b"\x02\x02"
    assert rollback_journal(data)[18:20] == b"\x01\x01"
    assert run(data, "SELECT x FROM t").rows == [(7,)]


def test_a_view_in_the_database_is_read_through_the_authorizer():
    with_view = image("CREATE TABLE t (x); INSERT INTO t VALUES (1), (2); CREATE VIEW big AS SELECT x FROM t WHERE x > 1;")
    assert run(with_view, "SELECT * FROM big").rows == [(2,)]


# Features


@pytest.mark.parametrize(
    "query, expected",
    [
        ("SELECT name FROM singer", {"selecting"}),
        ("SELECT count(*) FROM head WHERE age > 56", {"selecting", "aggregates", "filtering"}),
        ("SELECT DISTINCT country FROM singer ORDER BY country LIMIT 3", {"selecting", "distinct", "sorting", "limiting"}),
        ("SELECT dept, avg(age) FROM e GROUP BY dept HAVING count(*) > 2",
         {"selecting", "aggregates", "grouping", "having"}),
        ("SELECT T1.name FROM a AS T1 JOIN b AS T2 ON T1.id = T2.a_id", {"selecting", "joins"}),
        ("SELECT name FROM a WHERE id IN (SELECT a_id FROM b)", {"selecting", "filtering", "subqueries"}),
        ("SELECT name FROM a UNION SELECT name FROM b", {"selecting", "set operations"}),
        ("SELECT name FROM a INTERSECT SELECT name FROM b", {"selecting", "set operations"}),
        ("SELECT name FROM a WHERE name LIKE '%x%'", {"selecting", "filtering", "patterns"}),
        ("SELECT 'where order by' FROM a -- GROUP BY", {"selecting"}),
        ("SELECT max_age, counter FROM a", {"selecting"}),
    ],
)
def test_features_are_read_from_the_query(query, expected):
    assert features(query) == expected


def test_values_round_trip_through_the_built_tables():
    assert rows("SELECT * FROM employees WHERE id IN (3, 4) ORDER BY id") == [(3, "Linus", 2, None), (4, "Ada", None, 80.0)]
    assert rows("SELECT typeof(salary) FROM employees WHERE id = 2") == [("real",)]


def test_each_run_starts_from_a_fresh_copy():
    assert sqlite3.sqlite_version_info >= (3, 39)
    assert rows("SELECT count(*) FROM depts") == [(3,)]
