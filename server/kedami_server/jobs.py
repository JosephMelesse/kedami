"""Background jobs: Claude Code run by the server without a terminal, for the work a button starts.
See architecture/agent-mode.md, Background jobs.

Jobs run one at a time, in the order they were queued. Each is `claude -p` with a skill command as the
prompt, in restricted mode: it may read the data folder, start the plugin's subagents, and call Kedami's
tools, and nothing else. The server is still the only writer; a job only calls the agent routes.
"""

import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import threading
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from . import db, library
from .agent import plugin

KINDS = ("build", "solution", "simulation")
# The longest each kind may run before it is stopped, in seconds.
TIME_LIMITS = {"build": 60 * 60, "solution": 20 * 60, "simulation": 20 * 60}

NOT_INSTALLED = "Claude Code isn't installed. Install it from code.claude.com and log in once in the Terminal panel."
CLOSED = "Kedami was closed."

# IDs go into the prompt as words, so they must be plain words.
_PLAIN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
# The most of Claude Code's error output kept for a failure's reason.
_STDERR_LINES = 20


@dataclass(frozen=True)
class Job:
    id: int
    kind: str
    lesson_id: str
    block_id: str | None
    part_id: str | None
    status: str
    error: str | None
    created: str
    started: str | None
    ended: str | None

    @property
    def active(self) -> bool:
        return self.status in ("queued", "running")


def skill_command(job: Job) -> str:
    """The prompt: the plugin's skill command for this job, with its IDs."""
    if job.kind == "build":
        ids, skill = [job.lesson_id], "lesson"
    elif job.kind == "solution":
        ids, skill = [job.lesson_id, job.block_id, job.part_id], "solution"
    elif job.kind == "simulation":
        ids, skill = [job.lesson_id, job.block_id], "simulation"
    else:
        raise ValueError(f"unknown job kind: {job.kind}")
    for value in ids:
        if value is None or not _PLAIN_ID.fullmatch(value):
            raise ValueError(f"not a plain ID: {value!r}")
    return " ".join([f"/{plugin.NAME}:{skill}", *ids])


def command(claude: str, data_dir: Path, job: Job) -> list[str]:
    """Claude Code with Kedami's plugin, limited to reading the data folder, the subagents, and Kedami's tools.

    Restricted mode removes every tool that runs commands or code and web access, ignores the student's
    settings files, and keeps file tools inside the working directory. Only Kedami's MCP server is loaded,
    and since nothing may ask for permission, any tool not allowed here is refused.
    """
    return [
        claude,
        "-p",
        skill_command(job),
        "--plugin-dir",
        str(plugin.plugin_dir(data_dir)),
        "--restricted",
        "--tools",
        "Read,Agent",
        "--strict-mcp-config",
        "--mcp-config",
        str(plugin.job_mcp_path(data_dir)),
        "--allowedTools",
        f"mcp__{plugin.JOB_SERVER}",
        "--permission-prompts",
        "none",
        "--output-format",
        "stream-json",
        "--verbose",
        "--no-session-persistence",
    ]


def log_path(data_dir: Path, job_id: int) -> Path:
    return data_dir / "jobs" / f"{job_id}.jsonl"


# The jobs table.


def enqueue(conn: sqlite3.Connection, kind: str, lesson_id: str, block_id: str | None, part_id: str | None) -> Job:
    """Queue a job, or return the one already queued or running for the same thing."""
    if kind not in KINDS:
        raise ValueError(f"unknown job kind: {kind}")
    # Checked before anything is stored, so a bad ID is refused rather than queued.
    skill_command(Job(0, kind, lesson_id, block_id, part_id, "queued", None, "", None, None))
    existing = conn.execute(
        "SELECT * FROM jobs WHERE kind = ? AND lesson_id = ? AND block_id IS ? AND part_id IS ?"
        " AND status IN ('queued', 'running')",
        (kind, lesson_id, block_id, part_id),
    ).fetchone()
    if existing:
        return _job(existing)
    cursor = conn.execute(
        "INSERT INTO jobs (kind, lesson_id, block_id, part_id, status, created) VALUES (?, ?, ?, ?, 'queued', ?)",
        (kind, lesson_id, block_id, part_id, _now()),
    )
    return get(conn, cursor.lastrowid)


def get(conn: sqlite3.Connection, job_id: int) -> Job | None:
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _job(row) if row else None


def active(conn: sqlite3.Connection) -> list[Job]:
    """The running job, if any, then the queue, oldest first."""
    rows = conn.execute(
        "SELECT * FROM jobs WHERE status IN ('queued', 'running') ORDER BY status = 'queued', id"
    ).fetchall()
    return [_job(r) for r in rows]


def latest_for_lesson(conn: sqlite3.Connection, lesson_id: str) -> list[Job]:
    """The newest job of each kind, block, and part in a lesson."""
    rows = conn.execute(
        "SELECT * FROM jobs WHERE id IN (SELECT MAX(id) FROM jobs WHERE lesson_id = ? GROUP BY kind, block_id, part_id)"
        " ORDER BY id",
        (lesson_id,),
    ).fetchall()
    return [_job(r) for r in rows]


def fail_interrupted(conn: sqlite3.Connection) -> None:
    """On start: no job survives the app closing."""
    conn.execute(
        "UPDATE jobs SET status = 'failed', error = ?, ended = ? WHERE status IN ('queued', 'running')",
        (CLOSED, _now()),
    )


def _set_running(conn: sqlite3.Connection, job_id: int) -> str:
    started = _now()
    conn.execute("UPDATE jobs SET status = 'running', started = ? WHERE id = ?", (started, job_id))
    return started


def _end(conn: sqlite3.Connection, job_id: int, status: str, error: str | None = None) -> None:
    conn.execute("UPDATE jobs SET status = ?, error = ?, ended = ? WHERE id = ?", (status, error, _now(), job_id))


def _job(row: sqlite3.Row) -> Job:
    return Job(**{key: row[key] for key in Job.__dataclass_fields__})


def _now() -> str:
    return datetime.now(UTC).isoformat()


# Running them.


class JobRunner:
    """Runs queued jobs one at a time on a worker thread, which starts with the first job queued."""

    def __init__(
        self,
        data_dir: Path,
        port: int,
        token: str,
        find_claude: Callable[[], str | None] = lambda: shutil.which("claude"),
        environ: Mapping[str, str] = os.environ,
        time_limits: Mapping[str, float] = TIME_LIMITS,
    ):
        self.data_dir = data_dir
        self.find_claude = find_claude
        self.env = {**environ, "KEDAMI_PORT": str(port), "KEDAMI_TOKEN": token}
        self.time_limits = time_limits
        self._wake = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stopped = False
        self._process: subprocess.Popen | None = None
        self._running: int | None = None
        self._canceled: set[int] = set()

    def claude_installed(self) -> bool:
        return self.find_claude() is not None

    def enqueue(self, kind: str, lesson_id: str, block_id: str | None = None, part_id: str | None = None) -> Job:
        with db.connect(self.data_dir) as conn:
            job = enqueue(conn, kind, lesson_id, block_id, part_id)
        with self._lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._work, name="kedami-jobs", daemon=True)
                self._thread.start()
        self._wake.set()
        return job

    def cancel(self, job_id: int) -> None:
        """Take a job out of the queue, or stop it if it is running."""
        with self._lock:
            with db.connect(self.data_dir) as conn:
                job = get(conn, job_id)
                if job is None or not job.active:
                    return
                if job.status == "queued":
                    _end(conn, job_id, "canceled")
                    return
            self._canceled.add(job_id)
            if self._running == job_id and self._process:
                _stop(self._process)

    def cancel_lesson(self, lesson_id: str, kind: str | None = None) -> None:
        """Cancel a lesson's active jobs, or only those of one kind."""
        with db.connect(self.data_dir) as conn:
            ids = [j.id for j in active(conn) if j.lesson_id == lesson_id and (kind is None or j.kind == kind)]
        for job_id in ids:
            self.cancel(job_id)

    def shutdown(self) -> None:
        """Stop the running job when the server exits."""
        with self._lock:
            self._stopped = True
            if self._process:
                _stop(self._process)
        self._wake.set()

    def _work(self) -> None:
        while not self._stopped:
            with db.connect(self.data_dir) as conn:
                queue = [j for j in active(conn) if j.status == "queued"]
            if not queue:
                self._wake.wait()
                self._wake.clear()
                continue
            self._run(queue[0])

    def _run(self, job: Job) -> None:
        claude = self.find_claude()
        with db.connect(self.data_dir) as conn:
            if claude is None:
                _end(conn, job.id, "failed", NOT_INSTALLED)
                self._fail_build(conn, job, NOT_INSTALLED)
                return
            started = _set_running(conn, job.id)
        log = log_path(self.data_dir, job.id)
        log.parent.mkdir(parents=True, exist_ok=True)
        stderr: deque[str] = deque(maxlen=_STDERR_LINES)
        result: dict | None = None
        timed_out = threading.Event()
        with self._lock:
            if self._stopped or job.id in self._canceled:
                process = None
            else:
                process = subprocess.Popen(
                    command(claude, self.data_dir, job),
                    cwd=self.data_dir,
                    env=self.env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    # Its own process group, so stopping it also stops the MCP server it started.
                    start_new_session=os.name == "posix",
                )
                self._process, self._running = process, job.id
        if process is not None:
            timer = threading.Timer(self.time_limits[job.kind], lambda: (timed_out.set(), _stop(process)))
            timer.daemon = True
            timer.start()
            drain = threading.Thread(target=lambda: stderr.extend(process.stderr), daemon=True)
            drain.start()
            with log.open("w") as out:
                for line in process.stdout:
                    out.write(line)
                    result = _result_event(line) or result
            process.wait()
            timer.cancel()
            drain.join(timeout=5)
            with self._lock:
                self._process, self._running = None, None
        with db.connect(self.data_dir) as conn:
            self._finish(conn, job, started, process, result, list(stderr), timed_out.is_set())

    def _finish(
        self,
        conn: sqlite3.Connection,
        job: Job,
        started: str,
        process: subprocess.Popen | None,
        result: dict | None,
        stderr: list[str],
        timed_out: bool,
    ) -> None:
        if job.id in self._canceled:
            _end(conn, job.id, "canceled")
            return
        if self._stopped and not _saved(conn, job, started):
            _end(conn, job.id, "failed", CLOSED)
            return
        if _saved(conn, job, started):
            _end(conn, job.id, "done")
            return
        if job.kind == "build":
            row = library.get_lesson_row(conn, job.lesson_id)
            if row is not None and row.status == "failed":
                # Claude Code called fail_lesson, which already gave the reason.
                _end(conn, job.id, "failed", row.error)
                return
        if timed_out:
            minutes = round(self.time_limits[job.kind] / 60)
            reason = f"Claude Code ran longer than {minutes} minutes and was stopped."
        else:
            reason = _reason(result, stderr, process.returncode if process else None)
        _end(conn, job.id, "failed", reason)
        self._fail_build(conn, job, reason)

    @staticmethod
    def _fail_build(conn: sqlite3.Connection, job: Job, reason: str) -> None:
        """A build job that ends without finishing or failing its lesson fails it."""
        if job.kind != "build":
            return
        row = library.get_lesson_row(conn, job.lesson_id)
        if row is not None and row.status == "generating":
            library.set_failed(conn, job.lesson_id, reason)


def _saved(conn: sqlite3.Connection, job: Job, started: str) -> bool:
    """Whether what the job was for is in place: the lesson ready, or the solution or code stored since it started."""
    if job.kind == "build":
        row = library.get_lesson_row(conn, job.lesson_id)
        return row is not None and row.status == "ready"
    if job.kind == "solution":
        row = conn.execute(
            "SELECT updated FROM solutions WHERE lesson_id = ? AND block_id = ? AND part_id = ?",
            (job.lesson_id, job.block_id, job.part_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT updated FROM simulations WHERE lesson_id = ? AND block_id = ? AND code IS NOT NULL",
            (job.lesson_id, job.block_id),
        ).fetchone()
    return row is not None and row["updated"] >= started


def _result_event(line: str) -> dict | None:
    """Claude Code's closing event in its stream JSON, which carries its last message."""
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    return event if isinstance(event, dict) and event.get("type") == "result" else None


def _reason(result: dict | None, stderr: list[str], returncode: int | None) -> str:
    """Why a job failed, in Claude Code's own words where it gave any."""
    message = result.get("result") if result else None
    if isinstance(message, str) and message.strip():
        return _clip(message.strip())
    errors = [line.strip() for line in stderr if line.strip()]
    if errors:
        return _clip(errors[-1])
    return f"Claude Code stopped with exit code {returncode} before saving anything."


def _clip(text: str, limit: int = 600) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _stop(process: subprocess.Popen, grace: float = 5) -> None:
    """Stop the job's process and everything it started, forcing it if it hasn't ended after `grace` seconds."""

    def send(sig: int) -> None:
        try:
            if os.name == "posix":
                os.killpg(process.pid, sig)
            else:
                process.kill() if sig == _KILL else process.terminate()
        except (ProcessLookupError, PermissionError):
            pass

    send(signal.SIGTERM)

    def force() -> None:
        if process.poll() is None:
            send(_KILL)

    timer = threading.Timer(grace, force)
    timer.daemon = True
    timer.start()


_KILL = getattr(signal, "SIGKILL", signal.SIGTERM)
