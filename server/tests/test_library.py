import json

import pytest
from fastapi.testclient import TestClient

from kedami_server import db
from kedami_server.app import create_app
from kedami_server.config import Settings
from kedami_server.storage import seed_sample

AUTH = {"Authorization": "Bearer t"}


@pytest.fixture
def data_dir(tmp_path):
    db.init(tmp_path)
    seed_sample(tmp_path)
    return tmp_path


@pytest.fixture
def client(data_dir):
    return TestClient(create_app(Settings(port=0, token="t", data_dir=data_dir, allowed_origins=())))


def add_row(data_dir, lesson_id, status, created, stage=None):
    with db.connect(data_dir) as conn:
        conn.execute(
            "INSERT INTO lessons (id, title, subject, status, current_stage, schema_version, created)"
            " VALUES (?, ?, 'math', ?, ?, 1, ?)",
            (lesson_id, lesson_id.title(), status, stage, created),
        )


def test_lists_the_seeded_sample(client):
    [sample] = client.get("/lessons", headers=AUTH).json()["lessons"]
    assert sample["id"] == "sample"
    assert sample["title"] == "Projectile motion"
    assert sample["status"] == "ready"
    assert sample["problems_total"] == 2
    assert sample["problems_done"] == 0


def test_lessons_are_listed_oldest_first(client, data_dir):
    add_row(data_dir, "later", "ready", "9999-01-01T00:00:00+00:00")
    add_row(data_dir, "earlier", "generating", "0001-01-01T00:00:00+00:00", stage=2)
    ids = [lesson["id"] for lesson in client.get("/lessons", headers=AUTH).json()["lessons"]]
    assert ids == ["earlier", "sample", "later"]


def test_lesson_still_generating_has_no_body(client, data_dir):
    add_row(data_dir, "pending", "generating", "2026-01-01T00:00:00+00:00", stage=3)
    body = client.get("/lessons/pending", headers=AUTH).json()
    assert body == {"lesson": None, "status": "generating", "current_stage": 3, "error": None}
    lessons = client.get("/lessons", headers=AUTH).json()["lessons"]
    assert next(lesson for lesson in lessons if lesson["id"] == "pending")["problems_total"] == 0


def test_lesson_file_without_an_index_row_is_not_served(client, data_dir):
    lesson = json.loads((data_dir / "lessons" / "sample.json").read_text())
    lesson["id"] = "orphan"
    (data_dir / "lessons" / "orphan.json").write_text(json.dumps(lesson))
    assert client.get("/lessons/orphan", headers=AUTH).status_code == 404
    assert "orphan" not in [row["id"] for row in client.get("/lessons", headers=AUTH).json()["lessons"]]


def test_status_must_be_known(data_dir):
    with pytest.raises(Exception, match="CHECK"):
        add_row(data_dir, "bad", "done", "2026-01-01T00:00:00+00:00")
