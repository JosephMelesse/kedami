"""Placeholders: planned lessons that Upload fills in. See architecture/ui.md and pipeline.md."""

import pytest
from fastapi.testclient import TestClient

from kedami_server import db, library
from kedami_server.app import create_app
from kedami_server.config import Settings

from .conftest import AUTH
from .test_pipeline import FakeModel, happy_script, run

TODAY = "2026-11-10"
FILES = [("problem-set.md", b"PS1\n1. A ball...", "problem_set"), ("reference.md", b"Notes on projectiles.", "reference")]


@pytest.fixture
def runs():
    return []


@pytest.fixture
def client(data_dir, runs):
    return TestClient(
        create_app(Settings(0, "t", data_dir, ()), start_generation=lambda *args: runs.append(args), today=lambda: TODAY)
    )


def plan(client, name="Week 1", due=None, folder=None):
    response = client.post(
        "/placeholders",
        json={"folder_id": folder, "placeholders": [{"name": name, "due_date": due}]},
        headers=AUTH,
    )
    assert response.status_code == 201, response.text
    return response.json()["ids"][0]


def fill(client, lesson_id, files=FILES, subject="physics", extra=None):
    return client.post(
        f"/lessons/{lesson_id}/fill",
        data={"subject": subject, "roles": [f[2] for f in files], "force": ["false" for _ in files]} | (extra or {}),
        files=[("files", (f[0], f[1], "text/markdown")) for f in files],
        headers=AUTH,
    )


def summary(client, lesson_id):
    return {s["id"]: s for s in client.get("/lessons", headers=AUTH).json()["lessons"]}[lesson_id]


def new_folder(client, name="Physics"):
    return client.post("/folders", json={"name": name}, headers=AUTH).json()["id"]


def leftovers(data_dir):
    materials = data_dir / "materials"
    return sorted(path.name for path in materials.iterdir()) if materials.exists() else []


# Creating


def test_a_placeholder_is_listed_with_nothing_generated(client, data_dir, runs):
    folder = new_folder(client)
    lesson_id = plan(client, "Week 1", "2026-12-01", folder)
    listed = summary(client, lesson_id)
    assert listed["title"] == "Week 1"
    assert listed["status"] == "placeholder"
    assert listed["subject"] is None
    assert (listed["problems_total"], listed["problems_done"]) == (0, 0)
    assert (listed["folder_id"], listed["due_date"]) == (folder, "2026-12-01")
    assert (listed["active"], listed["done"], listed["overdue"]) == (False, False, False)
    assert runs == []
    assert not (data_dir / "lessons" / f"{lesson_id}.json").exists()
    assert not (data_dir / "materials" / lesson_id).exists()


def test_several_are_created_in_order(client):
    names = [f"Week {n}" for n in range(60)]
    response = client.post(
        "/placeholders", json={"placeholders": [{"name": n} for n in names]}, headers=AUTH
    )
    assert response.status_code == 201
    listed = [s["title"] for s in client.get("/lessons", headers=AUTH).json()["lessons"]]
    assert listed == names


@pytest.mark.parametrize("body, status", [
    ({"placeholders": []}, 422),
    ({}, 422),
    ({"placeholders": [{"name": ""}]}, 422),
    ({"placeholders": [{"name": "   "}]}, 422),
    ({"placeholders": [{"name": "x" * 121}]}, 422),
    ({"placeholders": [{"name": "Ok", "due_date": "2026-02-30"}]}, 422),
    ({"placeholders": [{"name": "Ok", "due_date": "20261201"}]}, 422),
    ({"placeholders": [{"name": "Ok", "extra": 1}]}, 422),
    ({"placeholders": [{"name": f"L{n}"} for n in range(101)]}, 422),
    ({"folder_id": 999, "placeholders": [{"name": "Ok"}]}, 404),
    ({"folder_id": "1", "placeholders": [{"name": "Ok"}]}, 422),
])
def test_bad_requests_create_nothing(client, body, status):
    assert client.post("/placeholders", json=body, headers=AUTH).status_code == status
    assert client.get("/lessons", headers=AUTH).json()["lessons"] == []


def test_one_bad_entry_creates_none(client):
    body = {"placeholders": [{"name": "Good"}, {"name": "Bad", "due_date": "nope"}]}
    assert client.post("/placeholders", json=body, headers=AUTH).status_code == 422
    assert client.get("/lessons", headers=AUTH).json()["lessons"] == []


def test_the_parse_route_saves_nothing(client):
    reply = client.post("/placeholders/parse", json={"text": "A\nB | 2026-12-01"}, headers=AUTH).json()
    assert reply == {"placeholders": [{"name": "A", "due_date": None}, {"name": "B", "due_date": "2026-12-01"}],
                     "problems": []}
    bad = client.post("/placeholders/parse", json={"text": "A\nB | C | D"}, headers=AUTH).json()
    assert bad["placeholders"] == []
    assert bad["problems"][0]["line"] == 2
    assert client.get("/lessons", headers=AUTH).json()["lessons"] == []


def test_the_parse_route_refuses_a_huge_paste(client):
    assert client.post("/placeholders/parse", json={"text": "x" * 100_001}, headers=AUTH).status_code == 422


# Treated like any lesson


def test_it_can_be_renamed_moved_dated_and_deleted(client):
    folder = new_folder(client)
    lesson_id = plan(client)
    assert client.post(f"/lessons/{lesson_id}/rename", json={"title": "Exam"}, headers=AUTH).status_code == 200
    assert client.post(f"/lessons/{lesson_id}/move", json={"folder_id": folder}, headers=AUTH).status_code == 200
    assert client.post(f"/lessons/{lesson_id}/due-date", json={"due_date": "2026-12-01"}, headers=AUTH).status_code == 200
    listed = summary(client, lesson_id)
    assert (listed["title"], listed["folder_id"], listed["due_date"]) == ("Exam", folder, "2026-12-01")
    assert client.delete(f"/lessons/{lesson_id}", headers=AUTH).json() == {"deleted": lesson_id}
    assert client.get("/lessons", headers=AUTH).json()["lessons"] == []


def test_it_counts_toward_its_folder_and_its_folder_due_date(client):
    folder = new_folder(client)
    plan(client, due="2026-11-01", folder=folder)
    listed = client.get("/folders", headers=AUTH).json()["folders"][0]
    assert (listed["lessons"], listed["next_due"], listed["next_due_overdue"]) == (1, "2026-11-01", True)


def test_it_is_never_done_and_shows_as_overdue_once_its_date_passes(client):
    on_time, due_today, late = plan(client, due="2026-11-11"), plan(client, due=TODAY), plan(client, due="2026-11-09")
    assert [summary(client, i)["overdue"] for i in (on_time, due_today, late)] == [False, False, True]
    assert summary(client, late)["done"] is False


def test_it_has_no_active_checkbox_or_lesson_to_serve(client):
    lesson_id = plan(client)
    assert client.post(f"/lessons/{lesson_id}/active", json={"active": True}, headers=AUTH).status_code == 404
    assert client.get(f"/lessons/{lesson_id}/progress", headers=AUTH).status_code == 404
    served = client.get(f"/lessons/{lesson_id}", headers=AUTH).json()
    assert (served["lesson"], served["status"], served["materials"], served["rerun_stages"]) == (
        None, "placeholder", [], [])


def test_it_cannot_be_rerun(client, runs):
    lesson_id = plan(client)
    assert client.post(f"/lessons/{lesson_id}/rerun", json={"stage": 1}, headers=AUTH).status_code == 409
    assert runs == []
    assert summary(client, lesson_id)["status"] == "placeholder"


def test_a_restart_leaves_it_alone(client, data_dir):
    lesson_id = plan(client, due="2026-12-01")
    with db.connect(data_dir) as conn:
        library.fail_interrupted(conn, lambda _: False)
    listed = summary(client, lesson_id)
    assert (listed["status"], listed["error"], listed["due_date"]) == ("placeholder", None, "2026-12-01")


def test_deleting_its_folder_moves_it_up_with_its_deadline(client):
    folder = new_folder(client)
    lesson_id = plan(client, due="2026-12-01", folder=folder)
    client.delete(f"/folders/{folder}", headers=AUTH)
    listed = summary(client, lesson_id)
    assert (listed["folder_id"], listed["status"], listed["due_date"]) == (None, "placeholder", "2026-12-01")


# Filling in


def test_filling_keeps_its_id_name_folder_and_deadline_and_starts_generating(client, data_dir, runs):
    folder = new_folder(client)
    lesson_id = plan(client, "Exam review", "2026-12-01", folder)
    assert fill(client, lesson_id).json() == {"id": lesson_id}
    assert runs == [(data_dir, lesson_id, "physics", 1)]
    listed = summary(client, lesson_id)
    assert (listed["status"], listed["subject"], listed["title"], listed["folder_id"], listed["due_date"]) == (
        "generating", "physics", "Exam review", folder, "2026-12-01")
    assert len(client.get("/lessons", headers=AUTH).json()["lessons"]) == 1
    assert sorted(p.name for p in (data_dir / "materials" / lesson_id).iterdir()) == ["problem-set.md", "reference.md"]
    assert leftovers(data_dir) == [lesson_id]
    with db.connect(data_dir) as conn:
        assert [(m.filename, m.role) for m in library.list_materials(conn, lesson_id)] == [
            ("problem-set.md", "problem_set"), ("reference.md", "reference")]


def test_generation_does_not_overwrite_the_name(client, data_dir):
    lesson_id = plan(client, "Exam review", "2026-12-01")
    fill(client, lesson_id)
    run(data_dir, lesson_id, FakeModel(happy_script()))
    listed = summary(client, lesson_id)
    assert (listed["status"], listed["title"], listed["due_date"]) == ("ready", "Exam review", "2026-12-01")
    assert listed["problems_total"] > 0
    assert client.get(f"/lessons/{lesson_id}", headers=AUTH).json()["lesson"]["title"] == "Exam review"
    assert client.post(f"/lessons/{lesson_id}/active", json={"active": True}, headers=AUTH).status_code == 200


def test_a_renamed_placeholder_fills_under_the_new_name(client, data_dir):
    lesson_id = plan(client, "Old name")
    client.post(f"/lessons/{lesson_id}/rename", json={"title": "New name"}, headers=AUTH)
    fill(client, lesson_id)
    run(data_dir, lesson_id, FakeModel(happy_script()))
    assert summary(client, lesson_id)["title"] == "New name"


@pytest.mark.parametrize("files, subject, extra", [
    ([("reference.md", b"Notes only.", "reference")], "physics", None),  # no problem set
    ([("ps.exe", b"MZ", "problem_set")], "physics", None),  # unsupported type
    ([("ps.md", b"PS1", "problem_set")], "not-a-subject", None),
    ([("ps.md", b"PS1", "problem_set")], "computer_science", None),  # needs a domain
    ([("ps.md", b"PS1", "problem_set")], "physics", {"domain": "dsa"}),  # only computer science has one
    ([("db.sql", b"CREATE TABLE t (x);", "database"), ("ps.md", b"PS1", "problem_set")], "physics", None),
])
def test_a_refused_upload_leaves_it_unchanged(client, data_dir, runs, files, subject, extra):
    folder = new_folder(client)
    lesson_id = plan(client, "Week 1", "2026-12-01", folder)
    before = summary(client, lesson_id)
    assert fill(client, lesson_id, files, subject, extra).status_code == 422
    assert summary(client, lesson_id) == before
    assert runs == []
    assert leftovers(data_dir) == []
    with db.connect(data_dir) as conn:
        assert library.list_materials(conn, lesson_id) == []
    assert fill(client, lesson_id).status_code == 200  # It can still be filled in.


def test_an_error_while_saving_leaves_it_unchanged(client, data_dir, runs, monkeypatch):
    lesson_id = plan(client, due="2026-12-01")
    before = summary(client, lesson_id)

    def broken(*args):
        raise OSError("disk full")

    monkeypatch.setattr("kedami_server.app.add_material", broken)
    with pytest.raises(OSError):
        fill(client, lesson_id)
    assert summary(client, lesson_id) == before
    assert runs == []
    assert leftovers(data_dir) == []


def test_a_second_upload_is_refused_and_changes_nothing(client, data_dir, runs):
    lesson_id = plan(client)
    fill(client, lesson_id)
    second = fill(client, lesson_id, [("other.md", b"PS2\n1. Other", "problem_set")], "math")
    assert second.status_code == 409
    assert len(runs) == 1
    assert summary(client, lesson_id)["subject"] == "physics"
    assert sorted(p.name for p in (data_dir / "materials" / lesson_id).iterdir()) == ["problem-set.md", "reference.md"]
    assert leftovers(data_dir) == [lesson_id]


def test_an_upload_that_loses_a_race_leaves_nothing_behind(client, data_dir, runs, monkeypatch):
    # Something else took it after the first check: the claim at the end must refuse, and clean up after itself.
    lesson_id = plan(client)
    monkeypatch.setattr(library, "fill_placeholder", lambda *args, **kwargs: False)
    assert fill(client, lesson_id).status_code == 409
    assert runs == []
    assert leftovers(data_dir) == []
    assert summary(client, lesson_id)["status"] == "placeholder"


def test_filling_refuses_what_is_not_a_placeholder(client, data_dir):
    made = client.post(
        "/lessons",
        data={"subject": "math", "roles": ["problem_set"], "force": ["false"]},
        files=[("files", ("ps.md", b"PS1\n1. x", "text/markdown"))],
        headers=AUTH,
    ).json()["id"]
    assert fill(client, made).status_code == 409
    assert fill(client, "missing").status_code == 404


def test_a_deleted_placeholder_cannot_be_filled(client, data_dir):
    lesson_id = plan(client)
    client.delete(f"/lessons/{lesson_id}", headers=AUTH)
    assert fill(client, lesson_id).status_code == 404
    assert leftovers(data_dir) == []


# When generation fails


def test_a_failed_run_keeps_its_name_folder_and_deadline(client, data_dir):
    folder = new_folder(client)
    lesson_id = plan(client, "Exam review", "2026-11-01", folder)
    fill(client, lesson_id)
    run(data_dir, lesson_id, FakeModel({}))
    listed = summary(client, lesson_id)
    assert listed["status"] == "failed" and listed["error"]
    assert (listed["title"], listed["folder_id"], listed["due_date"]) == ("Exam review", folder, "2026-11-01")
    assert (listed["overdue"], listed["done"]) == (True, False)
    assert client.get("/folders", headers=AUTH).json()["folders"][0]["next_due"] == "2026-11-01"


def test_a_failed_lesson_can_be_rerun_but_not_filled_again(client, data_dir, runs):
    lesson_id = plan(client)
    fill(client, lesson_id)
    run(data_dir, lesson_id, FakeModel({}))
    assert fill(client, lesson_id).status_code == 409
    assert client.post(f"/lessons/{lesson_id}/rerun", json={"stage": 1}, headers=AUTH).status_code == 200
    assert len(runs) == 2


def test_an_interrupted_run_fails_like_any_new_lesson_and_keeps_its_deadline(client, data_dir):
    lesson_id = plan(client, "Exam review", "2026-12-01")
    fill(client, lesson_id)
    with db.connect(data_dir) as conn:
        library.fail_interrupted(conn, lambda _: False)
    listed = summary(client, lesson_id)
    assert (listed["status"], listed["title"], listed["due_date"]) == ("failed", "Exam review", "2026-12-01")
    assert 1 in client.get(f"/lessons/{lesson_id}", headers=AUTH).json()["rerun_stages"]


def test_a_filled_lesson_can_be_deleted_when_it_fails(client, data_dir):
    lesson_id = plan(client)
    fill(client, lesson_id)
    run(data_dir, lesson_id, FakeModel({}))
    assert client.delete(f"/lessons/{lesson_id}", headers=AUTH).status_code == 200
    assert leftovers(data_dir) == []
