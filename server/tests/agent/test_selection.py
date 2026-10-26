"""Selecting a block for Claude Code. See architecture/agent-mode.md, Selecting a block.

What get_selection shows is the riskiest part: it must never carry a stored answer, hint, or solution.
"""

import json

import pytest

from kedami_server import db, solution_state
from kedami_server.storage import load_lesson, seed_sample

from .conftest import AUTH
from .test_requests import lesson_with_simulation

SOLUTION_TEXT = "SECRET-SOLUTION-STEP"
# The sample's stored answers that are written out somewhere, and could leak as text.
STORED = ["10*t - 4.9*t**2", "v0**2*sin(theta)**2/(2*g)", "2.3613", "32.559", "correct_index"]
# All an answer may say about itself: its form.
ANSWER_KEYS = {"format", "unit", "use_only_these_names", "options"}
# Keys that would carry an answer, hint, check, solution, or code.
FORBIDDEN_KEYS = {
    "hints", "rubric", "verified", "correct_index", "correct_indexes", "value", "rel_tolerance", "solution", "code", "svg"
}


@pytest.fixture
def sample(agent):
    seed_sample(agent.data_dir)
    return agent


def select(agent, **body):
    """Select, or with no arguments send JSON null, as the app does to clear the selection."""
    if not body:
        return agent.client.post("/selection", content="null", headers={**AUTH, "Content-Type": "application/json"})
    return agent.client.post("/selection", json=body, headers=AUTH)


def shown(agent):
    return agent.get("/agent/selection").json()


def every_selection(lesson):
    for section in lesson.sections:
        yield {"section_id": section.id}
        for block in section.blocks:
            yield {"block_id": block.id}


def secrets(lesson) -> list[str]:
    """Every hint and self-check rubric in the lesson, plus the stored answers written out."""
    found = list(STORED) + [SOLUTION_TEXT]
    for section in lesson.sections:
        for block in section.blocks:
            for asked in [block] if block.type == "checkpoint" else getattr(block, "parts", []):
                found += asked.hints
                if asked.answer.kind == "self_check":
                    found.append(asked.answer.rubric)
    return found


def keys(value):
    """Every key in a JSON value. A plot's functions are the one place an `expression` belongs, so they're skipped."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            if not (value.get("type") == "plot" and key == "functions"):
                yield from keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from keys(item)


def answers(view):
    for block in view["section"]["blocks"]:
        if block["type"] == "checkpoint":
            yield block["answer"]
        for part in block.get("parts", []):
            yield part["answer"]


class TestWhatClaudeCodeSees:
    def test_no_selection_shows_no_answer_hint_or_solution(self, sample):
        lesson = load_lesson(sample.data_dir, "sample")
        # Hints revealed and a solution written, so both exist to leak.
        sample.post("/lessons/sample/blocks/ps3-4/hint", {"part_id": "a", "count": 2})
        with db.connect(sample.data_dir) as conn:
            solution_state.save(conn, "sample", "ps3-4", "b", {"format": "physics", "steps": [SOLUTION_TEXT]}, True)
        hidden = secrets(lesson)
        assert len(hidden) > 10
        for body in every_selection(lesson):
            assert select(sample, lesson_id="sample", **body).status_code == 200
            view = shown(sample)
            text = json.dumps(view, ensure_ascii=False)
            leaked = [s for s in hidden if s in text]
            assert leaked == [], (body, leaked)
            for answer in answers(view):
                assert set(answer) <= ANSWER_KEYS, (body, answer)
            found = set(keys(view))
            assert not found & FORBIDDEN_KEYS, (body, found & FORBIDDEN_KEYS)
            assert "expression" not in found, body

    def test_each_answer_shows_its_form(self, sample):
        select(sample, lesson_id="sample", block_id="ps3-4")
        parts = {p["id"]: p["answer"] for p in next(b for b in shown(sample)["section"]["blocks"] if b["id"] == "ps3-4")["parts"]}
        assert parts["a"] == {"format": "number", "unit": "s"}
        assert parts["c"] == {"format": "expression", "use_only_these_names": ["g", "theta", "v0"]}
        assert parts["d"] == {"format": "written, then checked by the student against a rubric"}

    def test_a_block_comes_with_its_whole_section_and_the_course_files(self, sample):
        select(sample, lesson_id="sample", block_id="apex-check")
        view = shown(sample)
        assert view["selected"] == {"block": "apex-check"}
        assert view["lesson_id"] == "sample" and view["subject"] == "physics"
        ids = [b["id"] for b in view["section"]["blocks"]]
        assert "apex-check" in ids and "gravity-intro" in ids
        assert view["section"]["title"] and view["section"]["goal"]
        assert isinstance(view["materials"], list)

    def test_a_section_is_selected_as_a_whole(self, sample):
        lesson = load_lesson(sample.data_dir, "sample")
        first = lesson.sections[0]
        select(sample, lesson_id="sample", section_id=first.id)
        view = shown(sample)
        assert view["selected"] == {"section": first.id}
        assert [b["id"] for b in view["section"]["blocks"]] == [b.id for b in first.blocks]

    def test_teaching_shows_in_full(self, sample):
        lesson = load_lesson(sample.data_dir, "sample")
        select(sample, lesson_id="sample", block_id="components-example")
        blocks = {b["id"]: b for b in shown(sample)["section"]["blocks"]}
        example = lesson.find_block("components-example")
        assert blocks["components-example"]["steps"] == example.steps
        assert blocks["components-intro"]["body"] == lesson.find_block("components-intro").body
        # A diagram's SVG is large and says nothing its caption doesn't.
        assert set(blocks["components-diagram"]) == {"type", "id", "caption"}

    def test_a_simulation_shows_its_caption_and_brief_not_its_code(self, agent):
        lesson_id = lesson_with_simulation(agent)
        agent.post(f"/agent/lessons/{lesson_id}/blocks/vectors-block-4/simulation", {"code": "secretCode(); ready()"})
        select(agent, lesson_id=lesson_id, block_id="vectors-block-4")
        block = next(b for b in shown(agent)["section"]["blocks"] if b["id"] == "vectors-block-4")
        assert block == {"type": "simulation", "id": "vectors-block-4", "caption": block["caption"], "brief": "Drag the angle."}

    def test_with_nothing_selected_it_says_to_select_something(self, sample):
        assert shown(sample)["selected"] is None
        assert "Select" in shown(sample)["message"]


class TestSelecting:
    def test_selecting_replaces_the_selection_and_null_clears_it(self, sample):
        select(sample, lesson_id="sample", block_id="ps3-4")
        select(sample, lesson_id="sample", block_id="apex-check")
        assert sample.get("/selection").json()["selection"] == {"lesson_id": "sample", "section_id": None, "block_id": "apex-check"}
        assert select(sample).status_code == 200
        assert sample.get("/selection").json() == {"selection": None}

    @pytest.mark.parametrize(
        "body",
        [
            {"lesson_id": "sample"},
            {"lesson_id": "sample", "block_id": "ps3-4", "section_id": "gravity"},
            {"lesson_id": "sample", "block_id": "nope"},
            {"lesson_id": "sample", "section_id": "nope"},
        ],
    )
    def test_refuses_anything_but_one_section_or_block_of_the_lesson(self, sample, body):
        select(sample, lesson_id="sample", block_id="ps3-4")
        assert select(sample, **body).status_code == 422
        assert sample.get("/selection").json()["selection"]["block_id"] == "ps3-4"

    def test_refuses_a_lesson_that_isnt_ready(self, agent):
        lesson_id = agent.upload().json()["id"]
        assert select(agent, lesson_id=lesson_id, block_id="x").status_code == 404
        assert select(agent, lesson_id="nope", block_id="x").status_code == 404

    def test_the_selection_survives_a_restart(self, sample):
        from fastapi.testclient import TestClient

        from kedami_server.app import create_app
        from kedami_server.config import Settings

        select(sample, lesson_id="sample", block_id="ps3-4")
        again = TestClient(create_app(Settings(0, "t", sample.data_dir, ())))
        assert again.get("/selection", headers=AUTH).json()["selection"]["block_id"] == "ps3-4"

    def test_deleting_the_lesson_clears_it_and_deleting_another_doesnt(self, agent):
        seed_sample(agent.data_dir)
        other = lesson_with_simulation(agent)
        select(agent, lesson_id="sample", block_id="ps3-4")
        agent.client.delete(f"/lessons/{other}", headers=AUTH)
        assert agent.get("/selection").json()["selection"] is not None
        agent.client.delete("/lessons/sample", headers=AUTH)
        assert agent.get("/selection").json() == {"selection": None}
        assert shown(agent)["selected"] is None
