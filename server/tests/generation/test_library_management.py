import sqlite3

import pytest

from kedami_server import db, simulation_state
from kedami_server.generation.schemas import Plan
from kedami_server.progress import Record, save
from kedami_server.storage import seed_sample

from .conftest import AUTH, upload
from .factories import plan
from .test_pipeline import FakeModel, happy_script, run


@pytest.fixture
def two_lessons(started, data_dir):
    client, create, _ = started
    ids = [create().json()["id"] for _ in range(2)]
    for lesson_id in ids:
        run(data_dir, lesson_id, FakeModel(happy_script()))
    return client, ids


def rows(data_dir, table, lesson_id):
    with db.connect(data_dir) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE lesson_id = ?", (lesson_id,)).fetchone()[0]


def lesson_ids(client):
    return [lesson["id"] for lesson in client.get("/lessons", headers=AUTH).json()["lessons"]]


# Deleting lessons


def test_delete_removes_everything_for_that_lesson_only(two_lessons, data_dir):
    client, (gone, kept) = two_lessons
    with db.connect(data_dir) as conn:
        for lesson_id in (gone, kept):
            save(conn, lesson_id, Record(block_id="ps1-1", part_id="a", status="correct", last_response="8.66"))
            simulation_state.set_status(conn, lesson_id, "vectors-block-1", False, "boom")
    assert client.delete(f"/lessons/{gone}", headers=AUTH).json() == {"deleted": gone}

    assert client.get(f"/lessons/{gone}", headers=AUTH).status_code == 404
    assert lesson_ids(client) == [kept]
    for path in (data_dir / "lessons" / f"{gone}.json", data_dir / "materials" / gone, data_dir / "work" / gone):
        assert not path.exists()
    assert [rows(data_dir, t, gone) for t in ("progress", "materials", "simulations")] == [0, 0, 0]

    assert (data_dir / "lessons" / f"{kept}.json").exists() and (data_dir / "materials" / kept).exists()
    assert [rows(data_dir, t, kept) for t in ("progress", "materials", "simulations")] == [1, 2, 1]


def test_generating_lesson_cannot_be_deleted(started, data_dir):
    client, create, _ = started
    lesson_id = create().json()["id"]
    response = client.delete(f"/lessons/{lesson_id}", headers=AUTH)
    assert response.status_code == 409
    assert (data_dir / "materials" / lesson_id).exists() and lesson_id in lesson_ids(client)


def test_deleting_an_unknown_lesson(started):
    client, _, _ = started
    assert client.delete("/lessons/missing", headers=AUTH).status_code == 404
    assert client.delete("/lessons/..%2Fsecrets", headers=AUTH).status_code == 404


def test_deleted_sample_stays_deleted_after_a_restart(started, data_dir):
    client, _, _ = started
    seed_sample(data_dir)
    assert client.delete("/lessons/sample", headers=AUTH).status_code == 200
    seed_sample(data_dir)
    assert "sample" not in lesson_ids(client)
    assert not (data_dir / "lessons" / "sample.json").exists()


def test_existing_install_with_the_sample_is_not_seeded_twice(data_dir):
    seed_sample(data_dir)
    with db.connect(data_dir) as conn:
        conn.execute("DELETE FROM settings")  # an install from before the flag existed
    seed_sample(data_dir)
    with db.connect(data_dir) as conn:
        assert conn.execute("SELECT COUNT(*) FROM lessons WHERE id = 'sample'").fetchone()[0] == 1
        assert db.get_setting(conn, "sample_seeded") == "1"


# Folders


def folders(client):
    return client.get("/folders", headers=AUTH).json()["folders"]


def test_create_and_list_folders(started):
    client, _, _ = started
    assert client.post("/folders", json={"name": "  Physics 1  "}, headers=AUTH).json()["name"] == "Physics 1"
    client.post("/folders", json={"name": "calculus"}, headers=AUTH)
    assert [(f["name"], f["lessons"]) for f in folders(client)] == [("calculus", 0), ("Physics 1", 0)]


@pytest.mark.parametrize("body, status", [
    ({"name": "PHYSICS 1"}, 409),
    ({"name": "   "}, 422),
    ({"name": ""}, 422),
    ({"name": "x" * 81}, 422),
    ({}, 422),
    ({"name": "ok", "extra": 1}, 422),
])
def test_bad_folder_names(started, body, status):
    client, _, _ = started
    client.post("/folders", json={"name": "Physics 1"}, headers=AUTH)
    assert client.post("/folders", json=body, headers=AUTH).status_code == status


def test_rename_folder(started):
    client, _, _ = started
    week3 = client.post("/folders", json={"name": "Week 3"}, headers=AUTH).json()["id"]
    client.post("/folders", json={"name": "Week 4"}, headers=AUTH)
    rename = lambda name, folder=week3: client.post(f"/folders/{folder}/rename", json={"name": name}, headers=AUTH)
    assert rename("  Kinematics ").json() == {"id": week3, "name": "Kinematics"}
    assert [f["name"] for f in folders(client)] == ["Kinematics", "Week 4"]
    assert rename("KINEMATICS").status_code == 200  # changing only the case of its own name is fine
    assert rename("week 4").status_code == 409
    assert rename("  ").status_code == 422
    assert rename("x", folder=999).status_code == 404
    assert [f["name"] for f in folders(client)] == ["KINEMATICS", "Week 4"]


def test_renaming_keeps_the_folder_lessons(two_lessons):
    client, (first, _) = two_lessons
    folder = client.post("/folders", json={"name": "Week 3"}, headers=AUTH).json()["id"]
    client.post(f"/lessons/{first}/move", json={"folder_id": folder}, headers=AUTH)
    client.post(f"/folders/{folder}/rename", json={"name": "Kinematics"}, headers=AUTH)
    assert folders(client) == [{"id": folder, "name": "Kinematics", "lessons": 1}]


def test_move_lessons_between_folders_and_home(two_lessons):
    client, (first, second) = two_lessons
    folder = client.post("/folders", json={"name": "Week 3"}, headers=AUTH).json()["id"]
    assert client.post(f"/lessons/{first}/move", json={"folder_id": folder}, headers=AUTH).status_code == 200
    summaries = {s["id"]: s["folder_id"] for s in client.get("/lessons", headers=AUTH).json()["lessons"]}
    assert summaries == {first: folder, second: None}
    assert folders(client)[0]["lessons"] == 1
    client.post(f"/lessons/{first}/move", json={"folder_id": None}, headers=AUTH)
    assert folders(client)[0]["lessons"] == 0


@pytest.mark.parametrize("body, status", [({"folder_id": 999}, 404), ({"folder_id": "1"}, 422), ({}, 422)])
def test_bad_moves(two_lessons, body, status):
    client, (first, _) = two_lessons
    client.post("/folders", json={"name": "Week 3"}, headers=AUTH)
    assert client.post(f"/lessons/{first}/move", json=body, headers=AUTH).status_code == status


def test_move_unknown_lesson(started):
    client, _, _ = started
    assert client.post("/lessons/missing/move", json={"folder_id": None}, headers=AUTH).status_code == 404


def test_deleting_a_folder_moves_its_lessons_home(two_lessons, data_dir):
    client, (first, second) = two_lessons
    folder = client.post("/folders", json={"name": "Week 3"}, headers=AUTH).json()["id"]
    for lesson_id in (first, second):
        client.post(f"/lessons/{lesson_id}/move", json={"folder_id": folder}, headers=AUTH)
    assert client.delete(f"/folders/{folder}", headers=AUTH).json() == {"deleted": folder}
    assert folders(client) == []
    lessons = client.get("/lessons", headers=AUTH).json()["lessons"]
    assert [(lesson["id"], lesson["folder_id"]) for lesson in lessons] == [(first, None), (second, None)]
    assert (data_dir / "lessons" / f"{first}.json").exists()
    assert client.delete(f"/folders/{folder}", headers=AUTH).status_code == 404


def test_new_lesson_can_start_in_a_folder(started):
    client, _, _ = started
    folder = client.post("/folders", json={"name": "Week 3"}, headers=AUTH).json()["id"]
    files = [("ps.md", b"PS1 1. x", "problem_set", False)]
    response = client.post(
        "/lessons",
        data={"subject": "math", "roles": ["problem_set"], "force": ["false"], "folder": str(folder)},
        files=[("files", (f[0], f[1], "text/markdown")) for f in files],
        headers=AUTH,
    )
    lesson_id = response.json()["id"]
    assert {s["id"]: s["folder_id"] for s in client.get("/lessons", headers=AUTH).json()["lessons"]}[lesson_id] == folder
    missing = client.post(
        "/lessons",
        data={"subject": "math", "roles": ["problem_set"], "force": ["false"], "folder": "999"},
        files=[("files", ("ps.md", b"x", "text/markdown"))],
        headers=AUTH,
    )
    assert missing.status_code == 422
    assert upload(client, files).status_code == 201


def test_older_database_gains_the_folder_column(tmp_path):
    conn = sqlite3.connect(tmp_path / "kedami.db")
    conn.execute(
        "CREATE TABLE lessons (id TEXT PRIMARY KEY, title TEXT NOT NULL, subject TEXT NOT NULL, status TEXT NOT NULL,"
        " current_stage INTEGER, schema_version INTEGER NOT NULL, revision INTEGER NOT NULL DEFAULT 1, created TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO lessons VALUES ('old', 'Old', 'math', 'ready', NULL, 1, 1, '2026-01-01')")
    conn.commit()
    conn.close()
    db.init(tmp_path)
    with db.connect(tmp_path) as conn:
        row = conn.execute(
            "SELECT error, folder_id, custom_title, reading_block, day_starts FROM lessons WHERE id = 'old'"
        ).fetchone()
    assert [row[key] for key in row.keys()] == [None] * 5


# Renaming lessons


def titles(client):
    return {lesson["id"]: lesson["title"] for lesson in client.get("/lessons", headers=AUTH).json()["lessons"]}


def served_title(client, lesson_id):
    return client.get(f"/lessons/{lesson_id}", headers=AUTH).json()["lesson"]["title"]


def rename(client, lesson_id, body):
    return client.post(f"/lessons/{lesson_id}/rename", json=body, headers=AUTH)


def test_rename_shows_everywhere_but_leaves_the_lesson_file_alone(two_lessons, data_dir):
    client, (renamed, other) = two_lessons
    before = (data_dir / "lessons" / f"{renamed}.json").read_text()
    generated = served_title(client, renamed)

    assert rename(client, renamed, {"title": "  Week 3: projectiles  "}).json() == {
        "id": renamed,
        "title": "Week 3: projectiles",
    }
    assert titles(client) == {renamed: "Week 3: projectiles", other: generated}
    assert served_title(client, renamed) == "Week 3: projectiles"
    assert served_title(client, other) == generated
    assert (data_dir / "lessons" / f"{renamed}.json").read_text() == before


def test_renaming_again_replaces_the_name(two_lessons):
    client, (lesson_id, _) = two_lessons
    rename(client, lesson_id, {"title": "First"})
    rename(client, lesson_id, {"title": "Second"})
    assert served_title(client, lesson_id) == "Second"


def test_a_rerun_keeps_the_new_name(two_lessons, data_dir):
    client, (renamed, other) = two_lessons
    rename(client, renamed, {"title": "My projectiles"})
    new_plan = plan(("Vectors", ["vectors"]), ("Flight", ["gravity", "range"]), title="Projectile motion, revised")
    for lesson_id in (renamed, other):
        run(data_dir, lesson_id, FakeModel(happy_script({Plan: [new_plan]})), start_stage=3)
    assert served_title(client, renamed) == "My projectiles"
    assert titles(client)[renamed] == "My projectiles"
    # A lesson never renamed takes the new plan's title.
    assert served_title(client, other) == "Projectile motion, revised"
    assert titles(client)[other] == "Projectile motion, revised"


def test_a_generating_lesson_can_be_renamed(started):
    client, create, _ = started
    lesson_id = create().json()["id"]
    assert titles(client)[lesson_id] == "New lesson"
    assert rename(client, lesson_id, {"title": "Exam review"}).status_code == 200
    assert titles(client)[lesson_id] == "Exam review"


@pytest.mark.parametrize(
    "body",
    [{}, {"title": ""}, {"title": "   "}, {"title": "x" * 121}, {"title": 5}, {"title": "Ok", "extra": 1}],
)
def test_bad_names(two_lessons, body):
    client, (lesson_id, _) = two_lessons
    assert rename(client, lesson_id, body).status_code == 422


def test_rename_unknown_lesson(started):
    client, _, _ = started
    assert rename(client, "nope", {"title": "X"}).status_code == 404
