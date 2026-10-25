"""Solutions and simulations written by Claude Code when there is no API key. See architecture/agent-mode.md."""

import json

import pytest

from kedami_server.storage import seed_sample

from ..generation.factories import section_one, section_two
from .conftest import extraction_body

SIMULATION = "const draw = () => { ready(); }; draw();"


def physics_steps(value):
    return {
        "given": ["v_0 = 25\\,\\mathrm{m/s}"],
        "required": ["t"],
        "steps": ["t = \\frac{2 v_0 \\sin\\theta}{g}"],
        "final": {"value": value, "expression": None, "correct": None, "query": None},
    }


@pytest.fixture
def sample(agent):
    seed_sample(agent.data_dir)
    return agent


def request(agent, part_id, lesson_id="sample", block_id="ps3-4"):
    return agent.get(f"/agent/lessons/{lesson_id}/blocks/{block_id}/solution-request?part_id={part_id}")


def save(agent, part_id, steps, after_disagreement=False, lesson_id="sample", block_id="ps3-4"):
    return agent.post(
        f"/agent/lessons/{lesson_id}/blocks/{block_id}/solution",
        {"part_id": part_id, "steps": steps, "after_disagreement": after_disagreement},
    )


# Solutions


def test_the_request_shows_the_problem_and_answer_form_but_not_the_answer(sample):
    body = request(sample, "a").json()
    assert body["subject"] == "physics"
    assert body["solve_part"] == "(a)"
    assert [p["label"] for p in body["parts"]] == ["(a)", "(b)", "(c)", "(d)"]
    assert body["answer"] == {"format": "number", "unit": "s"}
    assert "2.36" not in json.dumps(body)


def test_an_agreeing_solution_is_stored_and_served_to_the_window(sample):
    response = save(sample, "a", physics_steps(2.36))
    assert response.json()["matches"] is True
    served = sample.post("/lessons/sample/blocks/ps3-4/solution", {"part_id": "a"}).json()
    assert served["matches"] is True
    assert served["solution"]["format"] == "physics"
    assert served["solution"]["required"] == ["t"]


def test_a_first_disagreement_returns_the_stored_answer_without_saving(sample):
    body = save(sample, "a", physics_steps(3.1)).json()
    assert body["saved"] is False
    assert "2.3613" in body["disagreement"]
    assert request(sample, "a").status_code == 200

    body = save(sample, "a", physics_steps(3.1), after_disagreement=True).json()
    assert (body["saved"], body["matches"]) == (True, False)


def test_a_self_check_part_is_not_compared(sample):
    steps = {**physics_steps(None), "final": {"value": None, "expression": None, "correct": None, "query": None}}
    assert save(sample, "d", steps).json() == {"saved": True, "matches": None}


def test_a_part_with_a_stored_solution_takes_no_new_one(sample):
    save(sample, "a", physics_steps(2.36))
    assert request(sample, "a").status_code == 409
    assert save(sample, "a", physics_steps(2.36)).status_code == 409


def test_steps_in_the_wrong_shape_are_rejected(sample):
    assert save(sample, "a", {"method": "Kinematics", "steps": ["x"], "final": {}}).status_code == 422


def test_unknown_parts_and_unready_lessons_have_no_solution(sample):
    assert request(sample, "z").status_code == 404
    waiting = sample.new_lesson()
    assert request(sample, "a", lesson_id=waiting).status_code == 404


# Simulations


def lesson_with_simulation(agent) -> str:
    lesson_id = agent.new_lesson()
    plan = {
        "title": "Projectiles",
        "sections": [
            {"title": "Vectors", "goal": "g", "concepts": ["vectors"], "simulation": "Drag the angle."},
            {"title": "Flight", "goal": "g", "concepts": ["gravity", "range"]},
        ],
    }
    draft = section_one()
    draft["blocks"].append({"type": "simulation", "caption": "Components as the angle changes."})
    for response in (
        agent.start(lesson_id),
        agent.pages(lesson_id),
        agent.extraction(lesson_id, extraction_body()),
        agent.plan(lesson_id, plan),
        agent.section(lesson_id, 1, draft),
        agent.section(lesson_id, 2, section_two()),
        agent.finish(lesson_id),
    ):
        assert response.status_code == 200, response.text
    return lesson_id


def simulation_path(lesson_id, end):
    return f"/agent/lessons/{lesson_id}/blocks/vectors-block-4/{end}"


def test_the_simulation_request_has_the_brief_and_any_failure(agent):
    lesson_id = lesson_with_simulation(agent)
    body = agent.get(simulation_path(lesson_id, "simulation-request")).json()
    assert (body["brief"], body["caption"], body["failure"]) == ("Drag the angle.", "Components as the angle changes.", None)
    assert body["teaching"] == ["Components."]

    agent.post(f"/lessons/{lesson_id}/blocks/vectors-block-4/simulation-status", {"ok": False, "error": "x is undefined"})
    assert agent.get(simulation_path(lesson_id, "simulation-request")).json()["failure"] == "x is undefined"


def test_saved_simulation_code_is_served_and_unflagged(agent):
    lesson_id = lesson_with_simulation(agent)
    agent.post(f"/lessons/{lesson_id}/blocks/vectors-block-4/simulation-status", {"ok": False, "error": "broken"})
    assert agent.post(simulation_path(lesson_id, "simulation"), {"code": SIMULATION}).status_code == 200
    served = agent.get(f"/lessons/{lesson_id}/blocks/vectors-block-4/simulation").json()
    assert served == {"code": SIMULATION, "flagged": False, "error": None}


def test_simulation_code_that_never_calls_ready_is_rejected(agent):
    lesson_id = lesson_with_simulation(agent)
    response = agent.post(simulation_path(lesson_id, "simulation"), {"code": "draw();"})
    assert response.status_code == 422
    assert "ready()" in response.json()["detail"]


def test_a_block_that_isnt_a_simulation_has_no_request(agent):
    lesson_id = lesson_with_simulation(agent)
    assert agent.get(f"/agent/lessons/{lesson_id}/blocks/vectors-block-1/simulation-request").status_code == 404
