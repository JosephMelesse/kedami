import json

import pytest

from kedami_server import db

from .conftest import AUTH
from .test_pipeline import FakeModel, happy_script, run

# The happy script's blocks, in lesson order: vectors-block-1, vectors-block-2, ps1-1, flight-block-1, ps1-2.


@pytest.fixture
def two_lessons(started, data_dir):
    client, create, _ = started
    ids = [create().json()["id"] for _ in range(2)]
    for lesson_id in ids:
        run(data_dir, lesson_id, FakeModel(happy_script()))
    return client, ids


def split(client, lesson_id, body):
    return client.post(f"/lessons/{lesson_id}/days", json=body, headers=AUTH)


def day_starts(client, lesson_id):
    return client.get(f"/lessons/{lesson_id}", headers=AUTH).json()["day_starts"]


def test_a_new_lesson_is_one_day(two_lessons):
    client, (lesson_id, _) = two_lessons
    assert day_starts(client, lesson_id) == []


def test_saved_and_served_for_that_lesson_only(two_lessons):
    client, (lesson_id, other) = two_lessons
    body = {"block_ids": ["ps1-1", "ps1-2"]}
    assert split(client, lesson_id, body).json() == body
    assert day_starts(client, lesson_id) == ["ps1-1", "ps1-2"]
    assert day_starts(client, other) == []


def test_splitting_again_replaces_them_and_an_empty_list_removes_them(two_lessons):
    client, (lesson_id, _) = two_lessons
    split(client, lesson_id, {"block_ids": ["ps1-1", "ps1-2"]})
    split(client, lesson_id, {"block_ids": ["flight-block-1"]})
    assert day_starts(client, lesson_id) == ["flight-block-1"]
    split(client, lesson_id, {"block_ids": []})
    assert day_starts(client, lesson_id) == []


def test_a_rerun_keeps_them(two_lessons, data_dir):
    client, (lesson_id, _) = two_lessons
    split(client, lesson_id, {"block_ids": ["ps1-1"]})
    run(data_dir, lesson_id, FakeModel(happy_script()), start_stage=3)
    assert day_starts(client, lesson_id) == ["ps1-1"]


def test_blocks_gone_after_a_rerun_are_dropped_and_the_rest_served_in_lesson_order(two_lessons, data_dir):
    client, (lesson_id, _) = two_lessons
    with db.connect(data_dir) as conn:
        conn.execute(
            "UPDATE lessons SET day_starts = ? WHERE id = ?",
            (json.dumps(["ps1-2", "gone", "vectors-block-1", "ps1-1"]), lesson_id),
        )
    # The first block can't start a later day, even if it moved there in a rerun.
    assert day_starts(client, lesson_id) == ["ps1-1", "ps1-2"]


@pytest.mark.parametrize(
    "block_ids, status",
    [
        (["nope"], 404),
        (["ps1-1", "nope"], 404),
        (["vectors-block-1"], 422),
        (["ps1-2", "ps1-1"], 422),
        (["ps1-1", "ps1-1"], 422),
    ],
)
def test_bad_day_starts_are_rejected_and_keep_the_saved_ones(two_lessons, block_ids, status):
    client, (lesson_id, _) = two_lessons
    split(client, lesson_id, {"block_ids": ["ps1-1"]})
    assert split(client, lesson_id, {"block_ids": block_ids}).status_code == status
    assert day_starts(client, lesson_id) == ["ps1-1"]


@pytest.mark.parametrize(
    "body",
    [{}, {"block_ids": "ps1-1"}, {"block_ids": [""]}, {"block_ids": [1]}, {"block_ids": [], "extra": 1}, {"block_ids": ["x"] * 30}],
)
def test_bad_requests(two_lessons, body):
    client, (lesson_id, _) = two_lessons
    assert split(client, lesson_id, body).status_code == 422


def test_unknown_or_generating_lessons(started):
    client, create, _ = started
    generating = create().json()["id"]
    assert split(client, "nope", {"block_ids": []}).status_code == 404
    assert split(client, generating, {"block_ids": []}).status_code == 404
    assert day_starts(client, generating) == []
