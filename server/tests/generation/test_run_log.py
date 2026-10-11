"""The run log: one record per pipeline run, kept apart from the lesson and the database.

See architecture/system.md, Run log.
"""

import threading

import pytest

from kedami_server import db, run_log
from kedami_server.config import MODEL_PRICES
from kedami_server.generation.schemas import Plan, ProblemsAndConcepts, SectionDraft, Solutions, Transcription
from kedami_server.model import ModelError

from .conftest import AUTH
from .files import text_pdf
from .test_ingest import transcribed
from .test_pipeline import FakeModel, happy_script, lesson_status, run
from .test_usage_log import LoggingModel, printed

SONNET, OPUS, HAIKU = "claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-4-5"
PROBLEM_SET = ("problem-set.md", b"PS1\n1. A ball...", "problem_set", False)


def scanned(create, pages):
    """A lesson whose reference is a PDF with no text layer, so every page of it is transcribed."""
    return create([PROBLEM_SET, ("scan.pdf", text_pdf(*[""] * pages), "reference", False)]).json()["id"]


def scanned_script(pages, overrides=None):
    return happy_script({Transcription: [transcribed] * pages, **(overrides or {})})


def logged(data_dir, lesson_id):
    """(stage, role) of each usage log row for a lesson."""
    with db.connect(data_dir) as conn:
        rows = conn.execute("SELECT stage, role FROM model_calls WHERE lesson_id = ? ORDER BY id", (lesson_id,))
        return [(row["stage"], row["role"]) for row in rows]


def groups(record):
    return [(u["stage"], u["role"], u["model"], u["calls"]) for u in record["usage"]]


@pytest.fixture
def new_lesson(started):
    _, create, _ = started
    return create().json()["id"]


# Calls made on the transcription threads


def test_transcription_calls_are_counted_under_the_run(started, data_dir, capsys):
    _, create, _ = started
    lesson_id = scanned(create, pages=6)
    run(data_dir, lesson_id, LoggingModel(scanned_script(6)))
    assert logged(data_dir, lesson_id).count(("ingest", "transcribe")) == 6
    [record] = run_log.read(data_dir)
    assert groups(record)[0] == ("ingest", "transcribe", OPUS, 6)
    assert sum(u["calls"] for u in record["usage"]) == len(logged(data_dir, lesson_id)) == 16
    assert (record["material"]["pages_kept"], record["material"]["pages_transcribed"]) == (1, 6)
    assert printed(capsys)[1]["ingest"][0] == "6"


def test_a_rejected_transcription_counts_every_attempt(started, data_dir):
    _, create, _ = started
    lesson_id = scanned(create, pages=1)
    run(data_dir, lesson_id, LoggingModel(scanned_script(1, {Transcription: [{"markdown": None}, transcribed]})))
    assert logged(data_dir, lesson_id).count(("ingest", "transcribe")) == 2
    assert groups(run_log.read(data_dir)[0])[0] == ("ingest", "transcribe", OPUS, 2)


def test_two_runs_transcribing_at_once_keep_their_calls_apart(started, data_dir):
    _, create, _ = started
    pages = {scanned(create, pages=5): 5, scanned(create, pages=3): 3}
    threads = [
        threading.Thread(target=run, args=(data_dir, lesson_id, LoggingModel(scanned_script(count))))
        for lesson_id, count in pages.items()
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    records = {record["lesson"]["id"]: record for record in run_log.read(data_dir)}
    for lesson_id, count in pages.items():
        assert logged(data_dir, lesson_id).count(("ingest", "transcribe")) == count
        assert groups(records[lesson_id])[0] == ("ingest", "transcribe", OPUS, count)
        assert records[lesson_id]["outcome"] == "ready"


def test_a_transcription_thread_does_not_leave_the_lesson_named(started, data_dir):
    _, create, _ = started
    lesson_id = scanned(create, pages=2)
    run(data_dir, lesson_id, LoggingModel(scanned_script(2)))
    before = len(logged(data_dir, lesson_id))
    LoggingModel({Transcription: [{"markdown": "x"}]})("transcribe", system="s", prompt="p", output=Transcription)
    assert len(logged(data_dir, lesson_id)) == before


# A complete record, whatever the outcome


def test_a_ready_run_records_what_it_made_and_what_it_took(new_lesson, data_dir):
    run(data_dir, new_lesson, LoggingModel(happy_script()))
    [record] = run_log.read(data_dir)
    assert (record["start_stage"], record["rerun"], record["outcome"]) == (1, False, "ready")
    assert (record["failed_stage"], record["error"]) == (None, None)
    assert record["started"].startswith("20") and record["wall_ms"] >= 0
    normalized = data_dir / "work" / new_lesson / "normalized"
    assert record["material"] == {
        "files": [
            {"filename": "problem-set.md", "role": "problem_set", "force_transcription": False},
            {"filename": "reference.md", "role": "reference", "force_transcription": False},
        ],
        "pages_kept": 2,
        "pages_transcribed": 0,
        "normalized_chars": sum(len(path.read_text()) for path in normalized.iterdir()),
    }
    # The second solve disagreed on one of the three parts; the checkpoint was verified.
    assert record["lesson"] == {
        "id": new_lesson, "title": "Projectiles", "subject": "physics",
        "sections": 2, "blocks": 5, "problems": 2, "parts": 3, "verifiable": 4, "verified": 3,
    }
    assert groups(record) == [
        ("extract", "generate", SONNET, 1),
        ("plan", "generate", SONNET, 1),
        ("generate", "generate", SONNET, 4),
        ("generate", "small_check", HAIKU, 2),
        ("generate", "second_solve", OPUS, 2),
    ]
    solves = record["usage"][-1]
    assert (solves["latency_ms"], solves["input_tokens"], solves["output_tokens"]) == (4000, 2000, 200)
    assert (solves["cache_write_tokens"], solves["cache_read_tokens"], solves["unpriced"]) == (0, 0, 0)
    assert solves["cost"] == pytest.approx(2 * 0.006)
    assert record["prices"] == {
        model: {"input": p.input, "output": p.output, "cache_write": p.cache_write, "cache_read": p.cache_read}
        for model, p in MODEL_PRICES.items()
    }


def test_a_run_with_no_calls_still_leaves_a_record(new_lesson, data_dir):
    run(data_dir, new_lesson, FakeModel(happy_script()))
    [record] = run_log.read(data_dir)
    assert (record["outcome"], record["usage"], record["prices"]) == ("ready", [], {})


def test_a_run_that_fails_in_stage_1_has_no_pages_and_no_lesson(started, data_dir):
    _, create, _ = started
    lesson_id = scanned(create, pages=1)
    run(data_dir, lesson_id, LoggingModel(scanned_script(1, {Transcription: [{"markdown": None}] * 3})))
    [record] = run_log.read(data_dir)
    assert (record["outcome"], record["failed_stage"]) == ("failed", "ingest")
    assert record["error"].startswith("Transcription of scan.pdf page 1 failed after 3 attempts")
    assert [f["filename"] for f in record["material"]["files"]] == ["problem-set.md", "scan.pdf"]
    assert {record["material"][key] for key in ("pages_kept", "pages_transcribed", "normalized_chars")} == {None}
    assert record["lesson"] == {
        "id": lesson_id, "title": "New lesson", "subject": "physics",
        "sections": None, "blocks": None, "problems": None, "parts": None, "verifiable": None, "verified": None,
    }
    # Each rejected reply is billed, so it is counted.
    assert groups(record) == [("ingest", "transcribe", OPUS, 3)]


def test_a_run_that_fails_in_stage_2_keeps_its_pages(new_lesson, data_dir):
    bad = {"concepts": [], "problems": []}
    run(data_dir, new_lesson, LoggingModel(happy_script({ProblemsAndConcepts: [bad, bad, bad]})))
    [record] = run_log.read(data_dir)
    assert (record["outcome"], record["failed_stage"]) == ("failed", "extract")
    assert record["error"].startswith("Extraction failed after 3 attempts")
    assert (record["material"]["pages_kept"], record["material"]["pages_transcribed"]) == (2, 0)
    assert record["material"]["normalized_chars"] > 0
    assert (record["lesson"]["title"], record["lesson"]["sections"]) == ("New lesson", None)
    assert groups(record) == [("extract", "generate", SONNET, 3)]


def test_a_run_that_fails_in_stage_4_has_the_title_but_no_lesson(new_lesson, data_dir):
    declined = ModelError("The model declined this request.")
    run(data_dir, new_lesson, LoggingModel(happy_script({Solutions: [declined]})))
    [record] = run_log.read(data_dir)
    assert (record["outcome"], record["failed_stage"], record["error"]) == ("failed", "generate", str(declined))
    assert (record["lesson"]["title"], record["lesson"]["blocks"]) == ("Projectiles", None)
    assert [g[0] for g in groups(record)] == ["extract", "plan", "generate", "generate", "generate"]


def test_an_unexpected_error_is_recorded_as_shown(new_lesson, data_dir):
    run(data_dir, new_lesson, LoggingModel(happy_script({Plan: [RuntimeError("boom")]})))
    [record] = run_log.read(data_dir)
    assert (record["outcome"], record["failed_stage"], record["error"]) == ("failed", "plan", "Unexpected error: boom")
    assert record["error"] == lesson_status_error(data_dir, new_lesson)


def lesson_status_error(data_dir, lesson_id):
    with db.connect(data_dir) as conn:
        return conn.execute("SELECT error FROM lessons WHERE id = ?", (lesson_id,)).fetchone()["error"]


# Reruns


def test_each_run_adds_one_record_with_its_own_usage(new_lesson, data_dir):
    run(data_dir, new_lesson, LoggingModel(happy_script()))
    run(data_dir, new_lesson, LoggingModel(happy_script()), start_stage=3)
    first, second = run_log.read(data_dir)
    assert (first["start_stage"], first["rerun"]) == (1, False)
    assert (second["start_stage"], second["rerun"], second["outcome"]) == (3, True, "ready")
    assert [g[0] for g in groups(second)] == ["plan", "generate", "generate", "generate"]
    assert sum(u["calls"] for u in second["usage"]) == 9
    # Stages that were not redone still describe the material.
    assert second["material"] == first["material"]


def test_a_retry_from_a_later_stage_after_a_failure_is_not_a_rerun(new_lesson, data_dir):
    run(data_dir, new_lesson, LoggingModel(happy_script({Solutions: [ModelError("declined")]})))
    run(data_dir, new_lesson, LoggingModel(happy_script()), start_stage=4)
    failed, retried = run_log.read(data_dir)
    assert (failed["outcome"], retried["outcome"]) == ("failed", "ready")
    assert (retried["start_stage"], retried["rerun"]) == (4, False)
    assert [g[0] for g in groups(retried)] == ["generate"] * 3


def test_a_failed_rerun_does_not_borrow_the_earlier_run(started, data_dir):
    client, create, _ = started
    lesson_id = scanned(create, pages=1)
    run(data_dir, lesson_id, LoggingModel(scanned_script(1)))
    run(data_dir, lesson_id, LoggingModel(scanned_script(1, {Transcription: [{"markdown": None}] * 3})))
    ready, failed = run_log.read(data_dir)
    assert (ready["material"]["pages_transcribed"], ready["lesson"]["sections"]) == (1, 2)
    assert (failed["rerun"], failed["outcome"], failed["failed_stage"]) == (True, "failed", "ingest")
    # The earlier lesson is still served, but this run made none, and its stage 1 output is gone.
    assert lesson_status(client, lesson_id)["status"] == "ready"
    assert (failed["lesson"]["title"], failed["lesson"]["sections"]) == ("Projectiles", None)
    assert failed["material"]["pages_transcribed"] is None
    assert not failed["error"].startswith("The last rerun failed")


# Where it lives


def test_deleting_the_lesson_or_the_database_keeps_the_record(new_lesson, data_dir, started):
    client, _, _ = started
    run(data_dir, new_lesson, LoggingModel(happy_script()))
    assert client.delete(f"/lessons/{new_lesson}", headers=AUTH).status_code == 200
    db.db_path(data_dir).unlink()
    [record] = run_log.read(data_dir)
    assert record["lesson"]["id"] == new_lesson and sum(u["calls"] for u in record["usage"]) == 10


def test_a_record_that_cannot_be_written_does_not_fail_the_run(new_lesson, data_dir, started, caplog):
    client, _, _ = started
    run_log.path(data_dir).mkdir()
    run(data_dir, new_lesson, LoggingModel(happy_script()))
    assert lesson_status(client, new_lesson)["status"] == "ready"
    assert "run log" in caplog.text


def test_a_line_cut_short_is_skipped_and_does_not_swallow_the_next_record(new_lesson, data_dir):
    run_log.path(data_dir).write_text('{"started": "2026-10-11T00:00:00+00:00", "usage": [')
    run(data_dir, new_lesson, LoggingModel(happy_script()))
    [record] = run_log.read(data_dir)
    assert record["lesson"]["id"] == new_lesson


def test_no_file_means_no_runs(data_dir):
    assert run_log.read(data_dir) == []


# The code that ran


def test_the_record_names_the_commit_the_server_runs_from(new_lesson, data_dir, monkeypatch):
    monkeypatch.setattr(run_log, "code", run_log.Code(commit="abc1234", dirty=True))
    run(data_dir, new_lesson, FakeModel(happy_script()))
    [record] = run_log.read(data_dir)
    assert (record["commit"], record["dirty"]) == ("abc1234", True)


def test_the_commit_is_empty_when_git_was_not_read(new_lesson, data_dir):
    run(data_dir, new_lesson, FakeModel(happy_script()))
    [record] = run_log.read(data_dir)
    assert (record["commit"], record["dirty"]) == (None, None)
