"""Nested folders: names within a parent, moves that would make a cycle, and deleting. See Folders in ui.md."""

import pytest
from fastapi.testclient import TestClient

from kedami_server import db, library
from kedami_server.app import create_app
from kedami_server.config import Settings

AUTH = {"Authorization": "Bearer t"}


@pytest.fixture
def data_dir(tmp_path):
    db.init(tmp_path)
    return tmp_path


@pytest.fixture
def client(data_dir):
    return TestClient(create_app(Settings(0, "t", data_dir, ())))


def new(client, name, parent=None):
    response = client.post("/folders", json={"name": name, "parent_id": parent}, headers=AUTH)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def listed(client):
    return {f["id"]: f for f in client.get("/folders", headers=AUTH).json()["folders"]}


def move(client, folder, parent):
    return client.post(f"/folders/{folder}/move", json={"parent_id": parent}, headers=AUTH)


def add_lesson(data_dir, lesson_id, folder=None):
    with db.connect(data_dir) as conn:
        library.create_generating(conn, lesson_id, "math", 1, folder_id=folder)


def lesson_folder(data_dir, lesson_id):
    with db.connect(data_dir) as conn:
        return library.get_lesson_row(conn, lesson_id).folder_id


# Names


def test_two_courses_can_each_have_a_week_1(client):
    physics, calculus = new(client, "Physics"), new(client, "Calculus")
    new(client, "Week 1", physics)
    new(client, "week 1", calculus)
    assert sorted(f["name"] for f in listed(client).values()) == ["Calculus", "Physics", "Week 1", "week 1"]


@pytest.mark.parametrize("second", ["Week 1", "WEEK 1", "  week 1 "])
def test_names_clash_within_a_parent_ignoring_case(client, second):
    physics = new(client, "Physics")
    new(client, "Week 1", physics)
    response = client.post("/folders", json={"name": second, "parent_id": physics}, headers=AUTH)
    assert response.status_code == 409


def test_names_clash_at_the_top_level_too(client):
    # UNIQUE (parent_id, name) would allow this, since NULLs count as distinct.
    new(client, "Physics")
    assert client.post("/folders", json={"name": "physics"}, headers=AUTH).status_code == 409
    assert client.post("/folders", json={"name": "physics", "parent_id": None}, headers=AUTH).status_code == 409


def test_a_rename_clashes_only_within_its_parent(client):
    physics = new(client, "Physics")
    week1, week2 = new(client, "Week 1", physics), new(client, "Week 2", physics)
    new(client, "Elsewhere")
    assert client.post(f"/folders/{week2}/rename", json={"name": "week 1"}, headers=AUTH).status_code == 409
    assert client.post(f"/folders/{week1}/rename", json={"name": "Elsewhere"}, headers=AUTH).status_code == 200


@pytest.mark.parametrize("parent, status", [(999, 404), ("1", 422), (True, 422)])
def test_a_new_folder_needs_a_real_parent(client, parent, status):
    new(client, "Physics")
    assert client.post("/folders", json={"name": "x", "parent_id": parent}, headers=AUTH).status_code == status


# Counts


def test_a_folder_counts_the_lessons_in_its_subfolders_at_any_depth(client, data_dir):
    a = new(client, "A")
    b = new(client, "B", a)
    c = new(client, "C", b)
    other = new(client, "Other")
    add_lesson(data_dir, "in-a", a)
    add_lesson(data_dir, "in-c", c)
    add_lesson(data_dir, "in-c-too", c)
    add_lesson(data_dir, "elsewhere", other)
    add_lesson(data_dir, "at-home")
    folders = listed(client)
    assert [folders[f]["lessons"] for f in (a, b, c, other)] == [3, 2, 2, 1]
    assert [folders[f]["own_lessons"] for f in (a, b, c, other)] == [1, 0, 2, 1]
    assert [folders[f]["subfolders"] for f in (a, b, c, other)] == [1, 1, 0, 0]
    assert [folders[f]["parent_id"] for f in (a, b, c, other)] == [None, a, b, None]


# Moves


def test_a_folder_moves_with_everything_in_it(client, data_dir):
    a, b = new(client, "A"), new(client, "B")
    inner = new(client, "Inner", a)
    add_lesson(data_dir, "deep", inner)
    assert move(client, a, b).json() == {"id": a, "parent_id": b}
    folders = listed(client)
    assert (folders[a]["parent_id"], folders[inner]["parent_id"]) == (b, a)
    assert folders[b]["lessons"] == 1
    assert lesson_folder(data_dir, "deep") == inner
    assert move(client, a, None).status_code == 200
    assert listed(client)[a]["parent_id"] is None
    assert listed(client)[b]["lessons"] == 0


def test_a_folder_cannot_move_into_itself(client):
    a = new(client, "A")
    assert move(client, a, a).status_code == 422
    assert listed(client)[a]["parent_id"] is None


@pytest.mark.parametrize("depth", [1, 2, 5])
def test_a_folder_cannot_move_into_a_descendant(client, depth):
    top = parent = new(client, "Top")
    for level in range(depth):
        parent = new(client, f"Level {level}", parent)
    assert move(client, top, parent).status_code == 422
    assert listed(client)[top]["parent_id"] is None
    assert listed(client)[parent]["lessons"] == 0


def test_a_folder_can_move_to_a_sibling_and_back_up_past_its_parent(client):
    # Neighbours of the forbidden case: only the folder's own subtree is refused.
    top = new(client, "Top")
    a, b = new(client, "A", top), new(client, "B", top)
    leaf = new(client, "Leaf", a)
    assert move(client, a, b).status_code == 200
    assert move(client, leaf, top).status_code == 200
    assert move(client, b, leaf).status_code == 200  # Leaf left B's subtree, so B can go inside it.
    assert move(client, leaf, a).status_code == 422  # A is now inside Leaf, by way of B.


def test_moving_to_where_it_already_is_changes_nothing(client):
    top = new(client, "Top")
    a = new(client, "A", top)
    assert move(client, a, top).status_code == 200
    assert listed(client)[a]["parent_id"] == top


def test_a_move_into_a_name_already_taken_is_refused(client):
    a, b = new(client, "A"), new(client, "B")
    week, _ = new(client, "Week 1", a), new(client, "WEEK 1", b)
    assert move(client, week, b).status_code == 409
    assert listed(client)[week]["parent_id"] == a


@pytest.mark.parametrize("body, status", [({"parent_id": 999}, 404), ({"parent_id": "1"}, 422), ({}, 422)])
def test_bad_folder_moves(client, body, status):
    a = new(client, "A")
    assert client.post(f"/folders/{a}/move", json=body, headers=AUTH).status_code == status


def test_moving_an_unknown_folder(client):
    assert move(client, 999, None).status_code == 404


# Deleting


def delete(client, folder):
    return client.delete(f"/folders/{folder}", headers=AUTH)


def test_deleting_moves_lessons_and_subfolders_up_to_the_parent(client, data_dir):
    top = new(client, "Top")
    middle = new(client, "Middle", top)
    leaf = new(client, "Leaf", middle)
    add_lesson(data_dir, "in-middle", middle)
    add_lesson(data_dir, "in-leaf", leaf)
    assert delete(client, middle).json() == {"deleted": middle, "parent_id": top, "renamed": []}
    assert lesson_folder(data_dir, "in-middle") == top
    assert lesson_folder(data_dir, "in-leaf") == leaf
    folders = listed(client)
    assert middle not in folders
    assert folders[leaf]["parent_id"] == top
    assert folders[top]["lessons"] == 2


def test_deleting_a_top_level_folder_moves_its_contents_home(client, data_dir):
    top = new(client, "Top")
    leaf = new(client, "Leaf", top)
    add_lesson(data_dir, "in-top", top)
    assert delete(client, top).json()["parent_id"] is None
    assert lesson_folder(data_dir, "in-top") is None
    assert listed(client)[leaf]["parent_id"] is None


def test_a_clash_on_delete_gets_the_lowest_free_number(client):
    top = new(client, "Top")
    new(client, "Week 1", top)
    middle = new(client, "Middle", top)
    clashing = new(client, "WEEK 1", middle)
    reply = delete(client, middle).json()
    assert reply["renamed"] == [{"id": clashing, "old": "WEEK 1", "new": "WEEK 1 (2)"}]
    assert listed(client)[clashing]["name"] == "WEEK 1 (2)"


def test_a_clash_skips_numbers_already_taken(client):
    top = new(client, "Top")
    for name in ("Week 1", "Week 1 (2)", "Week 1 (3)"):
        new(client, name, top)
    middle = new(client, "Middle", top)
    clashing = new(client, "Week 1", middle)
    delete(client, middle)
    assert listed(client)[clashing]["name"] == "Week 1 (4)"


def test_the_deleted_folders_own_name_does_not_count_as_taken(client):
    top = new(client, "Top")
    outer = new(client, "Week 1", top)
    inner = new(client, "week 1", outer)
    assert delete(client, outer).json()["renamed"] == []
    folders = listed(client)
    assert (folders[inner]["name"], folders[inner]["parent_id"]) == ("week 1", top)


def test_subfolders_that_can_keep_their_names_do(client):
    # Week 1 needs a number. Week 1 (2) is free and keeps it, so the number given is 3.
    top = new(client, "Top")
    new(client, "Week 1", top)
    middle = new(client, "Middle", top)
    clashing, keeps = new(client, "Week 1", middle), new(client, "Week 1 (2)", middle)
    reply = delete(client, middle).json()
    assert reply["renamed"] == [{"id": clashing, "old": "Week 1", "new": "Week 1 (3)"}]
    assert listed(client)[keeps]["name"] == "Week 1 (2)"


def test_a_renamed_folder_stays_within_the_name_limit(client):
    long_name = "x" * 80
    top = new(client, "Top")
    new(client, long_name, top)
    middle = new(client, "Middle", top)
    clashing = new(client, long_name, middle)
    delete(client, middle)
    name = listed(client)[clashing]["name"]
    assert name == "x" * 76 + " (2)"
    assert len(name) == 80


def test_a_clash_at_the_top_level_is_numbered_too(client):
    new(client, "Week 1")
    top = new(client, "Top")
    clashing = new(client, "Week 1", top)
    delete(client, top)
    assert listed(client)[clashing]["name"] == "Week 1 (2)"


def test_a_folder_left_with_children_cannot_be_deleted_directly(data_dir):
    # If the move up were ever skipped, the delete fails instead of orphaning folders.
    with pytest.raises(Exception):
        with db.connect(data_dir) as conn:
            parent = library.create_folder(conn, "A").id
            library.create_folder(conn, "B", parent_id=parent)
            conn.execute("DELETE FROM folders WHERE id = ?", (parent,))
    with db.connect(data_dir) as conn:
        assert conn.execute("SELECT COUNT(*) FROM folders").fetchone()[0] == 0


def test_deleting_an_unknown_folder(client):
    assert delete(client, 999).status_code == 404
