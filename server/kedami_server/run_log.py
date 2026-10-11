"""The run log: one record per pipeline run of what it made and what it took.

Kept in runs.jsonl in the app data folder, apart from the database and the lesson's files,
so it outlasts both. See architecture/system.md, Run log.
"""

import json
import logging
import subprocess
import threading
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from . import db, library, usage
from .generation.ingest import KEEP, TRANSCRIBE
from .generation.verify import NOT_VERIFIED
from .lesson import CheckpointBlock, Lesson, ProblemBlock
from .storage import load_lesson
from .usage import Recording

log = logging.getLogger(__name__)

RUNS_FILE = "runs.jsonl"

_lock = threading.Lock()


@dataclass(frozen=True)
class Code:
    """The commit the server runs from, and whether the working tree had uncommitted changes."""

    commit: str | None = None
    dirty: bool | None = None


# Read once when the server starts. Empty when git can't be read, and in anything that
# doesn't start the server.
code = Code()


def read_code(folder: Path) -> Code:
    try:
        return Code(_git(folder, "rev-parse", "--short", "HEAD"), bool(_git(folder, "status", "--porcelain")))
    except (OSError, subprocess.SubprocessError):
        return Code()


def _git(folder: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=folder, capture_output=True, text=True, check=True, timeout=10)
    return done.stdout.strip()


def path(data_dir: Path) -> Path:
    return data_dir / RUNS_FILE


def write(
    data_dir: Path,
    lesson_id: str,
    subject: str,
    *,
    work: Path,
    started: str,
    wall_seconds: float,
    start_stage: int,
    rerun: bool,
    error: str | None,
    recorded: Recording,
) -> None:
    """Add the record of a run that just ended; `error` is why it failed, if it did.

    Never raises: a run's outcome must not depend on its record.
    """
    try:
        with db.connect(data_dir) as conn:
            row = library.get_lesson_row(conn, lesson_id)
            materials = library.list_materials(conn, lesson_id)
        # Only a run that ends ready made a lesson; a failed rerun leaves an earlier one in place.
        lesson = load_lesson(data_dir, lesson_id) if error is None else None
        record = {
            "started": started,
            "wall_ms": round(wall_seconds * 1000),
            "start_stage": start_stage,
            "rerun": rerun,
            "outcome": "ready" if error is None else "failed",
            "failed_stage": None if error is None else recorded.stage,
            "error": error,
            "commit": code.commit,
            "dirty": code.dirty,
            "lesson": {"id": lesson_id, "title": row.title if row else None, "subject": subject, **_made(lesson)},
            "material": {
                "files": [
                    {"filename": m.filename, "role": m.role, "force_transcription": m.force_transcription}
                    for m in materials
                ],
                **_read(work),
            },
            "usage": [
                {
                    "stage": stage,
                    "role": role,
                    "model": model,
                    "calls": totals.calls,
                    "latency_ms": totals.latency_ms,
                    "input_tokens": totals.tokens.input,
                    "output_tokens": totals.tokens.output,
                    "cache_write_tokens": totals.tokens.cache_write,
                    "cache_read_tokens": totals.tokens.cache_read,
                    "cost": totals.cost,
                    "unpriced": totals.unpriced,
                }
                for (stage, role, model), totals in recorded.groups.items()
            ],
            "prices": {
                model: asdict(price)
                for model in dict.fromkeys(model for _, _, model in recorded.groups)
                if (price := usage.price_of(model)) is not None
            },
        }
        with _lock:
            _append(path(data_dir), json.dumps(record, ensure_ascii=False))
    except Exception as failure:
        log.warning("run log: could not record the run of lesson %s: %s", lesson_id, failure)


def _made(lesson: Lesson | None) -> dict:
    """The size of the lesson a run made, or nothing for a run that made none."""
    if lesson is None:
        return dict.fromkeys(("sections", "blocks", "problems", "parts", "verifiable", "verified"))
    blocks = [block for section in lesson.sections for block in section.blocks]
    problems = [block for block in blocks if isinstance(block, ProblemBlock)]
    parts = [part for block in problems for part in block.parts]
    answered = [block for block in blocks if isinstance(block, CheckpointBlock)] + parts
    verifiable = [item for item in answered if item.answer.kind not in NOT_VERIFIED]
    return {
        "sections": len(lesson.sections),
        "blocks": len(blocks),
        "problems": len(problems),
        "parts": len(parts),
        "verifiable": len(verifiable),
        "verified": sum(item.verified for item in verifiable),
    }


def _read(work: Path) -> dict:
    """What stage 1 read from the material, or nothing if its output isn't on disk."""
    try:
        routes = Counter(page["route"] for page in json.loads((work / "pages.json").read_text()))
        chars = sum(len(file.read_text()) for file in (work / "normalized").iterdir())
    except (OSError, ValueError, KeyError, TypeError):
        return {"pages_kept": None, "pages_transcribed": None, "normalized_chars": None}
    return {"pages_kept": routes[KEEP], "pages_transcribed": routes[TRANSCRIBE], "normalized_chars": chars}


def _append(file: Path, line: str) -> None:
    with file.open("a+b") as out:
        # A last line cut short, as by a crash while writing, would otherwise swallow this one.
        if out.seek(0, 2):
            out.seek(-1, 2)
            if out.read(1) != b"\n":
                out.write(b"\n")
        out.write(line.encode() + b"\n")


def read(data_dir: Path) -> list[dict]:
    """Every record, oldest first. A line that isn't a record, such as one cut short, is skipped."""
    try:
        lines = path(data_dir).read_text().splitlines()
    except FileNotFoundError:
        return []
    records = []
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records
