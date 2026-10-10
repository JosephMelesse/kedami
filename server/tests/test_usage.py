import json
import threading
from types import SimpleNamespace

import pytest

from kedami_server import db, library, model, usage
from kedami_server.config import MODEL_PRICES, MODEL_ROLES, ModelPrice
from kedami_server.model import ModelError, ValidationError, call_model
from kedami_server.usage import Tokens, Totals

from .test_model import GOOD, Reply, api, sse  # noqa: F401  (api is a fixture)

SONNET, OPUS, HAIKU = "claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-4-5"


def reported(input=0, output=0, cache_write=None, cache_read=None, iterations=None):
    """Usage as the API reports it at the top level of a message."""
    return SimpleNamespace(
        input_tokens=input,
        output_tokens=output,
        cache_creation_input_tokens=cache_write,
        cache_read_input_tokens=cache_read,
        iterations=iterations,
    )


def attempt(kind, model, input=0, output=0, cache_write=0, cache_read=0):
    return SimpleNamespace(
        type=kind,
        model=model,
        input_tokens=input,
        output_tokens=output,
        cache_creation_input_tokens=cache_write,
        cache_read_input_tokens=cache_read,
    )


def message(usage_, model_=SONNET):
    return SimpleNamespace(model=model_, usage=usage_)


@pytest.fixture
def data_dir(tmp_path):
    db.init(tmp_path)
    with db.connect(tmp_path) as conn:
        for lesson_id in ("first", "second"):
            library.create_generating(conn, lesson_id, "physics", 1)
    return tmp_path


def rows(data_dir, lesson_id=None):
    with db.connect(data_dir) as conn:
        found = conn.execute("SELECT * FROM model_calls ORDER BY id").fetchall()
    return [dict(r) for r in found if lesson_id in (None, r["lesson_id"])]


# Tokens and cost


def test_every_role_has_a_price():
    assert {role.model for role in MODEL_ROLES.values()} <= set(MODEL_PRICES)


def test_each_kind_of_token_has_its_own_rate():
    tokens, cost = usage.measure(SONNET, reported(input=1_000_000, output=100_000, cache_write=200_000, cache_read=3_000_000))
    assert tokens == Tokens(input=1_000_000, output=100_000, cache_write=200_000, cache_read=3_000_000)
    # 2.00 + 1.00 + 0.50 + 0.60
    assert cost == pytest.approx(4.10)


def test_cached_tokens_are_not_also_charged_as_input():
    _, cost = usage.measure(OPUS, reported(input=0, output=0, cache_read=1_000_000))
    assert cost == pytest.approx(0.20)


def test_missing_cache_counts_are_zero():
    tokens, cost = usage.measure(HAIKU, reported(input=10, output=20))
    assert tokens == Tokens(input=10, output=20)
    assert cost == pytest.approx((10 * 1.00 + 20 * 5.00) / 1_000_000)


def test_no_tokens_cost_nothing():
    assert usage.measure(SONNET, reported()) == (Tokens(), 0.0)


def test_a_fallback_is_priced_per_attempt_and_counted_once():
    declined = attempt("message", SONNET, input=1_000_000, output=10_000)
    served = attempt("fallback_message", OPUS, input=1_000_000, output=100_000, cache_write=50_000)
    # The top level repeats the serving attempt; adding it again would double the bill.
    top = reported(input=1_000_000, output=100_000, cache_write=50_000, iterations=[declined, served])
    tokens, cost = usage.measure(SONNET, top)
    assert tokens == Tokens(input=2_000_000, output=110_000, cache_write=50_000)
    # Sonnet 2.00 + 0.10, then Opus 4.00 + 2.00 + 0.25
    assert cost == pytest.approx(8.35)


def test_a_single_attempt_listed_on_its_own_matches_the_top_level():
    top = reported(input=500, output=70, cache_read=900)
    listed = reported(input=500, output=70, cache_read=900, iterations=[attempt("message", SONNET, 500, 70, 0, 900)])
    assert usage.measure(SONNET, listed) == usage.measure(SONNET, top)


def test_an_attempt_that_names_no_model_is_priced_as_the_requested_one():
    top = reported(iterations=[attempt("message", None, input=1_000_000)])
    assert usage.measure(HAIKU, top)[1] == pytest.approx(1.00)


def test_an_empty_list_of_attempts_falls_back_to_the_top_level():
    assert usage.measure(SONNET, reported(input=1_000_000, iterations=[]))[1] == pytest.approx(2.00)


def test_a_dated_model_id_is_priced_as_its_alias():
    top = reported(iterations=[attempt("message", "claude-haiku-4-5-20251001", input=1_000_000)])
    assert usage.measure(HAIKU, top)[1] == pytest.approx(1.00)


def test_a_model_with_no_price_leaves_the_cost_empty_but_keeps_the_tokens():
    declined = attempt("message", SONNET, input=1_000, output=10)
    served = attempt("fallback_message", "claude-unlisted-9", input=1_000, output=500)
    tokens, cost = usage.measure(SONNET, reported(iterations=[declined, served]))
    assert tokens == Tokens(input=2_000, output=510)
    assert cost is None
    assert usage.measure("claude-unlisted-9", reported(input=5))[1] is None


def test_prices_can_be_swapped_without_touching_the_arithmetic():
    prices = {"m": ModelPrice(input=1, output=2, cache_write=3, cache_read=4)}
    top = reported(input=1_000_000, output=1_000_000, cache_write=1_000_000, cache_read=1_000_000)
    assert usage.measure("m", top, prices)[1] == pytest.approx(10)


# Recording


def test_a_call_outside_a_lesson_is_not_recorded(data_dir):
    usage.record("generate", SONNET, message(reported(input=5)), "2026-10-10T00:00:00+00:00", 1.0)
    assert rows(data_dir) == []


def test_a_call_is_recorded_against_the_named_lesson_and_stage(data_dir):
    with usage.recording(data_dir, "first", "extract") as recorded:
        usage.record("generate", SONNET, message(reported(input=1_000_000, output=7, cache_read=3)), "t0", 2.3456)
    [row] = rows(data_dir)
    assert {k: row[k] for k in ("lesson_id", "stage", "role", "model", "started", "latency_ms")} == {
        "lesson_id": "first", "stage": "extract", "role": "generate", "model": SONNET, "started": "t0", "latency_ms": 2346,
    }
    assert (row["input_tokens"], row["output_tokens"], row["cache_write_tokens"], row["cache_read_tokens"]) == (1_000_000, 7, 0, 3)
    assert row["cost"] == pytest.approx(2.00 + 7 * 10 / 1e6 + 3 * 0.20 / 1e6)
    assert recorded.run.calls == 1 and recorded.run.cost == pytest.approx(row["cost"])


def test_the_stage_follows_the_run(data_dir):
    with usage.recording(data_dir, "first", "ingest"):
        usage.record("transcribe", OPUS, message(reported(input=1)), "t", 0)
        usage.set_stage("plan")
        usage.record("generate", SONNET, message(reported(input=1)), "t", 0)
    assert [r["stage"] for r in rows(data_dir)] == ["ingest", "plan"]


def test_recording_ends_with_its_block_even_on_an_error(data_dir):
    with pytest.raises(RuntimeError):
        with usage.recording(data_dir, "first", "plan"):
            raise RuntimeError
    usage.record("generate", SONNET, message(reported(input=5)), "t", 0)
    usage.set_stage("generate")  # nothing to set, and no error
    assert rows(data_dir) == []


def test_the_row_names_the_model_that_answered(data_dir):
    with usage.recording(data_dir, "first", "generate"):
        usage.record("generate", SONNET, message(reported(input=5), model_=OPUS), "t", 0)
    assert rows(data_dir)[0]["model"] == OPUS


def test_calls_made_at_the_same_time_reach_their_own_lessons(data_dir):
    """A generation thread and requests for other lessons record side by side."""
    ready = threading.Barrier(3)

    def work(lesson_id, stage, count):
        with usage.recording(data_dir, lesson_id, stage):
            ready.wait()
            for _ in range(count):
                usage.record("generate", SONNET, message(reported(input=1)), "t", 0)

    def unnamed():
        ready.wait()
        usage.record("generate", SONNET, message(reported(input=1)), "t", 0)

    threads = [
        threading.Thread(target=work, args=("first", "generate", 20)),
        threading.Thread(target=work, args=("second", "solution", 15)),
        threading.Thread(target=unnamed),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert {r["stage"] for r in rows(data_dir, "first")} == {"generate"} and len(rows(data_dir, "first")) == 20
    assert {r["stage"] for r in rows(data_dir, "second")} == {"solution"} and len(rows(data_dir, "second")) == 15


def test_a_call_for_a_deleted_lesson_is_dropped_without_failing(data_dir, caplog):
    with db.connect(data_dir) as conn:
        library.delete_lesson(conn, "first")
    with usage.recording(data_dir, "first", "solution") as recorded:
        usage.record("solution", OPUS, message(reported(input=5)), "t", 0)
    assert rows(data_dir) == []
    assert recorded.run.calls == 1
    assert "usage" in caplog.text


def test_a_reply_with_unreadable_usage_is_dropped_without_failing(data_dir, caplog):
    with usage.recording(data_dir, "first", "generate"):
        usage.record("generate", SONNET, SimpleNamespace(model=SONNET, usage=None), "t", 0)
    assert rows(data_dir) == []
    assert "usage" in caplog.text


def test_deleting_a_lesson_deletes_its_rows_only(data_dir):
    for lesson_id in ("first", "second"):
        with usage.recording(data_dir, lesson_id, "generate"):
            usage.record("generate", SONNET, message(reported(input=1)), "t", 0)
    with db.connect(data_dir) as conn:
        library.delete_lesson(conn, "first")
    assert [r["lesson_id"] for r in rows(data_dir)] == ["second"]


def test_an_existing_database_gains_the_table(tmp_path):
    db.init(tmp_path)
    with db.connect(tmp_path) as conn:
        conn.execute("DROP TABLE model_calls")
    db.init(tmp_path)
    with db.connect(tmp_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM model_calls").fetchone()[0] == 0


# Through the model function


def test_a_model_call_records_its_tokens(api, data_dir):
    with usage.recording(data_dir, "first", "plan"):
        call_model("generate", system="s", prompt="p", output=Reply)
    [row] = rows(data_dir)
    assert (row["role"], row["stage"], row["model"]) == ("generate", "plan", "m")
    assert row["latency_ms"] >= 0
    # The fake API reports 1 input token at the start and 5 output tokens at the end.
    assert (row["input_tokens"], row["output_tokens"]) == (1, 5)
    assert row["cost"] == pytest.approx((1 * 2.00 + 5 * 10.00) / 1e6)
    assert row["started"].startswith("20")


def test_fallback_attempts_reported_by_the_api_are_priced_per_attempt(api, data_dir):
    counts = {"cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    attempts = [
        {"type": "message", "model": SONNET, "input_tokens": 1000, "output_tokens": 0, **counts},
        {"type": "fallback_message", "model": OPUS, "input_tokens": 1000, "output_tokens": 500, **counts},
    ]
    final = json.dumps({"output_tokens": 500, "iterations": attempts})
    api.body = sse(json.dumps(GOOD)).replace(json.dumps({"output_tokens": 5}), final)
    assert final in api.body
    with usage.recording(data_dir, "first", "generate"):
        call_model("generate", system="s", prompt="p", output=Reply)
    [row] = rows(data_dir)
    assert (row["input_tokens"], row["output_tokens"]) == (2000, 500)
    assert row["cost"] == pytest.approx((1000 * 2.00 + 1000 * 4.00 + 500 * 20.00) / 1e6)


def test_a_rejected_reply_is_still_recorded(api, data_dir):
    api.body = sse(json.dumps({"answer": {"kind": "choice", "options": ["a", "b"], "correct_index": 5}}))
    with usage.recording(data_dir, "first", "generate"), pytest.raises(ValidationError):
        call_model("generate", system="s", prompt="p", output=Reply)
    assert len(rows(data_dir)) == 1


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_a_declined_or_cut_off_reply_is_still_recorded(api, data_dir, stop_reason):
    api.body = sse(json.dumps(GOOD), stop_reason)
    with usage.recording(data_dir, "first", "generate"), pytest.raises(ModelError):
        call_model("generate", system="s", prompt="p", output=Reply)
    assert len(rows(data_dir)) == 1


def test_an_api_error_records_nothing(api, data_dir):
    api.status = 400
    with usage.recording(data_dir, "first", "generate"), pytest.raises(ModelError):
        call_model("generate", system="s", prompt="p", output=Reply)
    assert rows(data_dir) == []


def test_the_time_includes_waits_for_a_temporary_failure(api, data_dir, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(model.time, "monotonic", lambda: clock[0])

    def sleep(seconds):
        clock[0] += seconds
        api.status = 200

    monkeypatch.setattr(model.time, "sleep", sleep)
    api.status = 529
    with usage.recording(data_dir, "first", "generate"):
        call_model("generate", system="s", prompt="p", output=Reply)
    [row] = rows(data_dir)
    assert row["latency_ms"] == 5000


# Totals


def test_totals_add_up_per_stage_and_across_runs(data_dir):
    calls = [("extract", SONNET, 100, 10, 1.0), ("generate", SONNET, 200, 20, 2.0), ("generate", HAIKU, 50, 5, 0.5)]
    for _run in range(2):
        with usage.recording(data_dir, "first", "ingest"):
            for stage, model_, input_, output, seconds in calls:
                usage.set_stage(stage)
                usage.record("generate", model_, message(reported(input=input_, output=output)), "t", seconds)
    with usage.recording(data_dir, "first", "solution"):
        usage.record("solution", "claude-unlisted-9", message(reported(input=7)), "t", 0.25)

    with db.connect(data_dir) as conn:
        stages = usage.by_stage(conn, "first")
        assert usage.by_stage(conn, "second") == {}
    assert list(stages) == ["extract", "generate", "solution"]
    assert stages["generate"] == Totals(
        calls=4, latency_ms=5000, tokens=Tokens(input=500, output=50),
        cost=pytest.approx(2 * (200 * 2 + 20 * 10 + 50 * 1 + 5 * 5) / 1e6), unpriced=0,
    )
    assert stages["solution"] == Totals(calls=1, latency_ms=250, tokens=Tokens(input=7), cost=0.0, unpriced=1)
    whole = sum(stages.values(), Totals())
    assert (whole.calls, whole.latency_ms, whole.tokens.input, whole.unpriced) == (7, 7250, 707, 1)


def test_describe_reads_as_one_line():
    totals = Totals(
        calls=47, latency_ms=842_400, tokens=Tokens(input=1_840_123, output=212_004, cache_write=98_000, cache_read=1_610_000),
        cost=4.3712, unpriced=0,
    )
    assert usage.describe(totals) == (
        "47 calls, 14m 02s of model time, 1,840,123 input tokens, 1,610,000 read from cache, "
        "98,000 written to cache, 212,004 output tokens, $4.37"
    )
    one = Totals(calls=1, latency_ms=900, tokens=Tokens(input=1), cost=0.0, unpriced=1)
    assert usage.describe(one) == (
        "1 call, 1s of model time, 1 input tokens, 0 read from cache, 0 written to cache, 0 output tokens, "
        "$0.00 plus 1 call with no listed price"
    )
    assert usage.describe(Totals()) == "no model calls"


@pytest.mark.parametrize("seconds, text", [(0.4, "0s"), (59.6, "1m 00s"), (61, "1m 01s"), (3725, "1h 02m 05s")])
def test_durations(seconds, text):
    assert usage.duration(seconds) == text
