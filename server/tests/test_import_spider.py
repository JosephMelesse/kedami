"""Importing the Spider exercise bank. See architecture/sql-lessons.md, Exercise bank."""

import json
import sqlite3

import pytest

from kedami_server import import_spider
from kedami_server.import_spider import import_bank
from kedami_server.queries import run


def make_db(path, script):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(script)
    conn.close()


@pytest.fixture
def spider(tmp_path):
    root = tmp_path / "spider_data"
    make_db(root / "database" / "music" / "music.sqlite",
            "CREATE TABLE singer (id INTEGER, name TEXT, age INTEGER);"
            "INSERT INTO singer VALUES (1, 'Ana', 30), (2, 'Bo', 45), (3, 'Cy', 45);")
    make_db(root / "test_database" / "zoo" / "zoo.sqlite",
            "CREATE TABLE animal (name TEXT, legs INTEGER); INSERT INTO animal VALUES ('cat', 4), ('bird', 2);")
    q = lambda db, query, question="A question?": {"db_id": db, "query": query, "question": question}
    (root / "train_spider.json").write_text(json.dumps([
        q("music", "SELECT name FROM singer ORDER BY age DESC", "Names  by age,\n oldest first?"),
        q("music", "select name from singer order by age desc;", "Paraphrase of the first?"),
        q("music", "SELECT count(*) FROM singer WHERE age > 40"),
        q("music", "SELECT name FROM singer WHERE age > 99"),
        q("music", "SELECT nope FROM singer"),
        q("music", "DELETE FROM singer"),
        q("missing_db", "SELECT 1"),
        {"db_id": "music", "query": "SELECT 1"},
    ]))
    (root / "dev.json").write_text(json.dumps([q("music", "SELECT DISTINCT age FROM singer")]))
    (root / "test.json").write_text(json.dumps([q("zoo", "SELECT name FROM animal WHERE legs = 4")]))
    (root / "train_others.json").write_text(json.dumps([q("music", "SELECT id FROM singer")]))
    return root


def read_bank(data_dir):
    return [json.loads(line) for line in (data_dir / "sql" / "exercises.jsonl").read_text().splitlines()]


def test_the_import_keeps_runnable_distinct_exercises_and_says_why_it_dropped_the_rest(tmp_path, spider):
    data = tmp_path / "data"
    data.mkdir()
    summary = import_bank(data, spider)
    assert (summary.kept, summary.databases) == (4, 2)
    assert dict(summary.dropped) == {
        "it repeats another question's query": 1,
        "its query returns no rows": 1,
        "its query doesn't run here": 2,
        "its database is missing": 1,
        "it isn't a complete exercise": 1,
    }
    bank = read_bank(data)
    assert sorted(e["query"] for e in bank) == [
        "SELECT DISTINCT age FROM singer",
        "SELECT count(*) FROM singer WHERE age > 40",
        "SELECT name FROM animal WHERE legs = 4",
        "SELECT name FROM singer ORDER BY age DESC",
    ]
    first = next(e for e in bank if e["query"].endswith("DESC"))
    assert first["question"] == "Names by age, oldest first?"
    assert first["ordered"] is True and first["features"] == ["selecting", "sorting"]
    assert first["id"].startswith("music-") and len(first["id"]) == len("music-") + 10
    assert sorted(p.name for p in (data / "sql" / "databases").iterdir()) == ["music.sqlite", "zoo.sqlite"]


def test_an_imported_database_answers_its_exercises(tmp_path, spider):
    import_bank(tmp_path, spider)
    image = (tmp_path / "sql" / "databases" / "music.sqlite").read_bytes()
    assert run(image, "SELECT count(*) FROM singer").rows == [(3,)]


def test_train_others_is_left_out(tmp_path, spider):
    import_bank(tmp_path, spider)
    assert all(e["query"] != "SELECT id FROM singer" for e in read_bank(tmp_path))


def test_ids_stay_the_same_across_imports(tmp_path, spider):
    import_bank(tmp_path, spider)
    first = [e["id"] for e in read_bank(tmp_path)]
    import_bank(tmp_path, spider)
    assert [e["id"] for e in read_bank(tmp_path)] == first


def test_a_large_database_is_left_out(tmp_path, spider, monkeypatch):
    monkeypatch.setattr(import_spider, "MAX_DATABASE", 100)
    summary = import_bank(tmp_path, spider)
    assert summary.kept == 0
    assert summary.dropped["its database is over 0 MB"] == 8


def test_a_query_returning_too_many_rows_is_left_out(tmp_path, spider, monkeypatch):
    monkeypatch.setattr(import_spider, "MAX_ROWS", 2)
    summary = import_bank(tmp_path, spider)
    assert summary.dropped["its query returns over 2 rows"] == 2


def test_a_new_import_replaces_the_old_one_whole(tmp_path, spider):
    import_bank(tmp_path, spider)
    (tmp_path / "sql" / "databases" / "stale.sqlite").write_bytes(b"x")
    (spider / "test.json").write_text("[]")
    import_bank(tmp_path, spider)
    assert sorted(p.name for p in (tmp_path / "sql" / "databases").iterdir()) == ["music.sqlite"]
    assert not (tmp_path / "sql.partial").exists() and not (tmp_path / "sql.old").exists()
