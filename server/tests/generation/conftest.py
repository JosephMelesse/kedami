"""Shared fixtures for generation tests."""

import pytest
from fastapi.testclient import TestClient

from kedami_server import db
from kedami_server.app import create_app
from kedami_server.config import Settings

AUTH = {"Authorization": "Bearer t"}


@pytest.fixture
def data_dir(tmp_path):
    db.init(tmp_path)
    return tmp_path


@pytest.fixture
def started(data_dir):
    """Create a lesson through the API without running generation."""
    runs = []
    client = TestClient(create_app(Settings(0, "t", data_dir, ()), start_generation=lambda *args: runs.append(args)))

    def create(files=None, subject="physics"):
        files = files if files is not None else [
            ("problem-set.md", b"PS1\n1. A ball...", "problem_set", False),
            ("reference.md", b"Notes on projectiles.", "reference", False),
        ]
        return upload(client, files, subject)

    return client, create, runs


def upload(client, files, subject="physics", domain=None):
    """POST /lessons with (name, data, role, force) per file. Computer science lessons are DSA unless named."""
    domain = domain or ("dsa" if subject == "computer_science" else None)
    return client.post(
        "/lessons",
        data={"subject": subject, "roles": [f[2] for f in files], "force": [str(f[3]).lower() for f in files]}
        | ({"domain": domain} if domain else {}),
        files=[("files", (f[0], f[1], "application/octet-stream")) for f in files],
        headers=AUTH,
    )
