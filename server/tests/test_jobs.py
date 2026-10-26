"""The job runner, with a stand-in for Claude Code. See architecture/agent-mode.md, Background jobs."""

import json
import stat
import sys
import textwrap
import time
from functools import partial

import pytest
from fastapi.testclient import TestClient

from kedami_server import db, jobs, library
from kedami_server.agent import plugin
from kedami_server.app import create_app
from kedami_server.config import Settings

AUTH = {"Authorization": "Bearer t"}

# Acts out what the job's prompt asks for, as standin.json in the data folder says, and records each call.
STANDIN = textwrap.dedent(
    f"""\
    #!{sys.executable}
    import json, os, signal, sqlite3, sys, time
    from datetime import datetime, UTC
    prompt = sys.argv[2]
    words = prompt.split()
    with open("calls.jsonl", "a") as calls:
        calls.write(json.dumps({{"argv": sys.argv, "port": os.environ.get("KEDAMI_PORT"),
                                 "token": os.environ.get("KEDAMI_TOKEN"), "start": time.time()}}) + "\\n")
    behavior = json.load(open("standin.json")).get(words[0], "nothing")
    print(json.dumps({{"type": "system", "subtype": "init"}}), flush=True)
    now = datetime.now(UTC).isoformat()
    conn = sqlite3.connect("kedami.db")
    if behavior == "save":
        if words[0] == "/kedami:lesson":
            conn.execute("UPDATE lessons SET status = 'ready' WHERE id = ?", (words[1],))
        elif words[0] == "/kedami:solution":
            conn.execute("INSERT INTO solutions VALUES (?, ?, ?, '{{}}', 1, ?)", (words[1], words[2], words[3], now))
        else:
            conn.execute("INSERT INTO simulations VALUES (?, ?, 'ready()', 0, NULL, ?)", (words[1], words[2], now))
        conn.commit()
        print(json.dumps({{"type": "result", "subtype": "success", "result": "Saved it."}}))
    elif behavior == "fail_lesson":
        conn.execute("UPDATE lessons SET status = 'failed', error = 'The problem set has no text.' WHERE id = ?", (words[1],))
        conn.commit()
        print(json.dumps({{"type": "result", "subtype": "success", "result": "I failed the lesson."}}))
    elif behavior == "nothing":
        print(json.dumps({{"type": "result", "subtype": "success", "result": "I couldn't read the file."}}))
    elif behavior == "crash":
        print("Invalid API key. Please run /login", file=sys.stderr)
        sys.exit(1)
    elif behavior == "slow":
        time.sleep(0.3)
        print(json.dumps({{"type": "result", "subtype": "success", "result": "Took a while."}}))
    elif behavior == "hang":
        time.sleep(60)
    elif behavior == "stubborn":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(60)
    with open("calls.jsonl", "a") as calls:
        calls.write(json.dumps({{"prompt": prompt, "end": time.time()}}) + "\\n")
    """
)


@pytest.fixture
def data_dir(tmp_path):
    db.init(tmp_path)
    plugin.write(tmp_path)
    return tmp_path


@pytest.fixture
def standin(data_dir):
    path = data_dir.parent / "claude"
    path.write_text(STANDIN)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def behave(data_dir, **by_skill):
    """Set what the stand-in does for each skill, such as lesson="save"."""
    (data_dir / "standin.json").write_text(json.dumps({f"/kedami:{k}": v for k, v in by_skill.items()}))


def make_runner(data_dir, standin, **limits):
    return jobs.JobRunner(
        data_dir, 8765, "secret", find_claude=lambda: str(standin), environ={"PATH": "/bin"},
        time_limits={**jobs.TIME_LIMITS, **limits},
    )


def lesson(data_dir, status="generating"):
    lesson_id = f"lesson-{len(list(data_dir.glob('*'))) + time.monotonic_ns()}"
    with db.connect(data_dir) as conn:
        library.create_generating(conn, lesson_id, "math", schema_version=1, folder_id=None, builder="agent")
        if status == "ready":
            library.set_ready(conn, lesson_id)
    return lesson_id


def job(data_dir, job_id):
    with db.connect(data_dir) as conn:
        return jobs.get(conn, job_id)


def lesson_row(data_dir, lesson_id):
    with db.connect(data_dir) as conn:
        return library.get_lesson_row(conn, lesson_id)


def wait_until(check, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if check():
            return
        time.sleep(0.02)
    raise AssertionError("timed out")


def wait_ended(data_dir, job_id, timeout=10.0):
    wait_until(lambda: not job(data_dir, job_id).active, timeout)
    return job(data_dir, job_id)


def calls(data_dir):
    path = data_dir / "calls.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


class TestCommand:
    def make(self, kind, block=None, part=None):
        return jobs.Job(1, kind, "abc-123", block, part, "queued", None, "", None, None)

    def test_runs_the_skill_for_each_kind(self):
        assert jobs.skill_command(self.make("build")) == "/kedami:lesson abc-123"
        assert jobs.skill_command(self.make("solution", "ps1-1", "a")) == "/kedami:solution abc-123 ps1-1 a"
        assert jobs.skill_command(self.make("simulation", "flight-block-4")) == "/kedami:simulation abc-123 flight-block-4"

    def test_is_limited_to_reading_the_data_folder_the_subagents_and_kedamis_tools(self, tmp_path):
        argv = jobs.command("/bin/claude", tmp_path, self.make("build"))
        assert argv[:3] == ["/bin/claude", "-p", "/kedami:lesson abc-123"]
        joined = " ".join(argv)
        for expected in (
            f"--plugin-dir {tmp_path / 'agent-plugin'}",
            "--tools Read,Agent",
            f"--mcp-config {tmp_path / 'jobs' / 'mcp.json'}",
            "--allowedTools mcp__plugin_kedami_kedami",
            "--permission-prompts none",
            "--output-format stream-json",
        ):
            assert expected in joined
        for flag in ("--restricted", "--strict-mcp-config", "--no-session-persistence"):
            assert flag in argv
        assert not any("bypass" in a or "dangerously" in a for a in argv)

    @pytest.mark.parametrize("bad", ["ps1 1", "-x", "a;b", "", "$(rm)", "ps1-1\n/other"])
    def test_refuses_ids_that_are_not_plain_words(self, bad):
        with pytest.raises(ValueError):
            jobs.skill_command(self.make("solution", bad, "a"))
        with pytest.raises(ValueError):
            jobs.skill_command(self.make("solution", "ps1-1", bad))

    def test_the_job_mcp_config_names_the_server_like_the_plugin_and_holds_no_token(self, data_dir):
        config = json.loads(plugin.job_mcp_path(data_dir).read_text())["mcpServers"]
        assert list(config) == ["plugin_kedami_kedami"]
        assert config["plugin_kedami_kedami"]["env"]["KEDAMI_TOKEN"] == "${KEDAMI_TOKEN}"
        # The tools it serves are the ones the job allows.
        argv = jobs.command("c", data_dir, self.make("build"))
        assert argv[argv.index("--allowedTools") + 1] == f"mcp__{plugin.JOB_SERVER}"


class TestQueue:
    def test_the_same_request_while_active_returns_the_same_job(self, data_dir):
        lesson_id = lesson(data_dir, "ready")
        with db.connect(data_dir) as conn:
            first = jobs.enqueue(conn, "solution", lesson_id, "ps1-1", "a")
            assert jobs.enqueue(conn, "solution", lesson_id, "ps1-1", "a").id == first.id
            assert jobs.enqueue(conn, "solution", lesson_id, "ps1-1", "b").id != first.id
            conn.execute("UPDATE jobs SET status = 'done' WHERE id = ?", (first.id,))
            assert jobs.enqueue(conn, "solution", lesson_id, "ps1-1", "a").id != first.id

    def test_a_bad_id_is_refused_before_anything_is_stored(self, data_dir):
        lesson_id = lesson(data_dir, "ready")
        with db.connect(data_dir) as conn:
            with pytest.raises(ValueError):
                jobs.enqueue(conn, "solution", lesson_id, "ps1 1", "a")
            with pytest.raises(ValueError):
                jobs.enqueue(conn, "rerun", lesson_id, None, None)
            assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0

    def test_runs_one_at_a_time_in_order(self, data_dir, standin):
        behave(data_dir, solution="slow")
        runner = make_runner(data_dir, standin)
        lesson_id = lesson(data_dir, "ready")
        ids = [runner.enqueue("solution", lesson_id, "ps1-1", part).id for part in ("a", "b", "c")]
        for job_id in ids:
            wait_ended(data_dir, job_id)
        starts = [c for c in calls(data_dir) if "start" in c]
        ends = [c for c in calls(data_dir) if "end" in c]
        assert [c["argv"][2].split()[-1] for c in starts] == ["a", "b", "c"]
        assert starts[1]["start"] >= ends[0]["end"] and starts[2]["start"] >= ends[1]["end"]

    def test_passes_the_port_and_token_and_runs_in_the_data_folder_with_a_log(self, data_dir, standin):
        behave(data_dir, lesson="save")
        runner = make_runner(data_dir, standin)
        queued = runner.enqueue("build", lesson(data_dir))
        wait_ended(data_dir, queued.id)
        call = calls(data_dir)[0]
        assert (call["port"], call["token"]) == ("8765", "secret")
        assert '"type": "result"' in jobs.log_path(data_dir, queued.id).read_text()


class TestEnding:
    def test_a_build_is_done_once_the_lesson_is_ready(self, data_dir, standin):
        behave(data_dir, lesson="save")
        lesson_id = lesson(data_dir)
        ended = wait_ended(data_dir, make_runner(data_dir, standin).enqueue("build", lesson_id).id)
        assert (ended.status, ended.error) == ("done", None)
        assert lesson_row(data_dir, lesson_id).status == "ready"

    def test_a_build_that_ends_without_finishing_fails_its_lesson_with_claude_codes_last_message(self, data_dir, standin):
        behave(data_dir, lesson="nothing")
        lesson_id = lesson(data_dir)
        ended = wait_ended(data_dir, make_runner(data_dir, standin).enqueue("build", lesson_id).id)
        assert (ended.status, ended.error) == ("failed", "I couldn't read the file.")
        assert (lesson_row(data_dir, lesson_id).status, lesson_row(data_dir, lesson_id).error) == (
            "failed",
            "I couldn't read the file.",
        )

    def test_a_build_that_failed_its_lesson_keeps_that_reason(self, data_dir, standin):
        behave(data_dir, lesson="fail_lesson")
        lesson_id = lesson(data_dir)
        ended = wait_ended(data_dir, make_runner(data_dir, standin).enqueue("build", lesson_id).id)
        assert (ended.status, ended.error) == ("failed", "The problem set has no text.")
        assert lesson_row(data_dir, lesson_id).error == "The problem set has no text."

    def test_a_crash_fails_with_what_claude_code_printed(self, data_dir, standin):
        behave(data_dir, solution="crash")
        ended = wait_ended(
            data_dir, make_runner(data_dir, standin).enqueue("solution", lesson(data_dir, "ready"), "ps1-1", "a").id
        )
        assert (ended.status, ended.error) == ("failed", "Invalid API key. Please run /login")

    def test_a_solution_or_simulation_is_done_only_if_saved_while_it_ran(self, data_dir, standin):
        lesson_id = lesson(data_dir, "ready")
        runner = make_runner(data_dir, standin)
        behave(data_dir, solution="save", simulation="nothing")
        assert wait_ended(data_dir, runner.enqueue("solution", lesson_id, "ps1-1", "a").id).status == "done"
        assert wait_ended(data_dir, runner.enqueue("simulation", lesson_id, "flight-block-4").id).status == "failed"
        # A solution saved before this job started doesn't count for it.
        behave(data_dir, solution="nothing")
        assert wait_ended(data_dir, runner.enqueue("solution", lesson_id, "ps1-1", "a").id).status == "failed"

    def test_a_job_past_its_time_limit_is_stopped_and_fails(self, data_dir, standin):
        behave(data_dir, lesson="hang")
        lesson_id = lesson(data_dir)
        ended = wait_ended(data_dir, make_runner(data_dir, standin, build=0.5).enqueue("build", lesson_id).id)
        assert ended.status == "failed" and "longer than" in ended.error
        assert lesson_row(data_dir, lesson_id).status == "failed"

    def test_a_job_that_ignores_being_stopped_is_killed(self, data_dir, standin, monkeypatch):
        monkeypatch.setattr(jobs, "_stop", partial(jobs._stop, grace=0.3))
        behave(data_dir, lesson="stubborn")
        ended = wait_ended(data_dir, make_runner(data_dir, standin, build=0.3).enqueue("build", lesson(data_dir)).id, 5)
        assert ended.status == "failed"

    def test_without_claude_code_the_job_fails_saying_to_install_it(self, data_dir):
        runner = jobs.JobRunner(data_dir, 1, "t", find_claude=lambda: None)
        lesson_id = lesson(data_dir)
        ended = wait_ended(data_dir, runner.enqueue("build", lesson_id).id)
        assert (ended.status, ended.error) == ("failed", jobs.NOT_INSTALLED)
        assert lesson_row(data_dir, lesson_id).error == jobs.NOT_INSTALLED
        assert not runner.claude_installed()


class TestCanceling:
    def test_a_queued_job_is_canceled_and_never_runs(self, data_dir, standin):
        behave(data_dir, lesson="hang", solution="save")
        runner = make_runner(data_dir, standin)
        first = runner.enqueue("build", lesson(data_dir))
        wait_until(lambda: job(data_dir, first.id).status == "running")
        second = runner.enqueue("solution", lesson(data_dir, "ready"), "ps1-1", "a")
        runner.cancel(second.id)
        runner.cancel(first.id)
        assert wait_ended(data_dir, first.id).status == "canceled"
        assert job(data_dir, second.id).status == "canceled"
        assert len([c for c in calls(data_dir) if "start" in c]) == 1

    def test_the_cancel_route_fails_the_lesson_and_stops_its_build(self, data_dir, standin):
        behave(data_dir, lesson="hang")
        runner = make_runner(data_dir, standin)
        client = TestClient(create_app(Settings(0, "t", data_dir, ()), runner))
        lesson_id = client.post(
            "/lessons", data={"subject": "math", "roles": ["problem_set"]},
            files=[("files", ("ps.md", b"1. Find x.", "text/markdown"))], headers=AUTH,
        ).json()["id"]
        build = client.get(f"/lessons/{lesson_id}/jobs", headers=AUTH).json()["jobs"][0]
        assert build["kind"] == "build"
        wait_until(lambda: job(data_dir, build["id"]).status == "running")
        assert client.post(f"/lessons/{lesson_id}/cancel", headers=AUTH).status_code == 200
        assert wait_ended(data_dir, build["id"]).status == "canceled"
        assert (lesson_row(data_dir, lesson_id).status, lesson_row(data_dir, lesson_id).error) == ("failed", "Canceled.")

    def test_shutdown_stops_the_running_job(self, data_dir, standin):
        behave(data_dir, lesson="hang")
        runner = make_runner(data_dir, standin)
        running = runner.enqueue("build", lesson(data_dir))
        wait_until(lambda: job(data_dir, running.id).status == "running")
        runner.shutdown()
        ended = wait_ended(data_dir, running.id)
        assert (ended.status, ended.error) == ("failed", jobs.CLOSED)

    def test_on_restart_jobs_that_were_queued_or_running_fail(self, data_dir):
        lesson_id = lesson(data_dir, "ready")
        with db.connect(data_dir) as conn:
            queued = jobs.enqueue(conn, "solution", lesson_id, "ps1-1", "a")
            running = jobs.enqueue(conn, "solution", lesson_id, "ps1-1", "b")
            jobs._set_running(conn, running.id)
            jobs.fail_interrupted(conn)
            for job_id in (queued.id, running.id):
                ended = jobs.get(conn, job_id)
                assert (ended.status, ended.error) == ("failed", jobs.CLOSED)


class TestRoutes:
    def test_without_a_runner_a_new_lesson_waits(self, data_dir):
        client = TestClient(create_app(Settings(0, "t", data_dir, ())))
        lesson_id = client.post(
            "/lessons", data={"subject": "math", "roles": ["problem_set"]},
            files=[("files", ("ps.md", b"1. Find x.", "text/markdown"))], headers=AUTH,
        ).json()["id"]
        assert client.get(f"/lessons/{lesson_id}/jobs", headers=AUTH).json() == {"jobs": []}
        assert client.get("/jobs", headers=AUTH).json() == {"claude": False, "running": None, "queued": []}

    def test_jobs_shows_the_running_job_the_queue_and_whether_claude_code_is_installed(self, data_dir, standin):
        behave(data_dir, lesson="hang")
        runner = make_runner(data_dir, standin)
        client = TestClient(create_app(Settings(0, "t", data_dir, ()), runner))
        first = runner.enqueue("build", lesson(data_dir))
        wait_until(lambda: job(data_dir, first.id).status == "running")
        second = runner.enqueue("build", lesson(data_dir))
        body = client.get("/jobs", headers=AUTH).json()
        assert body["claude"] is True
        assert body["running"]["id"] == first.id
        assert [j["id"] for j in body["queued"]] == [second.id]
        runner.shutdown()
        wait_ended(data_dir, first.id)

    def test_deleting_a_lesson_cancels_its_jobs(self, data_dir, standin):
        behave(data_dir, solution="hang")
        runner = make_runner(data_dir, standin)
        client = TestClient(create_app(Settings(0, "t", data_dir, ()), runner))
        lesson_id = lesson(data_dir, "ready")
        running = runner.enqueue("solution", lesson_id, "ps1-1", "a")
        wait_until(lambda: job(data_dir, running.id).status == "running")
        assert client.delete(f"/lessons/{lesson_id}", headers=AUTH).status_code == 200
        # The row goes with the lesson; the process must still have been stopped.
        wait_until(lambda: runner._running is None)
