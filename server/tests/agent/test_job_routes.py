"""Show solution and Generate simulation queue Claude Code jobs. See architecture/agent-mode.md, Background jobs."""

import pytest
from fastapi.testclient import TestClient

from kedami_server import jobs
from kedami_server.agent import plugin
from kedami_server.app import create_app
from kedami_server.config import Settings
from kedami_server.storage import seed_sample

from ..test_jobs import STANDIN, behave, wait_ended
from .conftest import AUTH
from .test_requests import lesson_with_simulation


@pytest.fixture
def standin(tmp_path_factory):
    path = tmp_path_factory.mktemp("bin") / "claude"
    path.write_text(STANDIN)
    path.chmod(0o755)
    return path


def client_for(data_dir, find_claude):
    runner = jobs.JobRunner(data_dir, 1, "t", find_claude=find_claude, environ={"PATH": "/bin"})
    return TestClient(create_app(Settings(0, "t", data_dir, ()), runner)), runner


@pytest.fixture
def jobs_client(agent, standin):
    seed_sample(agent.data_dir)
    plugin.write(agent.data_dir)
    client, runner = client_for(agent.data_dir, lambda: str(standin))
    yield client
    runner.shutdown()


def post(client, path, body=None):
    return client.post(path, json=body or {}, headers=AUTH)


def test_show_solution_queues_a_job_that_saves_it(agent, jobs_client):
    behave(agent.data_dir, solution="save")
    job = post(jobs_client, "/lessons/sample/blocks/ps3-4/solution-job", {"part_id": "a"}).json()
    assert (job["kind"], job["block_id"], job["part_id"]) == ("solution", "ps3-4", "a")
    assert wait_ended(agent.data_dir, job["id"]).status == "done"
    assert jobs_client.get("/lessons/sample/blocks/ps3-4/solution?part_id=a", headers=AUTH).json()["solution"] == {}


def test_asking_again_while_it_runs_returns_the_same_job(agent, jobs_client):
    behave(agent.data_dir, solution="hang")
    first = post(jobs_client, "/lessons/sample/blocks/ps3-4/solution-job", {"part_id": "a"}).json()
    again = post(jobs_client, "/lessons/sample/blocks/ps3-4/solution-job", {"part_id": "a"}).json()
    assert again["id"] == first["id"]


def test_only_parts_and_simulations_that_exist_can_be_asked_for(jobs_client):
    assert post(jobs_client, "/lessons/sample/blocks/ps3-4/solution-job", {"part_id": "z"}).status_code == 404
    assert post(jobs_client, "/lessons/sample/blocks/nope/solution-job", {"part_id": "a"}).status_code == 404
    assert post(jobs_client, "/lessons/sample/blocks/ps3-4/simulation-job").status_code == 404
    assert post(jobs_client, "/lessons/nope/blocks/ps3-4/solution-job", {"part_id": "a"}).status_code == 404
    assert post(jobs_client, "/lessons/sample/blocks/ps3-4/solution-job", {}).status_code == 422


def test_generate_simulation_queues_a_job_that_saves_the_code(agent, standin):
    lesson_id = lesson_with_simulation(agent)
    plugin.write(agent.data_dir)
    behave(agent.data_dir, simulation="save")
    client, runner = client_for(agent.data_dir, lambda: str(standin))
    job = post(client, f"/lessons/{lesson_id}/blocks/vectors-block-4/simulation-job").json()
    assert job["kind"] == "simulation"
    assert wait_ended(agent.data_dir, job["id"]).status == "done"
    assert client.get(f"/lessons/{lesson_id}/blocks/vectors-block-4/simulation", headers=AUTH).json()["code"] == "ready()"
    runner.shutdown()


def test_without_claude_code_the_request_is_refused_saying_to_install_it(agent):
    seed_sample(agent.data_dir)
    client, _ = client_for(agent.data_dir, lambda: None)
    response = post(client, "/lessons/sample/blocks/ps3-4/solution-job", {"part_id": "a"})
    assert (response.status_code, response.json()["detail"]) == (409, jobs.NOT_INSTALLED)


def test_without_a_runner_nothing_is_queued(agent):
    seed_sample(agent.data_dir)
    assert agent.post("/lessons/sample/blocks/ps3-4/solution-job", {"part_id": "a"}).status_code == 503
