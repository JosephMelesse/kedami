from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from kedami_server import db
from kedami_server.app import create_app
from kedami_server.config import Settings
from kedami_server.storage import seed_sample

AUTH = {"Authorization": "Bearer t"}
BASE = "/lessons/sample/blocks"


@pytest.fixture
def data_dir(tmp_path):
    db.init(tmp_path)
    seed_sample(tmp_path)
    return tmp_path


@pytest.fixture
def client(data_dir):
    return TestClient(create_app(Settings(port=0, token="t", data_dir=data_dir, allowed_origins=())))


def post(client, path, body):
    return client.post(f"{BASE}/{path}", json=body, headers=AUTH)


def progress(client):
    records = client.get("/lessons/sample/progress", headers=AUTH).json()["progress"]
    return {(r["block_id"], r["part_id"]): r for r in records}


def summary(client):
    return client.get("/lessons", headers=AUTH).json()["lessons"][0]


def test_progress_starts_empty(client):
    assert progress(client) == {}


def test_wrong_then_correct_answer_is_recorded(client):
    wrong = post(client, "ps3-4/check", {"part_id": "a", "response": "3"}).json()
    assert wrong["correct"] is False
    assert wrong["progress"]["status"] == "in_progress"
    right = post(client, "ps3-4/check", {"part_id": "a", "response": "2.36"}).json()
    assert right["correct"] is True
    record = progress(client)[("ps3-4", "a")]
    assert (record["status"], record["attempts"], record["last_response"]) == ("correct", 2, "2.36")


def test_progress_survives_a_new_app_instance(client, data_dir):
    post(client, "ps3-4/check", {"part_id": "a", "response": "2.36"})
    fresh = TestClient(create_app(Settings(port=0, token="t", data_dir=data_dir, allowed_origins=())))
    assert progress(fresh)[("ps3-4", "a")]["status"] == "correct"


def test_checkpoint_is_checked_without_a_part(client):
    body = post(client, "components-check/check", {"response": "10.05"}).json()
    assert body["correct"] is True
    assert body["progress"]["part_id"] is None
    assert progress(client)[("components-check", None)]["status"] == "correct"


@pytest.mark.parametrize(
    "path, body",
    [
        ("ps3-4/check", {"response": "2.36"}),  # problem needs a part
        ("ps3-4/check", {"part_id": "z", "response": "2.36"}),
        ("components-check/check", {"part_id": "a", "response": "10"}),  # checkpoint has no parts
        ("components-intro/check", {"response": "x"}),
        ("missing/check", {"response": "x"}),
    ],
)
def test_unknown_targets(client, path, body):
    assert post(client, path, body).status_code == 404


def test_malformed_response_is_rejected_and_not_counted(client):
    response = post(client, "ps3-4/check", {"part_id": "a", "response": "two"})
    assert response.status_code == 422
    assert "number" in response.json()["detail"]
    assert progress(client) == {}


def test_expression_with_unknown_name_is_rejected(client):
    response = post(client, "ps3-4/check", {"part_id": "c", "response": "v**2/(2*g)"})
    assert response.status_code == 422
    assert "'v'" in response.json()["detail"]


def test_expression_part(client):
    body = post(client, "ps3-4/check", {"part_id": "c", "response": "(v0*sin(theta))^2/(2*g)"}).json()
    assert body["correct"] is True


def test_self_check_records_judgment_and_text(client):
    body = post(client, "ps3-4/check", {"part_id": "d", "response": {"text": "sin 2θ", "correct": False}}).json()
    assert body["progress"]["status"] == "in_progress"
    assert progress(client)[("ps3-4", "d")]["last_response"] == {"text": "sin 2θ", "correct": False}


def test_choice_checkpoint(client):
    assert post(client, "apex-check/check", {"response": 0}).json()["correct"] is True


def test_cannot_check_a_correct_part_again(client):
    post(client, "ps3-4/check", {"part_id": "a", "response": "2.36"})
    assert post(client, "ps3-4/check", {"part_id": "a", "response": "9"}).status_code == 409
    assert progress(client)[("ps3-4", "a")]["attempts"] == 1


def test_unknown_request_fields_are_rejected(client):
    assert post(client, "ps3-4/check", {"part_id": "a", "response": "2.36", "status": "correct"}).status_code == 422


def test_hints(client):
    body = post(client, "ps3-4/hint", {"part_id": "a", "count": 1}).json()
    assert (body["progress"]["status"], body["progress"]["hints_used"]) == ("in_progress", 1)
    assert post(client, "ps3-4/hint", {"part_id": "a", "count": 1}).json()["progress"]["hints_used"] == 1
    assert post(client, "ps3-4/hint", {"part_id": "a", "count": 2}).json()["progress"]["hints_used"] == 2
    assert post(client, "ps3-4/hint", {"part_id": "a", "count": 3}).status_code == 409


def test_mark_done_and_undo(client):
    post(client, "ps3-4/check", {"part_id": "b", "response": "1"})
    marked = post(client, "ps3-4/mark-done", {"part_id": "b", "done": True}).json()["progress"]
    assert marked["status"] == "marked_done"
    assert post(client, "ps3-4/check", {"part_id": "b", "response": "32.559"}).status_code == 409
    undone = post(client, "ps3-4/mark-done", {"part_id": "b", "done": False}).json()["progress"]
    assert (undone["status"], undone["last_response"], undone["attempts"]) == ("in_progress", "1", 1)


def test_mark_done_needs_a_part(client):
    assert post(client, "components-check/mark-done", {"part_id": None, "done": True}).status_code == 422
    assert post(client, "ps3-4/mark-done", {"part_id": "a", "done": "yes"}).status_code == 422


def test_correct_part_cannot_be_marked_done(client):
    post(client, "ps3-4/check", {"part_id": "a", "response": "2.36"})
    assert post(client, "ps3-4/mark-done", {"part_id": "a", "done": True}).status_code == 409


def test_library_counts_finished_problems(client):
    assert summary(client)["problems_done"] == 0
    for part, response in [("a", "2.36"), ("b", "32.6"), ("c", "v0**2*sin(theta)**2/(2*g)")]:
        assert post(client, "ps3-4/check", {"part_id": part, "response": response}).json()["correct"]
    assert summary(client)["problems_done"] == 0
    post(client, "ps3-4/mark-done", {"part_id": "d", "done": True})
    assert summary(client)["problems_done"] == 1
    post(client, "ps3-5/check", {"part_id": "5", "response": [2, 0]})
    assert summary(client)["problems_done"] == 2
    post(client, "ps3-4/mark-done", {"part_id": "d", "done": False})
    assert summary(client)["problems_done"] == 1


def test_parallel_checks_count_every_attempt(client):
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: post(client, "ps3-4/check", {"part_id": "a", "response": "1"}), range(24)))
    assert all(r.status_code == 200 for r in results)
    assert progress(client)[("ps3-4", "a")]["attempts"] == 24
