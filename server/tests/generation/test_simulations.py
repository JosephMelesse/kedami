
import pytest
from pydantic import ValidationError

from kedami_server import db, simulation_state
from kedami_server.generation.assemble import SectionError, assemble_section
from kedami_server.generation.plan import place_problems
from kedami_server.generation.schemas import Plan, SectionDraft, SimulationCode
from kedami_server.lesson import Lesson
from kedami_server.model import ModelError

from .conftest import AUTH
from .factories import extraction
from .test_pipeline import FakeModel, happy_script, lesson_status, run, section_one, section_two

GOOD_CODE = "const ctx = canvas.getContext('2d'); ctx.fillStyle = tokens.text; ctx.fillRect(0, 0, 10, 10); ready();"


def plan_with_simulation():
    return Plan.model_validate({"title": "Projectiles", "sections": [
        {"title": "Vectors", "goal": "Split vectors.", "concepts": ["vectors"], "simulation": "Drag a vector; watch its components."},
        {"title": "Flight", "goal": "Find range.", "concepts": ["gravity", "range"], "simulation": None},
    ]})


def with_simulation(section):
    blocks = section["blocks"]
    return {"blocks": blocks[:1] + [{"type": "simulation", "caption": "Drag the tip of $\\\\vec{A}$."}] + blocks[1:]}


# The code a simulation call must return


@pytest.mark.parametrize(
    "code, message",
    [("", "empty"), ("   ", "empty"), ("draw();", "never calls ready"), ("ready();" + "x" * 40_000, "longer than")],
)
def test_unusable_code_is_rejected(code, message):
    with pytest.raises(ValidationError, match=message):
        SimulationCode(code=code)


# Placement


def test_section_must_have_a_simulation_exactly_when_the_plan_asks():
    first, second = place_problems(plan_with_simulation(), extraction())
    assert first.simulation and second.simulation is None
    section = assemble_section(first, SectionDraft.model_validate(with_simulation(section_one())))
    block = section.blocks[1]
    assert (block.type, block.id, block.code) == ("simulation", "vectors-block-2", "")
    with pytest.raises(SectionError, match="exactly 1 simulation"):
        assemble_section(first, SectionDraft.model_validate(section_one()))
    with pytest.raises(SectionError, match="exactly 0 simulation"):
        assemble_section(second, SectionDraft.model_validate(with_simulation(section_two())))


# Generation and the routes


@pytest.fixture
def lesson_with_simulation(started, data_dir):
    client, create, _ = started
    lesson_id = create().json()["id"]
    fake = FakeModel(happy_script({
        Plan: [plan_with_simulation()],
        SectionDraft: [with_simulation(section_one()), section_two()],
        SimulationCode: [{"code": "no ready here"}, {"code": GOOD_CODE}],
    }))
    run(data_dir, lesson_id, fake)
    return client, lesson_id, fake


def path(lesson_id, block_id="vectors-block-2"):
    return f"/lessons/{lesson_id}/blocks/{block_id}"


def test_generation_writes_the_code_with_a_separate_call(lesson_with_simulation):
    client, lesson_id, fake = lesson_with_simulation
    lesson = Lesson.model_validate(lesson_status(client, lesson_id)["lesson"])
    assert lesson.find_block("vectors-block-2").code == GOOD_CODE
    calls = fake.calls[SimulationCode]
    assert [c["role"] for c in calls] == ["generate", "generate"]
    request = calls[0]["prompt"][-1]["text"]
    assert "Drag a vector; watch its components." in request and "Drag the tip" in request
    assert "never calls ready()" in calls[1]["prompt"][-1]["text"]
    plan_request = fake.calls[Plan][0]["system"]
    assert "simulation" in plan_request


def test_simulation_route_serves_the_lesson_code(lesson_with_simulation):
    client, lesson_id, _ = lesson_with_simulation
    body = client.get(f"{path(lesson_id)}/simulation", headers=AUTH).json()
    assert body == {"code": GOOD_CODE, "flagged": False, "error": None}


def test_only_simulation_blocks_have_simulation_routes(lesson_with_simulation):
    client, lesson_id, _ = lesson_with_simulation
    assert client.get(f"{path(lesson_id, 'ps1-1')}/simulation", headers=AUTH).status_code == 404
    assert client.post(f"{path(lesson_id, 'ps1-1')}/regenerate", headers=AUTH).status_code == 404


def test_failed_load_is_flagged_and_a_good_one_clears_it(lesson_with_simulation):
    client, lesson_id, _ = lesson_with_simulation
    report = lambda body: client.post(f"{path(lesson_id)}/simulation-status", json=body, headers=AUTH)
    assert report({"ok": False, "error": "No ready within 4 seconds"}).json() == {"flagged": True}
    assert client.get(f"{path(lesson_id)}/simulation", headers=AUTH).json()["error"] == "No ready within 4 seconds"
    report({"ok": True})
    assert client.get(f"{path(lesson_id)}/simulation", headers=AUTH).json() == {"code": GOOD_CODE, "flagged": False, "error": None}


@pytest.mark.parametrize("body", [{}, {"ok": "no"}, {"ok": False, "error": "x" * 2001}, {"ok": True, "extra": 1}])
def test_bad_status_reports(lesson_with_simulation, body):
    client, lesson_id, _ = lesson_with_simulation
    assert client.post(f"{path(lesson_id)}/simulation-status", json=body, headers=AUTH).status_code == 422


@pytest.fixture
def app_with_model(data_dir):
    """An app whose regenerate route uses a scripted model."""
    from fastapi.testclient import TestClient

    from kedami_server.app import create_app
    from kedami_server.config import Settings

    def make(script):
        fake = FakeModel(script)
        return TestClient(create_app(Settings(0, "t", data_dir, ()), start_generation=lambda *a: None, call=fake)), fake

    return make


def test_regenerate_stores_new_code_apart_from_the_lesson(lesson_with_simulation, app_with_model, data_dir):
    _, lesson_id, _ = lesson_with_simulation
    before = (data_dir / "lessons" / f"{lesson_id}.json").read_text()
    client, fake = app_with_model({SimulationCode: [{"code": "ready(); // v2"}]})
    client.post(f"{path(lesson_id)}/simulation-status", json={"ok": False, "error": "TypeError: x is undefined"}, headers=AUTH)
    body = client.post(f"{path(lesson_id)}/regenerate", headers=AUTH).json()
    assert body == {"code": "ready(); // v2", "flagged": False, "error": None}
    assert "TypeError: x is undefined" in fake.calls[SimulationCode][0]["prompt"][-1]["text"]
    assert "PS1" in fake.calls[SimulationCode][0]["prompt"][0]["text"]
    assert client.get(f"{path(lesson_id)}/simulation", headers=AUTH).json()["code"] == "ready(); // v2"
    assert (data_dir / "lessons" / f"{lesson_id}.json").read_text() == before


def test_regenerate_failure_is_reported_and_keeps_the_old_code(lesson_with_simulation, app_with_model):
    _, lesson_id, _ = lesson_with_simulation
    client, _ = app_with_model({SimulationCode: [ModelError("Overloaded")]})
    response = client.post(f"{path(lesson_id)}/regenerate", headers=AUTH)
    assert (response.status_code, response.json()["detail"]) == (502, "Overloaded")
    assert client.get(f"{path(lesson_id)}/simulation", headers=AUTH).json()["code"] == GOOD_CODE


def test_rerun_clears_regenerated_code_and_flags(lesson_with_simulation, data_dir):
    client, lesson_id, _ = lesson_with_simulation
    with db.connect(data_dir) as conn:
        simulation_state.save_code(conn, lesson_id, "vectors-block-2", "ready(); // old regeneration")
        simulation_state.set_status(conn, lesson_id, "vectors-block-2", False, "boom")
    fake = FakeModel(happy_script({
        Plan: [plan_with_simulation()],
        SectionDraft: [with_simulation(section_one()), section_two()],
        SimulationCode: [{"code": GOOD_CODE + " // rerun"}],
    }))
    run(data_dir, lesson_id, fake, start_stage=3)
    body = client.get(f"{path(lesson_id)}/simulation", headers=AUTH).json()
    assert body == {"code": GOOD_CODE + " // rerun", "flagged": False, "error": None}
