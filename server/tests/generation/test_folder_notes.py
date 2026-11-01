"""Folder notes: saved on the server, deleted with the folder, and never sent to the model. See ui.md."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from kedami_server import db
from kedami_server.app import create_app
from kedami_server.config import Settings
from kedami_server.library import MAX_FOLDER_NOTE

from .conftest import AUTH
from .test_pipeline import FakeModel, happy_script, run

SECRET = "my private exam plan zebra"


def new_folder(client, name="Week 1", parent=None):
    return client.post("/folders", json={"name": name, "parent_id": parent}, headers=AUTH).json()["id"]


def save(client, folder, note):
    return client.post(f"/folders/{folder}/note", json={"note": note}, headers=AUTH)


def note_of(client, folder):
    return {f["id"]: f["note"] for f in client.get("/folders", headers=AUTH).json()["folders"]}[folder]


def test_a_new_folder_has_no_note(started):
    client, _, _ = started
    assert note_of(client, new_folder(client)) == ""


def test_saving_replaces_the_note_and_keeps_it_as_typed(started):
    client, _, _ = started
    folder = new_folder(client)
    assert save(client, folder, "First").status_code == 200
    typed = "  line one\n\n  line two  \n"
    assert save(client, folder, typed).json() == {"id": folder, "note": typed}
    assert note_of(client, folder) == typed
    assert save(client, folder, "").status_code == 200
    assert note_of(client, folder) == ""


def test_a_note_survives_a_restart(started, data_dir):
    client, _, _ = started
    folder = new_folder(client)
    save(client, folder, "Keep me")
    db.init(data_dir)
    restarted = TestClient(create_app(Settings(0, "t", data_dir, ())))
    assert note_of(restarted, folder) == "Keep me"


@pytest.mark.parametrize("body, status", [
    ({"note": "x" * (MAX_FOLDER_NOTE + 1)}, 422),
    ({"note": 5}, 422),
    ({"note": None}, 422),
    ({}, 422),
    ({"note": "ok", "extra": 1}, 422),
])
def test_bad_notes(started, body, status):
    client, _, _ = started
    folder = new_folder(client)
    save(client, folder, "Before")
    assert client.post(f"/folders/{folder}/note", json=body, headers=AUTH).status_code == status
    assert note_of(client, folder) == "Before"


def test_the_longest_note_is_accepted(started):
    client, _, _ = started
    folder = new_folder(client)
    assert save(client, folder, "x" * MAX_FOLDER_NOTE).status_code == 200


def test_saving_a_note_on_a_deleted_folder(started):
    # A save still waiting when the folder is deleted must not bring anything back.
    client, _, _ = started
    folder = new_folder(client)
    client.delete(f"/folders/{folder}", headers=AUTH)
    assert save(client, folder, "Late").status_code == 404
    assert client.get("/folders", headers=AUTH).json()["folders"] == []


def test_a_note_moves_with_its_folder(started):
    client, _, _ = started
    a, b = new_folder(client, "A"), new_folder(client, "B")
    save(client, a, "Stay with A")
    client.post(f"/folders/{a}/move", json={"parent_id": b}, headers=AUTH)
    assert note_of(client, a) == "Stay with A"
    assert note_of(client, b) == ""


def test_deleting_a_folder_deletes_its_note_and_a_subfolder_keeps_its_own(started, data_dir):
    client, _, _ = started
    top = new_folder(client, "Top")
    inner = new_folder(client, "Inner", top)
    save(client, top, "Goes away")
    save(client, inner, "Moves up")
    client.delete(f"/folders/{top}", headers=AUTH)
    assert note_of(client, inner) == "Moves up"
    with db.connect(data_dir) as conn:
        assert [row["note"] for row in conn.execute("SELECT note FROM folders")] == ["Moves up"]


def test_an_older_database_gains_empty_notes(tmp_path):
    conn = sqlite3.connect(tmp_path / "kedami.db")
    conn.execute("CREATE TABLE folders (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE, created TEXT NOT NULL)")
    conn.execute("INSERT INTO folders VALUES (1, 'Physics', '2026-01-01')")
    conn.commit()
    conn.close()
    db.init(tmp_path)
    with db.connect(tmp_path) as conn:
        assert tuple(conn.execute("SELECT name, parent_id, note FROM folders").fetchone()) == ("Physics", None, "")


def test_a_note_never_reaches_the_model_or_the_lesson(started, data_dir):
    client, _, _ = started
    folder = new_folder(client)
    save(client, folder, SECRET)
    response = client.post(
        "/lessons",
        data={"subject": "physics", "roles": ["problem_set", "reference"], "force": ["false", "false"],
              "folder": str(folder)},
        files=[("files", ("problem-set.md", b"PS1\n1. A ball...", "text/markdown")),
               ("files", ("reference.md", b"Notes on projectiles.", "text/markdown"))],
        headers=AUTH,
    )
    lesson_id = response.json()["id"]
    fake = FakeModel(happy_script())
    run(data_dir, lesson_id, fake)
    assert client.get(f"/lessons/{lesson_id}", headers=AUTH).json()["status"] == "ready"
    assert fake.calls
    assert SECRET not in str(fake.calls)
    for root in ("lessons", "materials", "work"):
        for path in (data_dir / root).rglob("*"):
            if path.is_file():
                assert SECRET.encode() not in path.read_bytes(), path
