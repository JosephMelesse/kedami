"""Choosing practice exercises from the bank by SQL feature. See architecture/sql-lessons.md, In a lesson.

The plan says which SQL features each section teaches; this chooses the bank exercises. An exercise is
eligible for a section when it uses at least one feature the section teaches and none that isn't taught by
then. Selecting is taught from the start, since every query selects.
"""

import json
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PER_SECTION = 3


@dataclass(frozen=True)
class Exercise:
    id: str
    database: str
    question: str
    query: str
    features: frozenset[str]


def choose(bank: list[Exercise], sections: list[set[str]], per_section: int = PER_SECTION) -> list[list[Exercise]]:
    """For each section in order, up to `per_section` exercises. Fewer features come first, a section's come
    from one database where possible, and no exercise is chosen twice."""
    taught = {"selecting"}
    used: set[str] = set()
    chosen = []
    for teaches in sections:
        taught |= teaches
        eligible = sorted(
            (e for e in bank if e.id not in used and e.features & teaches and e.features <= taught),
            key=lambda e: (len(e.features), e.id),
        )
        picks = _mostly_one_database(eligible, per_section)
        used |= {e.id for e in picks}
        chosen.append(picks)
    return chosen


def _mostly_one_database(eligible: list[Exercise], count: int) -> list[Exercise]:
    """The first `count` from the database with the most eligible exercises, so a section's practice shares one
    set of tables, then the next eligible from other databases if that one runs short."""
    if not eligible:
        return []
    by_database: dict[str, list[Exercise]] = defaultdict(list)
    for exercise in eligible:
        by_database[exercise.database].append(exercise)
    best = min(by_database, key=lambda db: (-len(by_database[db]), db))
    picks = by_database[best][:count]
    return picks + [e for e in eligible if e.database != best][: count - len(picks)]


BANK_FILE = Path("sql") / "exercises.jsonl"


def load_bank(data_dir: Path) -> list[Exercise]:
    """The imported exercise bank, kept in memory until the file changes. Empty if nothing is imported."""
    path = data_dir / BANK_FILE
    try:
        stat = path.stat()
    except FileNotFoundError:
        return []
    return _load(path, stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=4)
def _load(path: Path, mtime_ns: int, size: int) -> list[Exercise]:
    bank = []
    with path.open(encoding="utf-8") as lines:
        for line in lines:
            e = json.loads(line)
            bank.append(Exercise(e["id"], e["database"], e["question"], e["query"], frozenset(e["features"])))
    return bank
