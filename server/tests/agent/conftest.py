"""Shared fixtures for agent mode tests. No Claude Code involved: the tests call the agent routes directly."""

import pytest
from fastapi.testclient import TestClient

from kedami_server import db
from kedami_server.app import create_app
from kedami_server.config import Settings
from kedami_server.generation.schemas import ProblemsAndConcepts

from ..generation.factories import extraction, plan, section_one, section_two

AUTH = {"Authorization": "Bearer t"}

FILES = [
    ("problem-set.md", b"PS1\n1. A ball...", "problem_set"),
    ("reference.md", b"Notes on projectiles.", "reference"),
]

PAGES = {
    "files": [
        {"file": "problem-set.md", "pages": ["PS1 #1: A ball is thrown at $10$ m/s.", "PS1 #2: How far?"]},
        {"file": "reference.md", "pages": ["Notes on projectiles."]},
    ]
}


def extraction_body() -> dict:
    return ProblemsAndConcepts.model_validate(extraction().model_dump(exclude={"answers"})).model_dump()


def plan_body() -> dict:
    return plan(("Vectors", ["vectors"]), ("Flight", ["gravity", "range"])).model_dump()


@pytest.fixture
def data_dir(tmp_path):
    db.init(tmp_path)
    return tmp_path


class Agent:
    """A test client with the agent's tool calls as methods."""

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.client = TestClient(create_app(Settings(0, "t", data_dir, ())))

    def get(self, path):
        return self.client.get(path, headers=AUTH)

    def post(self, path, body=None):
        return self.client.post(path, json=body if body is not None else {}, headers=AUTH)

    def upload(self, subject="physics", files=FILES):
        data = {"subject": subject, "roles": [f[2] for f in files]}
        return self.client.post(
            "/lessons",
            data=data,
            files=[("files", (f[0], f[1], "application/octet-stream")) for f in files],
            headers=AUTH,
        )

    def new_lesson(self) -> str:
        response = self.upload()
        assert response.status_code == 201, response.text
        return response.json()["id"]

    def lesson(self, lesson_id):
        return self.get(f"/lessons/{lesson_id}").json()

    def start(self, lesson_id):
        return self.post(f"/agent/lessons/{lesson_id}/start")

    def pages(self, lesson_id, body=PAGES):
        return self.post(f"/agent/lessons/{lesson_id}/pages", body)

    def extraction(self, lesson_id, body=None):
        return self.post(f"/agent/lessons/{lesson_id}/extraction", body or extraction_body())

    def plan(self, lesson_id, body=None):
        return self.post(f"/agent/lessons/{lesson_id}/plan", body or plan_body())

    def section(self, lesson_id, number, body):
        return self.post(f"/agent/lessons/{lesson_id}/sections/{number}", body)

    def hints(self, lesson_id, number, items):
        return self.post(f"/agent/lessons/{lesson_id}/sections/{number}/hints", {"items": items})

    def questions(self, lesson_id, number):
        return self.get(f"/agent/lessons/{lesson_id}/sections/{number}/questions")

    def verification(self, lesson_id, number, solutions):
        return self.post(f"/agent/lessons/{lesson_id}/sections/{number}/verification", {"solutions": solutions})

    def finish(self, lesson_id):
        return self.post(f"/agent/lessons/{lesson_id}/finish")

    def fail(self, lesson_id, reason="Stopped."):
        return self.post(f"/agent/lessons/{lesson_id}/fail", {"reason": reason})

    def through_plan(self) -> str:
        """A started lesson with its pages, extraction, and plan saved."""
        lesson_id = self.new_lesson()
        for step in (self.start, self.pages, self.extraction, self.plan):
            response = step(lesson_id)
            assert response.status_code == 200, response.text
        return lesson_id

    def through_sections(self) -> str:
        lesson_id = self.through_plan()
        for number, draft in ((1, section_one()), (2, section_two())):
            response = self.section(lesson_id, number, draft)
            assert response.status_code == 200, response.text
        return lesson_id


@pytest.fixture
def agent(data_dir):
    return Agent(data_dir)


def number(target, value):
    return {"target": target, "value": value, "expression": None, "correct": None, "query": None}
