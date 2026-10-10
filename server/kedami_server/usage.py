"""The usage log: what each model call took, recorded against its lesson.

See architecture/system.md, Usage log. Cost is an estimate from the list prices in config.
"""

import logging
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import db
from .config import MODEL_PRICES, ModelPrice

log = logging.getLogger(__name__)

# Pipeline stages 1 to 4, then the calls made on request.
STAGES = ("ingest", "extract", "plan", "generate", "solution", "simulation")
# The API may name a model by a dated snapshot of the ID that was requested.
DATE_SUFFIX = re.compile(r"-\d{8}$")


@dataclass(frozen=True)
class Tokens:
    # Uncached input, as the API reports it. Input, cache write, and cache read make up the prompt.
    input: int = 0
    output: int = 0
    cache_write: int = 0
    cache_read: int = 0

    def __add__(self, other: "Tokens") -> "Tokens":
        return Tokens(
            self.input + other.input,
            self.output + other.output,
            self.cache_write + other.cache_write,
            self.cache_read + other.cache_read,
        )


@dataclass(frozen=True)
class Totals:
    calls: int = 0
    latency_ms: int = 0
    tokens: Tokens = Tokens()
    cost: float = 0.0
    # Calls with no cost, because a model that ran them has no listed price.
    unpriced: int = 0

    def __add__(self, other: "Totals") -> "Totals":
        return Totals(
            self.calls + other.calls,
            self.latency_ms + other.latency_ms,
            self.tokens + other.tokens,
            self.cost + other.cost,
            self.unpriced + other.unpriced,
        )


@dataclass
class Recording:
    data_dir: Path
    lesson_id: str
    stage: str
    # What the calls made under this recording add up to so far.
    run: Totals = Totals()


_current: ContextVar[Recording | None] = ContextVar("usage_recording", default=None)


@contextmanager
def recording(data_dir: Path, lesson_id: str, stage: str) -> Iterator[Recording]:
    """Name the lesson and stage that model calls made inside the block belong to.

    Held per thread, so a generation run and requests for other lessons don't mix.
    """
    current = Recording(data_dir, lesson_id, stage)
    token = _current.set(current)
    try:
        yield current
    finally:
        _current.reset(token)


def set_stage(stage: str) -> None:
    current = _current.get()
    if current is not None:
        current.stage = stage


def measure(
    requested_model: str, reported: Any, prices: dict[str, ModelPrice] = MODEL_PRICES
) -> tuple[Tokens, float | None]:
    """The tokens a reply used and what they cost, with no cost if a model that ran has no listed price.

    When a declined request is re-run on a fallback model, the API lists each attempt and
    its top-level counts repeat only the last one. The attempts are added up, each at its
    own model's rate, and the top level is ignored.
    """
    attempts = [(getattr(a, "model", None) or requested_model, _tokens(a)) for a in reported.iterations or []]
    total, cost = Tokens(), 0.0
    for model, tokens in attempts or [(requested_model, _tokens(reported))]:
        total += tokens
        price = prices.get(model) or prices.get(DATE_SUFFIX.sub("", model))
        if price is None or cost is None:
            cost = None
            continue
        cost += (
            tokens.input * price.input
            + tokens.output * price.output
            + tokens.cache_write * price.cache_write
            + tokens.cache_read * price.cache_read
        ) / 1_000_000
    return total, cost


def _tokens(reported: Any) -> Tokens:
    return Tokens(
        input=reported.input_tokens or 0,
        output=reported.output_tokens or 0,
        cache_write=reported.cache_creation_input_tokens or 0,
        cache_read=reported.cache_read_input_tokens or 0,
    )


def record(role: str, requested_model: str, message: Any, started: str, seconds: float) -> None:
    """Log a reply against the lesson being worked on, if one is named.

    Never raises: a model call must not fail over its log entry.
    """
    current = _current.get()
    if current is None:
        return
    try:
        tokens, cost = measure(requested_model, message.usage)
        latency_ms = round(seconds * 1000)
        current.run += Totals(1, latency_ms, tokens, cost or 0.0, int(cost is None))
        log.info(
            "lesson %s %s %s (%s): %s", current.lesson_id, current.stage, role, message.model, _call(seconds, tokens, cost)
        )
        with db.connect(current.data_dir) as conn:
            conn.execute(
                "INSERT INTO model_calls (lesson_id, stage, role, model, started, latency_ms,"
                " input_tokens, output_tokens, cache_write_tokens, cache_read_tokens, cost)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    current.lesson_id,
                    current.stage,
                    role,
                    message.model,
                    started,
                    latency_ms,
                    tokens.input,
                    tokens.output,
                    tokens.cache_write,
                    tokens.cache_read,
                    cost,
                ),
            )
    except Exception as error:
        log.warning("usage: could not record a %s call for lesson %s: %s", role, current.lesson_id, error)


def by_stage(conn: sqlite3.Connection, lesson_id: str) -> dict[str, Totals]:
    """A lesson's totals per stage, over every run and on-request call, in stage order."""
    found = {
        row["stage"]: Totals(
            calls=row["calls"],
            latency_ms=row["latency_ms"],
            tokens=Tokens(row["input"], row["output"], row["cache_write"], row["cache_read"]),
            cost=row["cost"],
            unpriced=row["unpriced"],
        )
        for row in conn.execute(
            "SELECT stage, COUNT(*) AS calls, SUM(latency_ms) AS latency_ms, SUM(input_tokens) AS input,"
            " SUM(output_tokens) AS output, SUM(cache_write_tokens) AS cache_write,"
            " SUM(cache_read_tokens) AS cache_read, COALESCE(SUM(cost), 0.0) AS cost,"
            " SUM(cost IS NULL) AS unpriced"
            " FROM model_calls WHERE lesson_id = ? GROUP BY stage",
            (lesson_id,),
        )
    }
    return {stage: found[stage] for stage in STAGES if stage in found}


def describe(totals: Totals) -> str:
    if not totals.calls:
        return "no model calls"
    tokens = totals.tokens
    cost = f"${totals.cost:,.2f}"
    if totals.unpriced:
        cost += f" plus {_count(totals.unpriced)} with no listed price"
    return (
        f"{_count(totals.calls)}, {duration(totals.latency_ms / 1000)} of model time, "
        f"{tokens.input:,} input tokens, {tokens.cache_read:,} read from cache, "
        f"{tokens.cache_write:,} written to cache, {tokens.output:,} output tokens, {cost}"
    )


def _call(seconds: float, tokens: Tokens, cost: float | None) -> str:
    """One call as it happens: finer time and cost than a total needs."""
    return (
        f"{seconds:.1f}s, {tokens.input:,} input tokens, {tokens.cache_read:,} read from cache, "
        f"{tokens.cache_write:,} written to cache, {tokens.output:,} output tokens, "
        + ("no listed price" if cost is None else f"${cost:,.4f}")
    )


def duration(seconds: float) -> str:
    minutes, secs = divmod(round(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    return f"{minutes}m {secs:02d}s" if minutes else f"{secs}s"


def _count(calls: int) -> str:
    return f"{calls} call" if calls == 1 else f"{calls} calls"
