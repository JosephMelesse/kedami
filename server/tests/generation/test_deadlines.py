"""Due dates and the overdue rule, at its boundaries. See Deadlines in ui.md."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from kedami_server import db, library
from kedami_server.app import create_app
from kedami_server.config import Settings
from kedami_server.deadlines import is_overdue, parse_due_date, soonest_by_folder
from kedami_server.lesson import Lesson, ProblemBlock
from kedami_server.progress import Record, save
from kedami_server.storage import seed_sample

from .conftest import AUTH
from .test_pipeline import FakeModel, happy_script, run

TODAY = "2026-11-10"


@pytest.fixture
def clock():
    return {"today": TODAY}


@pytest.fixture
def client(data_dir, clock):
    return TestClient(
        create_app(Settings(0, "t", data_dir, ()), start_generation=lambda *args: None, today=lambda: clock["today"])
    )


def create(client, folder=None):
    response = client.post(
        "/lessons",
        data={"subject": "physics", "roles": ["problem_set", "reference"], "force": ["false", "false"]}
        | ({"folder": str(folder)} if folder else {}),
        files=[("files", ("problem-set.md", b"PS1\n1. A ball...", "text/markdown")),
               ("files", ("reference.md", b"Notes on projectiles.", "text/markdown"))],
        headers=AUTH,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def ready_lesson(client, data_dir, folder=None):
    lesson_id = create(client, folder)
    run(data_dir, lesson_id, FakeModel(happy_script()))
    return lesson_id


def finish(data_dir, lesson_id):
    lesson = Lesson.model_validate_json((data_dir / "lessons" / f"{lesson_id}.json").read_text())
    with db.connect(data_dir) as conn:
        for section in lesson.sections:
            for block in section.blocks:
                if isinstance(block, ProblemBlock):
                    for part in block.parts:
                        save(conn, lesson_id, Record(block_id=block.id, part_id=part.id, status="marked_done"))


def set_due(client, lesson_id, due):
    return client.post(f"/lessons/{lesson_id}/due-date", json={"due_date": due}, headers=AUTH)


def summary(client, lesson_id):
    return {s["id"]: s for s in client.get("/lessons", headers=AUTH).json()["lessons"]}[lesson_id]


def folder_of(client, folder):
    return {f["id"]: f for f in client.get("/folders", headers=AUTH).json()["folders"]}[folder]


def new_folder(client, name, parent=None):
    return client.post("/folders", json={"name": name, "parent_id": parent}, headers=AUTH).json()["id"]


# Reading a date


@pytest.mark.parametrize("text", ["2026-11-01", "2028-02-29", "0001-01-01", "9999-12-31"])
def test_real_dates_are_kept_as_written(text):
    assert parse_due_date(text) == text


@pytest.mark.parametrize("text", [
    "20261101", "2026-W44-7", "2026-305",  # `date.fromisoformat` accepts forms of the first two
    "2026-02-30", "2027-02-29", "2026-13-01", "2026-00-10", "2026-11-00",
    "2026-11-1", "26-11-01", "11/01/2026", " 2026-11-01", "2026-11-01 ", "2026-11-01\n",
    "2026-11-01T00:00:00", "٢٠٢٦-١١-٠١", "",
])
def test_anything_else_is_refused(text):
    with pytest.raises(ValueError):
        parse_due_date(text)


@pytest.mark.parametrize("body", [
    {"due_date": "20261101"}, {"due_date": "2026-02-30"}, {"due_date": 20261101}, {"due_date": ""}, {},
    {"due_date": None, "extra": 1},
])
def test_the_route_refuses_a_bad_date_and_changes_nothing(client, data_dir, body):
    lesson_id = create(client)
    set_due(client, lesson_id, "2026-12-01")
    assert client.post(f"/lessons/{lesson_id}/due-date", json=body, headers=AUTH).status_code == 422
    assert summary(client, lesson_id)["due_date"] == "2026-12-01"


def test_a_due_date_on_an_unknown_lesson(client):
    assert set_due(client, "missing", "2026-12-01").status_code == 404


# The rule


@pytest.mark.parametrize("due, on, overdue", [
    ("2026-11-10", "2026-11-10", False),  # the date itself isn't overdue yet
    ("2026-11-09", "2026-11-10", True),  # the day after is
    ("2026-11-11", "2026-11-10", False),
    ("2026-12-31", "2027-01-01", True),  # across a year
    ("2027-01-01", "2026-12-31", False),
    ("2026-09-30", "2026-10-01", True),  # across a month, where comparing as numbers without padding would fail
    ("2028-02-29", "2028-03-01", True),  # a leap day
    (None, "2026-11-10", False),
])
def test_overdue_at_its_boundaries(due, on, overdue):
    assert is_overdue(due, False, on) is overdue


def test_a_done_lesson_is_never_overdue():
    assert is_overdue("2020-01-01", True, "2026-11-10") is False


def test_midnight_changes_the_answer_without_any_write(client, data_dir, clock):
    lesson_id = ready_lesson(client, data_dir)
    set_due(client, lesson_id, "2026-11-10")
    assert summary(client, lesson_id)["overdue"] is False
    clock["today"] = "2026-11-11"
    assert summary(client, lesson_id)["overdue"] is True


# On lessons of every status


def test_set_change_and_clear(client, data_dir):
    lesson_id = ready_lesson(client, data_dir)
    assert summary(client, lesson_id)["due_date"] is None
    assert set_due(client, lesson_id, "2026-12-01").json() == {"id": lesson_id, "due_date": "2026-12-01"}
    set_due(client, lesson_id, "2026-12-02")
    assert summary(client, lesson_id)["due_date"] == "2026-12-02"
    set_due(client, lesson_id, None)
    assert summary(client, lesson_id)["due_date"] is None
    assert summary(client, lesson_id)["overdue"] is False


def test_a_past_date_is_allowed_and_overdue_at_once(client, data_dir):
    lesson_id = ready_lesson(client, data_dir)
    assert set_due(client, lesson_id, "2020-01-01").status_code == 200
    assert summary(client, lesson_id)["overdue"] is True


def test_finishing_a_lesson_clears_overdue_and_undoing_brings_it_back(client, data_dir):
    lesson_id = ready_lesson(client, data_dir)
    set_due(client, lesson_id, "2026-01-01")
    finish(data_dir, lesson_id)
    assert (summary(client, lesson_id)["done"], summary(client, lesson_id)["overdue"]) == (True, False)
    with db.connect(data_dir) as conn:
        conn.execute("DELETE FROM progress WHERE lesson_id = ?", (lesson_id,))
    assert (summary(client, lesson_id)["done"], summary(client, lesson_id)["overdue"]) == (False, True)


def test_a_done_lesson_is_not_overdue_while_it_reruns(client, data_dir):
    # A summary reports no problems while a lesson generates, so `done` can't come from those counts.
    lesson_id = ready_lesson(client, data_dir)
    set_due(client, lesson_id, "2026-01-01")
    finish(data_dir, lesson_id)
    with db.connect(data_dir) as conn:
        library.start_run(conn, lesson_id)
    during = summary(client, lesson_id)
    assert (during["status"], during["done"], during["overdue"]) == ("generating", True, False)


def test_an_unfinished_lesson_is_overdue_while_it_reruns(client, data_dir):
    lesson_id = ready_lesson(client, data_dir)
    set_due(client, lesson_id, "2026-01-01")
    with db.connect(data_dir) as conn:
        library.start_run(conn, lesson_id)
    assert summary(client, lesson_id)["overdue"] is True


def test_a_new_lesson_is_not_done_while_generating_or_after_failing(client, data_dir):
    lesson_id = create(client)
    set_due(client, lesson_id, "2026-01-01")
    assert (summary(client, lesson_id)["done"], summary(client, lesson_id)["overdue"]) == (False, True)
    with db.connect(data_dir) as conn:
        library.set_failed(conn, lesson_id, "boom")
    failed = summary(client, lesson_id)
    assert (failed["status"], failed["done"], failed["overdue"], failed["due_date"]) == (
        "failed", False, True, "2026-01-01")


def test_a_lesson_with_no_problems_counts_as_done(client, data_dir):
    seed_sample(data_dir)
    path = data_dir / "lessons" / "sample.json"
    lesson = json.loads(path.read_text())
    for section in lesson["sections"]:
        section["blocks"] = [b for b in section["blocks"] if b["type"] != "problem"]
    path.write_text(json.dumps(lesson))
    set_due(client, "sample", "2026-01-01")
    assert (summary(client, "sample")["done"], summary(client, "sample")["overdue"]) == (True, False)


# Keeping it


def test_a_rerun_keeps_the_deadline(client, data_dir):
    lesson_id = ready_lesson(client, data_dir)
    set_due(client, lesson_id, "2026-12-01")
    run(data_dir, lesson_id, FakeModel(happy_script()), start_stage=3)
    assert summary(client, lesson_id)["due_date"] == "2026-12-01"


def test_a_failed_rerun_keeps_the_deadline(client, data_dir):
    lesson_id = ready_lesson(client, data_dir)
    set_due(client, lesson_id, "2026-12-01")
    run(data_dir, lesson_id, FakeModel({}), start_stage=3)
    after = summary(client, lesson_id)
    assert after["error"] and after["due_date"] == "2026-12-01"


def test_a_move_keeps_the_deadline(client, data_dir):
    lesson_id = ready_lesson(client, data_dir)
    set_due(client, lesson_id, "2026-12-01")
    folder = new_folder(client, "Week 1")
    client.post(f"/lessons/{lesson_id}/move", json={"folder_id": folder}, headers=AUTH)
    assert summary(client, lesson_id)["due_date"] == "2026-12-01"


def test_deleting_the_lesson_removes_it(client, data_dir):
    lesson_id = ready_lesson(client, data_dir)
    folder = new_folder(client, "Week 1")
    client.post(f"/lessons/{lesson_id}/move", json={"folder_id": folder}, headers=AUTH)
    set_due(client, lesson_id, "2026-12-01")
    client.delete(f"/lessons/{lesson_id}", headers=AUTH)
    with db.connect(data_dir) as conn:
        assert conn.execute("SELECT COUNT(*) FROM lessons WHERE id = ?", (lesson_id,)).fetchone()[0] == 0
    assert folder_of(client, folder)["next_due"] is None


def test_an_older_database_gains_the_column_with_no_dates(tmp_path):
    conn = sqlite3.connect(tmp_path / "kedami.db")
    conn.execute(
        "CREATE TABLE lessons (id TEXT PRIMARY KEY, title TEXT NOT NULL, subject TEXT NOT NULL, status TEXT NOT NULL,"
        " current_stage INTEGER, schema_version INTEGER NOT NULL, revision INTEGER NOT NULL DEFAULT 1,"
        " created TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO lessons VALUES ('old', 'Old', 'math', 'ready', NULL, 1, 1, '2026-01-01')")
    conn.commit()
    conn.close()
    db.init(tmp_path)
    with db.connect(tmp_path) as conn:
        assert library.get_lesson_row(conn, "old").due_date is None


# Folder tiles


def test_soonest_by_folder_counts_subfolders():
    parents = {1: None, 2: 1, 3: 2, 4: None}
    soonest = soonest_by_folder(parents, [(3, "2026-12-05"), (2, "2026-12-09"), (1, "2026-12-07"), (4, "2026-12-01")])
    assert soonest == {3: "2026-12-05", 2: "2026-12-05", 1: "2026-12-05", 4: "2026-12-01"}


def test_a_folder_shows_the_soonest_unfinished_date_inside_it(client, data_dir):
    top = new_folder(client, "Top")
    inner = new_folder(client, "Inner", top)
    other = new_folder(client, "Other")
    soon, later, finished = (ready_lesson(client, data_dir, f) for f in (inner, top, top))
    set_due(client, soon, "2026-12-05")
    set_due(client, later, "2026-12-20")
    set_due(client, finished, "2026-11-20")
    finish(data_dir, finished)
    assert folder_of(client, top)["next_due"] == "2026-12-05"
    assert folder_of(client, inner)["next_due"] == "2026-12-05"
    assert folder_of(client, other)["next_due"] is None
    assert folder_of(client, top)["next_due_overdue"] is False


def test_a_folder_is_overdue_when_its_soonest_date_has_passed(client, data_dir, clock):
    top = new_folder(client, "Top")
    lesson_id = ready_lesson(client, data_dir, top)
    set_due(client, lesson_id, "2026-11-10")
    assert folder_of(client, top)["next_due_overdue"] is False
    clock["today"] = "2026-11-11"
    assert folder_of(client, top)["next_due_overdue"] is True
    finish(data_dir, lesson_id)
    assert (folder_of(client, top)["next_due"], folder_of(client, top)["next_due_overdue"]) == (None, False)
