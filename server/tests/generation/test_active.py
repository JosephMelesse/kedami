import pytest

from kedami_server.generation.schemas import SectionDraft

from .conftest import AUTH


@pytest.fixture
def two_lessons(started, data_dir):
    client, create, build = started
    ids = [create().json()["id"] for _ in range(2)]
    for lesson_id in ids:
        build(lesson_id)
    return client, ids


def set_active(client, lesson_id, body):
    return client.post(f"/lessons/{lesson_id}/active", json=body, headers=AUTH)


def active(client, lesson_id):
    lessons = client.get("/lessons", headers=AUTH).json()["lessons"]
    return next(lesson["active"] for lesson in lessons if lesson["id"] == lesson_id)


def test_a_new_lesson_starts_inactive(two_lessons):
    client, (lesson_id, _) = two_lessons
    assert active(client, lesson_id) is False


def test_saved_for_that_lesson_only_and_can_be_undone(two_lessons):
    client, (lesson_id, other) = two_lessons
    assert set_active(client, lesson_id, {"active": True}).json() == {"id": lesson_id, "active": True}
    assert active(client, lesson_id) is True
    assert active(client, other) is False
    # Repeating the request changes nothing.
    set_active(client, lesson_id, {"active": True})
    assert active(client, lesson_id) is True
    set_active(client, lesson_id, {"active": False})
    assert active(client, lesson_id) is False


@pytest.mark.parametrize("body", [{}, {"active": "true"}, {"active": 1}, {"active": None}, {"active": True, "extra": 1}])
def test_bad_requests(two_lessons, body):
    client, (lesson_id, _) = two_lessons
    assert set_active(client, lesson_id, body).status_code == 422
    assert active(client, lesson_id) is False


def test_unknown_or_generating_lessons(started):
    client, create, build = started
    generating = create().json()["id"]
    assert set_active(client, "nope", {"active": True}).status_code == 404
    assert set_active(client, generating, {"active": True}).status_code == 404
    assert active(client, generating) is False
