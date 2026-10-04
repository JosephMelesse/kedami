import json

import pytest
from pydantic import ValidationError

from kedami_server import db, solution_state
from kedami_server.generation import pipeline
from kedami_server.generation.schemas import MathSteps, PhysicsSteps, SectionDraft
from kedami_server.generation.solutions import has_solution
from kedami_server.lesson import Part
from kedami_server.model import ModelError

from .conftest import AUTH
from .test_pipeline import FakeModel, happy_script, run, section_one, section_two

FINAL_NONE = {"value": None, "expression": None, "correct": None}


def physics(value, steps=None):
    return {
        "given": ["v_0 = 10\\,\\mathrm{m/s}", "\\theta = 30^\\circ"],
        "required": ["v_x"],
        "steps": steps or ["v_x = v_0 \\cos\\theta", "v_x = (10)(\\cos 30^\\circ)", f"\\boxed{{v_x = {value}\\,\\mathrm{{m/s}}}}"],
        "final": {**FINAL_NONE, "value": value},
    }


def math(value):
    return {
        "method": "Direct substitution",
        "steps": ["f(x) = 10\\cos x", f"\\boxed{{{value}}}"],
        "final": {**FINAL_NONE, "value": value},
    }


# The shape of a reply


def test_stray_dollar_delimiters_are_removed():
    steps = MathSteps.model_validate({**math(1), "steps": ["$$x = 1$$", " $\\boxed{1}$ "]})
    assert steps.steps == ["x = 1", "\\boxed{1}"]


@pytest.mark.parametrize(
    "change, message",
    [
        ({"method": ""}, "method must be"),
        ({"method": "x" * 81}, "method must be"),
        ({"steps": []}, "at least one line"),
        ({"steps": ["x = 1", "  $$ "]}, "empty line"),
        ({"steps": ["x"] * 25}, "more than 24 lines"),
        ({"steps": ["x" * 601]}, "longer than 600"),
    ],
)
def test_unusable_math_steps_are_rejected(change, message):
    with pytest.raises(ValidationError, match=message):
        MathSteps.model_validate({**math(1), **change})


def test_physics_needs_what_is_required_but_not_given_values():
    assert PhysicsSteps.model_validate({**physics(1), "given": []}).given == []
    with pytest.raises(ValidationError, match="required needs at least one line"):
        PhysicsSteps.model_validate({**physics(1), "required": []})


def test_only_math_and_physics_parts_with_checked_or_shown_answers_have_solutions():
    part = lambda answer: Part.model_validate({"label": "(a)", "prompt": "x", "answer": answer})
    numeric = part({"kind": "numeric", "value": 1})
    external = part({"kind": "external", "platform": "leetcode", "number": 1, "title": "Two Sum", "slug": "two-sum"})
    assert has_solution("math", numeric) and has_solution("physics", numeric)
    assert not has_solution("computer_science", numeric)
    assert not has_solution("computer_science", external)


# Writing on request


@pytest.fixture
def lesson(started, data_dir):
    client, create, _ = started
    lesson_id = create().json()["id"]
    run(data_dir, lesson_id, FakeModel(happy_script()))
    return client, lesson_id


@pytest.fixture
def app_with_model(data_dir):
    from fastapi.testclient import TestClient

    from kedami_server.app import create_app
    from kedami_server.config import Settings

    def make(script):
        fake = FakeModel(script)
        return TestClient(create_app(Settings(0, "t", data_dir, ()), start_generation=lambda *a: None, call=fake)), fake

    return make


def ask(client, lesson_id, part_id="a", block_id="ps1-1"):
    return client.post(f"/lessons/{lesson_id}/blocks/{block_id}/solution", json={"part_id": part_id}, headers=AUTH)


def request_data(call):
    """The JSON the request sends about the problem."""
    text = call["prompt"][-1]["text"]
    return json.loads(text.split("\n\n", 1)[1].split("\n\n")[0]), text


def test_written_on_request_without_seeing_the_stored_answer(lesson, app_with_model, data_dir):
    _, lesson_id = lesson
    before = (data_dir / "lessons" / f"{lesson_id}.json").read_text()
    client, fake = app_with_model({PhysicsSteps: [physics(8.66)]})

    body = ask(client, lesson_id).json()
    assert body["matches"] is True
    assert body["solution"]["format"] == "physics"
    assert body["solution"]["steps"][0] == "v_x = v_0 \\cos\\theta"

    [call] = fake.calls[PhysicsSteps]
    assert call["role"] == "solution" and "physics homework problem" in call["system"]
    assert "PS1" in call["prompt"][0]["text"]
    data, text = request_data(call)
    assert (data["problem"], data["solve_part"], data["format"], data["unit"]) == ("PS1 #1", "(a)", "number", "m/s")
    assert [p["label"] for p in data["parts"]] == ["(a)", "(b)"]
    assert "8.66" not in text and "answer key" not in text
    assert (data_dir / "lessons" / f"{lesson_id}.json").read_text() == before


def test_stored_after_the_first_request(lesson, app_with_model):
    _, lesson_id = lesson
    client, fake = app_with_model({PhysicsSteps: [physics(8.66)]})
    first = ask(client, lesson_id).json()
    assert ask(client, lesson_id).json() == first
    assert len(fake.calls[PhysicsSteps]) == 1


def test_each_part_has_its_own_solution(lesson, app_with_model):
    _, lesson_id = lesson
    client, fake = app_with_model({PhysicsSteps: [physics(8.66), physics(5)]})
    assert ask(client, lesson_id, "a").json()["matches"] is True
    assert ask(client, lesson_id, "b").json()["matches"] is True
    assert [request_data(c)[0]["solve_part"] for c in fake.calls[PhysicsSteps]] == ["(a)", "(b)"]


def test_a_disagreement_is_sent_back_once_with_the_stored_answer(lesson, app_with_model):
    _, lesson_id = lesson
    client, fake = app_with_model({PhysicsSteps: [physics(7.1), physics(8.66)]})
    assert ask(client, lesson_id).json()["matches"] is True
    first, second = fake.calls[PhysicsSteps]
    assert "answer key" not in first["prompt"][-1]["text"]
    assert "answer key has 8.66 m/s" in second["prompt"][-1]["text"] and '"value": 7.1' in second["prompt"][-1]["text"]


def test_a_second_disagreement_is_kept_and_marked(lesson, app_with_model):
    _, lesson_id = lesson
    client, fake = app_with_model({PhysicsSteps: [physics(7.1), physics(7.1)]})
    body = ask(client, lesson_id).json()
    assert body["matches"] is False and body["solution"]["final"]["value"] == 7.1
    assert ask(client, lesson_id).json() == body
    assert len(fake.calls[PhysicsSteps]) == 2


def test_a_malformed_reply_is_retried_with_the_reason(lesson, app_with_model):
    _, lesson_id = lesson
    client, fake = app_with_model({PhysicsSteps: [{**physics(8.66), "required": []}, physics(8.66)]})
    assert ask(client, lesson_id).json()["matches"] is True
    assert "required needs at least one line" in fake.calls[PhysicsSteps][1]["prompt"][-1]["text"]


def test_a_failed_call_is_reported_and_stores_nothing(lesson, app_with_model):
    _, lesson_id = lesson
    client, _ = app_with_model({PhysicsSteps: [ModelError("Overloaded"), physics(8.66)]})
    response = ask(client, lesson_id)
    assert (response.status_code, response.json()["detail"]) == (502, "Overloaded")
    assert ask(client, lesson_id).json()["matches"] is True


def test_math_lessons_get_a_method_and_working(started, data_dir, app_with_model):
    _, create, _ = started
    lesson_id = create(subject="math").json()["id"]
    pipeline.run(data_dir, lesson_id, "math", 1, call=FakeModel(happy_script()))
    client, fake = app_with_model({MathSteps: [math(8.66)]})
    body = ask(client, lesson_id).json()
    assert (body["solution"]["format"], body["solution"]["method"], body["matches"]) == ("math", "Direct substitution", True)
    assert "math homework problem" in fake.calls[MathSteps][0]["system"]


def test_self_checked_parts_are_shown_but_not_compared(started, data_dir, app_with_model):
    _, create, _ = started
    lesson_id = create().json()["id"]
    section = section_one()
    section["blocks"][2]["parts"][1]["answer"] = {"kind": "self_check", "rubric": "Explains why."}
    run(data_dir, lesson_id, FakeModel(happy_script({SectionDraft: [section, section_two()]})))
    client, fake = app_with_model({PhysicsSteps: [{**physics(0), "final": FINAL_NONE}]})
    assert ask(client, lesson_id, "b").json()["matches"] is None
    data, _ = request_data(fake.calls[PhysicsSteps][0])
    assert data["format"] == "shown"
    assert len(fake.calls[PhysicsSteps]) == 1


@pytest.mark.parametrize(
    "block_id, part_id",
    [("ps1-1", "z"), ("vectors-block-1", "a"), ("vectors-block-2", "a"), ("nope", "a")],
)
def test_only_problem_parts_have_solutions(lesson, block_id, part_id):
    client, lesson_id = lesson
    assert ask(client, lesson_id, part_id, block_id).status_code == 404


@pytest.mark.parametrize("body", [{}, {"part_id": ""}, {"part_id": 1}, {"part_id": "a", "extra": 1}])
def test_bad_requests(lesson, body):
    client, lesson_id = lesson
    assert client.post(f"/lessons/{lesson_id}/blocks/ps1-1/solution", json=body, headers=AUTH).status_code == 422


def test_rerun_clears_solutions(lesson, data_dir):
    client, lesson_id = lesson
    with db.connect(data_dir) as conn:
        solution_state.save(conn, lesson_id, "ps1-1", "a", {"format": "physics"}, True)
    run(data_dir, lesson_id, FakeModel(happy_script()), start_stage=3)
    with db.connect(data_dir) as conn:
        assert solution_state.load(conn, lesson_id, "ps1-1", "a") is None


def test_deleting_a_lesson_deletes_its_solutions(lesson, data_dir):
    client, lesson_id = lesson
    with db.connect(data_dir) as conn:
        solution_state.save(conn, lesson_id, "ps1-1", "a", {"format": "physics"}, False)
    assert client.delete(f"/lessons/{lesson_id}", headers=AUTH).status_code == 200
    with db.connect(data_dir) as conn:
        assert conn.execute("SELECT COUNT(*) FROM solutions").fetchone()[0] == 0
