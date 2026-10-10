"""The usage log across a lesson's life: runs, reruns, and calls made on request."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from kedami_server import db, usage, usage_report
from kedami_server.app import create_app
from kedami_server.config import Settings
from kedami_server.generation.schemas import PhysicsSteps, Plan, SectionDraft, SimulationCode
from kedami_server.model import ModelError

from .conftest import AUTH
from .test_pipeline import FakeModel, happy_script, run, section_one, section_two
from .test_simulations import GOOD_CODE, plan_with_simulation, with_simulation
from .test_solutions import physics

MODELS = {"generate": "claude-sonnet-5-5", "second_solve": "claude-opus-5-5", "solution": "claude-opus-5-5",
          "small_check": "claude-haiku-4-5"}


class LoggingModel(FakeModel):
    """A scripted model that logs each call the way the real model function does on a reply."""

    def __call__(self, role, *, system, prompt, output):
        reply = SimpleNamespace(
            model=MODELS[role],
            usage=SimpleNamespace(
                input_tokens=1000, output_tokens=100, cache_creation_input_tokens=0, cache_read_input_tokens=0, iterations=None
            ),
        )
        usage.record(role, MODELS[role], reply, "2026-10-10T00:00:00+00:00", 2.0)
        return super().__call__(role, system=system, prompt=prompt, output=output)


def stages(data_dir, lesson_id):
    with db.connect(data_dir) as conn:
        return {stage: totals.calls for stage, totals in usage.by_stage(conn, lesson_id).items()}


def with_model(data_dir, script):
    fake = LoggingModel(script)
    return TestClient(create_app(Settings(0, "t", data_dir, ()), start_generation=lambda *a: None, call=fake))


@pytest.fixture
def new_lesson(started):
    _, create, _ = started
    return create().json()["id"]


def printed(capsys):
    """The table a run leaves in the server's output: its heading, and each row's cells by stage."""
    heading, _columns, *rows = capsys.readouterr().err.splitlines()[-7:]
    return heading, {row.split()[0]: row.split()[1:] for row in rows}


def test_a_run_logs_each_call_under_its_stage(new_lesson, data_dir, capsys):
    run(data_dir, new_lesson, LoggingModel(happy_script()))
    # Text files need no model to ingest. Stage 4 makes a section, hints, a hint check,
    # and a second solve for each of the two sections.
    assert stages(data_dir, new_lesson) == {"extract": 1, "plan": 1, "generate": 8}
    with db.connect(data_dir) as conn:
        roles = [r["role"] for r in conn.execute("SELECT DISTINCT role FROM model_calls ORDER BY role")]
    assert roles == ["generate", "second_solve", "small_check"]
    heading, rows = printed(capsys)
    assert heading.startswith("lesson ready in ")
    assert rows == {
        "ingest": ["0", "0s", "$0.00"], "extract": ["1", "2s", "$0.00"], "plan": ["1", "2s", "$0.00"],
        "generate": ["8", "16s", "$0.03"], "total": ["10", "20s", "$0.03"],
    }


def test_a_rerun_adds_to_the_lesson_from_its_start_stage(new_lesson, data_dir, capsys):
    run(data_dir, new_lesson, LoggingModel(happy_script()))
    run(data_dir, new_lesson, LoggingModel(happy_script()), start_stage=3)
    assert stages(data_dir, new_lesson) == {"extract": 1, "plan": 2, "generate": 16}
    # The table for the rerun counts only the rerun.
    _, rows = printed(capsys)
    assert (rows["extract"][0], rows["plan"][0], rows["total"][0]) == ("0", "1", "9")


def test_a_failed_run_keeps_what_it_spent(new_lesson, data_dir, capsys):
    run(data_dir, new_lesson, LoggingModel(happy_script({Plan: [ModelError("The model declined this request.")]})))
    assert stages(data_dir, new_lesson) == {"extract": 1, "plan": 1}
    heading, rows = printed(capsys)
    assert heading.startswith("lesson failed in ") and rows["total"][0] == "2"


def test_a_run_that_makes_no_calls_prints_an_empty_table(new_lesson, data_dir, capsys):
    run(data_dir, new_lesson, FakeModel(happy_script()))
    assert stages(data_dir, new_lesson) == {}
    assert printed(capsys)[1]["total"] == ["0", "0s", "$0.00"]


def test_a_run_does_not_leave_its_lesson_named(new_lesson, data_dir):
    run(data_dir, new_lesson, LoggingModel(happy_script()))
    LoggingModel(happy_script())("generate", system="s", prompt="p", output=Plan)
    assert stages(data_dir, new_lesson) == {"extract": 1, "plan": 1, "generate": 8}


def test_a_solution_written_on_request_is_logged_once(new_lesson, data_dir):
    run(data_dir, new_lesson, FakeModel(happy_script()))
    client = with_model(data_dir, {PhysicsSteps: [physics(8.66)]})
    path = f"/lessons/{new_lesson}/blocks/ps1-1/solution"
    assert client.post(path, json={"part_id": "a"}, headers=AUTH).status_code == 200
    # The second request is served from storage.
    assert client.post(path, json={"part_id": "a"}, headers=AUTH).status_code == 200
    assert stages(data_dir, new_lesson) == {"solution": 1}


def test_a_simulation_written_on_request_logs_every_attempt(new_lesson, data_dir):
    script = happy_script({Plan: [plan_with_simulation()], SectionDraft: [with_simulation(section_one()), section_two()]})
    run(data_dir, new_lesson, FakeModel(script))
    client = with_model(data_dir, {SimulationCode: [{"code": "no ready here"}, {"code": GOOD_CODE}]})
    assert client.post(f"/lessons/{new_lesson}/blocks/vectors-block-2/regenerate", headers=AUTH).status_code == 200
    assert stages(data_dir, new_lesson) == {"simulation": 2}


def test_deleting_a_lesson_through_the_api_deletes_its_log(new_lesson, data_dir, started):
    client, _, _ = started
    run(data_dir, new_lesson, LoggingModel(happy_script()))
    assert client.delete(f"/lessons/{new_lesson}", headers=AUTH).status_code == 200
    with db.connect(data_dir) as conn:
        assert conn.execute("SELECT COUNT(*) FROM model_calls").fetchone()[0] == 0


def test_the_report_lists_each_lesson_with_calls(started, data_dir):
    _, create, _ = started
    assert usage_report.report(data_dir) == "No model calls recorded."
    logged, quiet = create().json()["id"], create().json()["id"]
    run(data_dir, logged, LoggingModel(happy_script()))
    run(data_dir, quiet, FakeModel(happy_script()))
    lines = usage_report.report(data_dir).splitlines()
    assert lines[0] == f"Projectiles ({logged})"
    assert lines[1].startswith("  total: 10 calls, 20s of model time, 10,000 input tokens")
    assert [line.split(":")[0] for line in lines[2:]] == ["  extract", "  plan", "  generate"]
    # 4 section and hint calls on Sonnet, 2 hint checks on Haiku, 2 second solves on Opus.
    assert lines[4].endswith(f"${(4 * 0.003 + 2 * 0.0015 + 2 * 0.006):.2f}")


def test_the_report_command_needs_an_existing_database(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["usage_report", str(tmp_path)])
    with pytest.raises(SystemExit, match="no database"):
        usage_report.main()
    assert not list(tmp_path.iterdir())
    db.init(tmp_path)
    usage_report.main()
    assert capsys.readouterr().out == "No model calls recorded.\n"
