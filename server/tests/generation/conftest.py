"""Shared fixtures for tests that need lessons: created through the API and built through the agent routes."""

import pytest
from fastapi.testclient import TestClient

from kedami_server import db
from kedami_server.app import create_app
from kedami_server.config import Settings
from kedami_server.generation.schemas import ProblemsAndConcepts

from .factories import extraction, plan, section_one, section_two

AUTH = {"Authorization": "Bearer t"}


@pytest.fixture
def data_dir(tmp_path):
    db.init(tmp_path)
    return tmp_path


@pytest.fixture
def started(data_dir):
    """A client, a function that creates a lesson waiting for Claude Code, and one that builds it."""
    client = TestClient(create_app(Settings(0, "t", data_dir, ())))

    def create(files=None, subject="physics"):
        files = files if files is not None else [
            ("problem-set.md", b"PS1\n1. A ball...", "problem_set"),
            ("reference.md", b"Notes on projectiles.", "reference"),
        ]
        return upload(client, files, subject)

    return client, create, lambda lesson_id, **kwargs: build(client, lesson_id, **kwargs)


def upload(client, files, subject="physics"):
    """POST /lessons with (name, data, role) per file."""
    return client.post(
        "/lessons",
        data={"subject": subject, "roles": [f[2] for f in files]},
        files=[("files", (f[0], f[1], "application/octet-stream")) for f in files],
        headers=AUTH,
    )


def build(client, lesson_id, title="Projectiles"):
    """Build a created lesson the way Claude Code would, from the factories' extraction and two sections.
    In lesson order its blocks are vectors-block-1, vectors-block-2, ps1-1, flight-block-1, ps1-2."""
    base = f"/agent/lessons/{lesson_id}"
    pages = {"files": [{"file": "problem-set.md", "pages": ["PS1"]}, {"file": "reference.md", "pages": ["Notes"]}]}
    steps = [
        ("start", None),
        ("pages", pages),
        ("extraction", ProblemsAndConcepts.model_validate(extraction().model_dump(exclude={"answers"})).model_dump()),
        ("plan", plan(("Vectors", ["vectors"]), ("Flight", ["gravity", "range"]), title=title).model_dump()),
        ("sections/1", section_one()),
        ("sections/2", section_two()),
        ("finish", None),
    ]
    for path, body in steps:
        response = client.post(f"{base}/{path}", json=body if body is not None else {}, headers=AUTH)
        assert response.status_code == 200, response.text
