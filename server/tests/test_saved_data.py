"""Lessons, stage outputs, and databases saved while LeetCode and SQL lessons existed."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from kedami_server import db
from kedami_server.app import create_app
from kedami_server.config import Settings
from kedami_server.generation import pipeline
from kedami_server.generation.schemas import Extraction, Plan
from kedami_server.lesson import Lesson
from kedami_server.library import add_ready_lesson, get_lesson_row, list_lessons
from kedami_server.storage import lessons_dir, load_lesson

AUTH = {"Authorization": "Bearer t"}
EXTERNAL = {"kind": "external", "platform": "leetcode", "number": 1, "title": "Two Sum", "slug": "two-sum"}


@pytest.fixture
def data_dir(tmp_path):
    db.init(tmp_path)
    return tmp_path


@pytest.fixture
def client(data_dir):
    return TestClient(create_app(Settings(0, "t", data_dir, ())))


def save(data_dir, lesson_id, data):
    """Index a lesson directly, as an older version of the app would have left it."""
    folder = lessons_dir(data_dir)
    folder.mkdir(exist_ok=True)
    (folder / f"{lesson_id}.json").write_text(json.dumps({**data, "id": lesson_id}))
    with db.connect(data_dir) as conn:
        conn.execute(
            "INSERT INTO lessons (id, title, subject, status, schema_version, created)"
            " VALUES (?, ?, ?, 'ready', 1, '2026-10-01')",
            (lesson_id, data["title"], data["subject"]),
        )


def first_problem(lesson_data):
    return next(b for s in lesson_data["sections"] for b in s["blocks"] if b["type"] == "problem")


def removed_subject(lesson_data):
    """A computer science lesson whose one problem was solved on LeetCode."""
    lesson_data["subject"] = "computer_science"
    lesson_data["domain"] = "dsa"
    first_problem(lesson_data)["parts"][0]["answer"] = EXTERNAL
    return lesson_data


def test_a_lesson_saved_with_the_empty_removed_fields_still_loads(lesson_data):
    lesson = Lesson.model_validate({**lesson_data, "domain": None, "credits": []})
    assert "domain" not in lesson.model_dump() and "credits" not in lesson.model_dump()


def test_new_lessons_cant_use_the_removed_subject(lesson_data):
    with pytest.raises(ValueError):
        Lesson.model_validate({**lesson_data, "subject": "computer_science"})


@pytest.mark.parametrize("answer", [
    EXTERNAL,
    {"kind": "query", "database": "course/people", "reference": "SELECT 1"},
    {"kind": "code", "platform": "leetcode", "number": 1, "title": "Two Sum", "slug": "two-sum", "difficulty": "Easy",
     "method": "twoSum", "starter_code": "class Solution: pass", "tests": [{"args": "", "expected": "1", "compare": "equal"}]},
])
def test_the_removed_answer_kinds_are_refused(lesson_data, answer):
    first_problem(lesson_data)["parts"][0]["answer"] = answer
    with pytest.raises(ValueError):
        Lesson.model_validate(lesson_data)


def test_an_unreadable_lesson_doesnt_break_the_library(client, data_dir, lesson_data):
    good = json.loads(json.dumps(lesson_data))
    save(data_dir, "good", good)
    save(data_dir, "old", removed_subject(lesson_data))

    assert load_lesson(data_dir, "old") is None
    listed = {lesson["id"]: lesson for lesson in client.get("/lessons", headers=AUTH).json()["lessons"]}
    assert listed["good"]["problems_total"] == 2
    assert listed["old"]["problems_total"] == 0


def test_an_unreadable_lesson_cant_be_opened_but_can_be_deleted(client, data_dir, lesson_data):
    save(data_dir, "old", removed_subject(lesson_data))

    assert client.get("/lessons/old", headers=AUTH).status_code == 404
    assert client.delete("/lessons/old", headers=AUTH).status_code == 200
    assert client.get("/lessons", headers=AUTH).json()["lessons"] == []
    assert not (lessons_dir(data_dir) / "old.json").exists()


def test_a_corrupt_lesson_file_counts_as_unreadable(data_dir):
    lessons_dir(data_dir).mkdir()
    (lessons_dir(data_dir) / "broken.json").write_text("{not json")
    assert load_lesson(data_dir, "broken") is None


def test_a_database_with_the_old_columns_and_table_still_works(tmp_path, lesson_data):
    # Its status check names placeholders, so it has been through that migration and keeps the old columns.
    conn = sqlite3.connect(tmp_path / "kedami.db")
    conn.executescript(
        """
        CREATE TABLE lessons (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, custom_title TEXT, subject TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('placeholder', 'generating', 'ready', 'failed')),
            current_stage INTEGER, schema_version INTEGER NOT NULL,
            revision INTEGER NOT NULL DEFAULT 1, created TEXT NOT NULL, error TEXT, domain TEXT, chapter INTEGER,
            due_date TEXT
        );
        INSERT INTO lessons (id, title, subject, status, schema_version, created, domain, chapter)
        VALUES ('old', 'Old', 'computer_science', 'ready', 1, '2026-10-01', 'sql', 3);
        CREATE TABLE test_flags (lesson_id TEXT NOT NULL REFERENCES lessons (id) ON DELETE CASCADE, block_id TEXT);
        INSERT INTO test_flags VALUES ('old', 'b');
        """
    )
    conn.close()
    db.init(tmp_path)

    with db.connect(tmp_path) as conn:
        assert {row[1] for row in conn.execute("PRAGMA table_info(lessons)")} >= {"domain", "chapter"}
        assert [row.id for row in list_lessons(conn)] == ["old"]
        assert get_lesson_row(conn, "old").title == "Old"
        add_ready_lesson(conn, Lesson.model_validate(lesson_data))
        assert {row.id for row in list_lessons(conn)} == {"old", "sample"}
        # Deleting a lesson still reaches the old table's rows.
        conn.execute("DELETE FROM lessons WHERE id = 'old'")
        assert conn.execute("SELECT COUNT(*) FROM test_flags").fetchone()[0] == 0


def extraction(**extra):
    part = {"label": "(a)", "prompt": "Find x.", "options": None}
    problem = {"source_ref": "PS1 #1", "prompt": "", "parts": [part], "concepts": []}
    return {"concepts": [], "problems": [problem], **extra}


@pytest.mark.parametrize("saved", [{}, {"answers": {}}, {"externals": {}}])
def test_an_extraction_with_no_listed_answers_still_loads(saved):
    assert len(Extraction.model_validate(extraction(**saved)).problems) == 1


def test_an_extraction_with_listed_answers_doesnt_load():
    with pytest.raises(ValueError):
        Extraction.model_validate(extraction(answers={"ps1-1": EXTERNAL}))


def test_a_plan_with_no_sql_features_still_loads():
    section = {"title": "A", "goal": "B", "concepts": [], "simulation": None, "sql_features": []}
    assert len(Plan.model_validate({"title": "T", "sections": [section]}).sections) == 1


def test_a_plan_with_sql_features_doesnt_load():
    section = {"title": "A", "goal": "B", "concepts": [], "simulation": None, "sql_features": ["joins"]}
    with pytest.raises(ValueError):
        Plan.model_validate({"title": "T", "sections": [section]})


def test_a_lesson_with_older_stage_outputs_can_still_be_rerun_from_any_stage(data_dir):
    work = pipeline.work_dir(data_dir, "old")
    (work / pipeline.NORMALIZED).mkdir(parents=True)
    (work / pipeline.NORMALIZED / pipeline.PROBLEM_SET_FILE).write_text("PS1")
    (work / "extraction.json").write_text(json.dumps(extraction(answers={})))
    section = {"title": "A", "goal": "B", "concepts": [], "simulation": None, "sql_features": []}
    (work / "plan.json").write_text(json.dumps({"title": "T", "sections": [section]}))

    assert pipeline.available_stages(data_dir, "old", True) == [1, 2, 3, 4]
