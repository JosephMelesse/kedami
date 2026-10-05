import pytest

from .conftest import AUTH
from .test_pipeline import FakeModel, happy_script, run


@pytest.fixture
def two_lessons(started, data_dir):
    client, create, _ = started
    ids = [create().json()["id"] for _ in range(2)]
    for lesson_id in ids:
        run(data_dir, lesson_id, FakeModel(happy_script()))
    return client, ids


def record(client, lesson_id, body):
    return client.post(f"/lessons/{lesson_id}/reading-position", json=body, headers=AUTH)


def reading_block(client, lesson_id):
    return client.get(f"/lessons/{lesson_id}", headers=AUTH).json()["reading_block"]


def test_a_new_lesson_has_no_reading_position(two_lessons):
    client, (lesson_id, _) = two_lessons
    assert reading_block(client, lesson_id) is None


def test_recorded_and_served_for_that_lesson_only(two_lessons):
    client, (read, other) = two_lessons
    assert record(client, read, {"block_id": "vectors-block-1"}).json() == {"block_id": "vectors-block-1"}
    assert reading_block(client, read) == "vectors-block-1"
    assert reading_block(client, other) is None


def test_recording_again_replaces_it(two_lessons):
    client, (lesson_id, _) = two_lessons
    record(client, lesson_id, {"block_id": "vectors-block-1"})
    record(client, lesson_id, {"block_id": "ps1-1"})
    assert reading_block(client, lesson_id) == "ps1-1"


def test_a_rerun_keeps_it(two_lessons, data_dir):
    client, (lesson_id, _) = two_lessons
    record(client, lesson_id, {"block_id": "ps1-1"})
    run(data_dir, lesson_id, FakeModel(happy_script()), start_stage=3)
    assert reading_block(client, lesson_id) == "ps1-1"


def test_a_block_not_in_the_lesson_is_rejected(two_lessons):
    client, (lesson_id, _) = two_lessons
    record(client, lesson_id, {"block_id": "ps1-1"})
    assert record(client, lesson_id, {"block_id": "nope"}).status_code == 404
    assert reading_block(client, lesson_id) == "ps1-1"


@pytest.mark.parametrize("body", [{}, {"block_id": ""}, {"block_id": 1}, {"block_id": "ps1-1", "extra": 1}])
def test_bad_requests(two_lessons, body):
    client, (lesson_id, _) = two_lessons
    assert record(client, lesson_id, body).status_code == 422


def test_unknown_or_generating_lessons(started):
    client, create, _ = started
    generating = create().json()["id"]
    assert record(client, "nope", {"block_id": "ps1-1"}).status_code == 404
    assert record(client, generating, {"block_id": "ps1-1"}).status_code == 404
    assert reading_block(client, generating) is None
