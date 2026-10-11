"""The run log read back as Markdown, and the commit a record names."""

import json
import subprocess

import pytest

from kedami_server import run_log, run_report
from kedami_server.generation.schemas import ProblemsAndConcepts

from .test_pipeline import happy_script, run
from .test_usage_log import LoggingModel


def group(stage, role, model, calls=1, seconds=1, cost=0.0, unpriced=0, **tokens):
    counts = {f"{kind}_tokens": tokens.get(kind, 0) for kind in ("input", "output", "cache_write", "cache_read")}
    return {"stage": stage, "role": role, "model": model, "calls": calls, "latency_ms": seconds * 1000, **counts,
            "cost": cost, "unpriced": unpriced}


def record(**changes):
    made = {
        "started": "2026-10-11T16:05:08.881583+00:00",
        "wall_ms": 529_000,
        "start_stage": 1,
        "rerun": False,
        "outcome": "ready",
        "failed_stage": None,
        "error": None,
        "commit": "e921bcf",
        "dirty": False,
        "lesson": {"id": "abc", "title": "Heat Engines", "subject": "physics", "sections": 9, "blocks": 61,
                   "problems": 10, "parts": 27, "verifiable": 36, "verified": 35},
        "material": {
            "files": [{"filename": "hw.md", "role": "problem_set", "force_transcription": False},
                      {"filename": "lect.pdf", "role": "reference", "force_transcription": False}],
            "pages_kept": 22, "pages_transcribed": 7, "normalized_chars": 29608,
        },
        "usage": [
            group("ingest", "transcribe", "opus", calls=7, seconds=20, cost=0.25, input=10_000, output=2_000),
            group("generate", "generate", "sonnet", calls=3, seconds=400, cost=0.5, output=50_000),
            group("generate", "second_solve", "opus", calls=2, seconds=99, cost=0.25, cache_read=1_000_000),
        ],
        # Not the prices in config: the report uses what the run recorded.
        "prices": {"opus": {"input": 5.0, "output": 100.0, "cache_write": 0.0, "cache_read": 0.25},
                   "sonnet": {"input": 1.0, "output": 10.0, "cache_write": 0.0, "cache_read": 0.1}},
    }
    made.update(changes)
    return made


def written(data_dir, *records):
    run_log.path(data_dir).write_text("".join(json.dumps(r) + "\n" for r in records))
    return run_report.report(data_dir)


def test_nothing_recorded(data_dir):
    assert run_report.report(data_dir) == "No runs recorded."


def test_a_ready_run_reads_as_a_row_and_a_section(data_dir):
    text = written(data_dir, record())
    assert text.startswith("# Run log\n\n| # | Started | Lesson | From stage | Outcome | Calls | Wall time | Cost |")
    assert "| 1 | 2026-10-11 16:05 UTC | Heat Engines | 1 | ready | 12 | 8m 49s | $1.000 |" in text
    assert "## 1. Heat Engines (2026-10-11 16:05 UTC)" in text
    for line in (
        "- Outcome: ready, run from stage 1",
        "- Code: commit e921bcf",
        "- Lesson: physics, abc",
        "- Material: hw.md (problem set), lect.pdf (reference)",
        "- Read: 22 pages kept as text, 7 transcribed, 29,608 characters of normalized text",
        "- Made: 9 sections, 61 blocks, 10 problems (27 parts), 35 of 36 answers verified",
        "- Took: 12 calls, 8m 49s wall time, 8m 39s model time, $1.000",
        "| ingest | 7 | 20s | $0.250 | 25.0% |",
        "| generate | 5 | 8m 19s | $0.750 | 75.0% |",
        "| transcribe | opus | 7 | 20s | $0.250 | 25.0% |",
        "| second_solve | opus | 2 | 1m 39s | $0.250 | 25.0% |",
        # 2,000 on Opus at 100.00 and 50,000 on Sonnet at 10.00.
        "| Output | 52,000 | $0.700 | 70.0% |",
        "| Input | 10,000 | $0.050 | 5.0% |",
        "| Cache read | 1,000,000 | $0.250 | 25.0% |",
    ):
        assert f"\n{line}\n" in f"\n{text}\n"
    assert "Why it failed" not in text


def test_a_failed_run_shows_where_and_why(data_dir):
    failed = record(
        outcome="failed", failed_stage="generate", rerun=True, start_stage=4, dirty=True, commit="abc1234",
        error="Section 6 (Entropy) failed after 3 attempts. Last problem: 1 validation error\nblocks.2.answer\n  bad | value",
        lesson={"id": "abc", "title": "Heat | Engines", "subject": "physics", "sections": None, "blocks": None,
                "problems": None, "parts": None, "verifiable": None, "verified": None},
    )
    text = written(data_dir, record(), failed)
    assert "| 2 | 2026-10-11 16:05 UTC | Heat \\| Engines | 4 | failed | 12 | 8m 49s | $1.000 |" in text
    assert "- Outcome: failed in generate, rerun from stage 4" in text
    assert "- Code: commit abc1234, with uncommitted changes" in text
    assert "Why it failed:\n\n    Section 6 (Entropy) failed after 3 attempts. Last problem: 1 validation error\n    blocks.2.answer\n      bad | value" in text
    second = text.split("## 2. ")[1]
    assert "- Made:" not in second and "- Read: 22 pages" in second


def test_a_run_that_read_nothing_and_called_nothing_has_no_tables(data_dir):
    empty = record(
        outcome="failed", failed_stage="ingest", error="No text could be read from the problem set.", commit=None,
        dirty=None, usage=[], prices={},
        material={"files": [], "pages_kept": None, "pages_transcribed": None, "normalized_chars": None},
    )
    text = written(data_dir, empty)
    assert "| 1 | 2026-10-11 16:05 UTC | Heat Engines | 1 | failed | 0 | 8m 49s | $0.000 |" in text
    assert "- Code: not recorded" in text and "- Material: none" in text
    assert "- Read:" not in text and "| Stage |" not in text and "| Kind |" not in text
    assert "- Took: 0 calls, 8m 49s wall time, 0s model time, $0.000" in text


def test_counts_of_one_read_as_singular(data_dir):
    one = record(
        lesson={"id": "abc", "title": "T", "subject": "math", "sections": 1, "blocks": 1, "problems": 1, "parts": 1,
                "verifiable": 1, "verified": 1},
        material={"files": [], "pages_kept": 1, "pages_transcribed": 0, "normalized_chars": 40},
        usage=[group("plan", "generate", "sonnet")],
    )
    text = written(data_dir, one)
    assert "- Read: 1 page kept as text, 0 transcribed, 40 characters of normalized text" in text
    assert "- Made: 1 section, 1 block, 1 problem (1 part), 1 of 1 answers verified" in text
    assert "- Took: 1 call, " in text


def test_calls_with_no_listed_price_are_counted_not_costed(data_dir):
    usage = [group("generate", "generate", "sonnet", cost=0.5, output=50_000),
             group("generate", "generate", "unlisted", calls=2, unpriced=2, output=9_000)]
    text = written(data_dir, record(usage=usage))
    assert "| generate | 3 | 2s | $0.500 plus 2 with no listed price | 100.0% |" in text
    assert "| generate | unlisted | 2 | 1s | $0.000 plus 2 with no listed price | 0.0% |" in text
    # The tokens are all counted, and only the priced ones costed.
    assert "| Output | 59,000 | $0.500 | 100.0% |" in text


def test_the_report_of_real_runs(started, data_dir):
    _, create, _ = started
    lesson_id = create().json()["id"]
    bad = {"concepts": [], "problems": []}
    run(data_dir, lesson_id, LoggingModel(happy_script({ProblemsAndConcepts: [bad, bad, bad]})))
    run(data_dir, lesson_id, LoggingModel(happy_script()))
    text = run_report.report(data_dir)
    rows = [line.split(" | ") for line in text.splitlines() if line.startswith(("| 1 |", "| 2 |"))]
    assert [(row[2], row[4], row[5], row[-1]) for row in rows] == [
        ("New lesson", "failed", "3", "$0.009 |"), ("Projectiles", "ready", "10", "$0.033 |"),
    ]
    assert "- Outcome: failed in extract, run from stage 1" in text
    assert "    Extraction failed after 3 attempts." in text
    assert "- Made: 2 sections, 5 blocks, 2 problems (3 parts), 3 of 4 answers verified" in text
    assert "| second_solve | claude-opus-5-5 | 2 | 4s | $0.012 | 36.4% |" in text
    # 10 calls of 100 output tokens: 6 on Sonnet at 10.00, 2 on Haiku at 5.00, 2 on Opus at 20.00.
    assert "| Output | 1,000 | $0.011 | 33.3% |" in text


def test_the_command_prints_the_report(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["run_report", str(tmp_path / "missing")])
    with pytest.raises(SystemExit, match="no data folder"):
        run_report.main()
    monkeypatch.setattr("sys.argv", ["run_report", str(tmp_path)])
    run_report.main()
    assert capsys.readouterr().out == "No runs recorded.\n"
    assert not list(tmp_path.iterdir())
    monkeypatch.setattr("sys.argv", ["run_report"])
    with pytest.raises(SystemExit, match="usage"):
        run_report.main()


# The commit the server runs from


def git(folder, *args):
    identity = ["-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]
    subprocess.run(["git", *identity, *args], cwd=folder, check=True, capture_output=True)


def test_the_commit_and_uncommitted_changes_are_read_from_git(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "a.txt").write_text("one")
    git(tmp_path, "add", "a.txt")
    git(tmp_path, "commit", "-q", "-m", "first")
    inside = tmp_path / "server"
    inside.mkdir()
    clean = run_log.read_code(inside)
    assert len(clean.commit) >= 7 and int(clean.commit, 16) >= 0 and clean.dirty is False
    (tmp_path / "a.txt").write_text("two")
    assert run_log.read_code(inside) == run_log.Code(clean.commit, True)


def test_a_folder_outside_a_repository_has_no_commit(tmp_path):
    assert run_log.read_code(tmp_path) == run_log.Code(None, None)


def test_a_machine_without_git_has_no_commit(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    assert run_log.read_code(tmp_path) == run_log.Code(None, None)
