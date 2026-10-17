"""Choosing practice exercises from the bank by SQL feature. See architecture/sql-lessons.md, In a lesson.

The plan says which SQL features each section teaches; this chooses the bank exercises. An exercise is
eligible for a section when it uses at least one feature the section teaches and none that isn't taught by
then. Selecting is taught from the start, since every query selects.
"""

from collections import defaultdict
from dataclasses import dataclass

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
