"""Recommending problems for one SQL chapter. See architecture/sql-lessons.md, Recommending problems."""

from collections import defaultdict
from dataclasses import dataclass

from .practice import Exercise
from .sql_chapters import Chapter, known_features

MIN_COUNT = 1
MAX_COUNT = 10
DEFAULT_COUNT = 5


@dataclass(frozen=True)
class Recommendation:
    source: str  # "spider" or "pgexercises"
    id: str  # a Spider exercise's ID, or a pgexercises page's path
    text: str
    database: str | None = None


def eligible(bank: list[Exercise], chapter: Chapter) -> list[Exercise]:
    """Spider exercises that use one of the chapter's features and none from a later chapter."""
    known = known_features(chapter.number)
    return [e for e in bank if e.features & chapter.features and e.features <= known]


def available(bank: list[Exercise], chapter: Chapter) -> int:
    """How many problems the chapter can recommend in all."""
    return len(chapter.pages) if chapter.pages else len(eligible(bank, chapter))


def recommend(bank: list[Exercise], chapter: Chapter, count: int, round_: int = 0) -> list[Recommendation]:
    """Up to `count` problems for the chapter. `round_` is how many times Recommend again was pressed."""
    count = max(MIN_COUNT, min(MAX_COUNT, count))
    if chapter.pages:
        return [Recommendation("pgexercises", p.path, p.title) for p in chapter.pages[:count]]

    by_database: dict[str, list[Exercise]] = defaultdict(list)
    for exercise in sorted(eligible(bank, chapter), key=lambda e: (len(e.features), e.id)):
        by_database[exercise.database].append(exercise)
    # Most eligible problems first, so a lesson's problems share as few sets of tables as possible.
    databases = sorted(by_database, key=lambda db: (-len(by_database[db]), db))
    if not databases:
        return []
    start = round_ % len(databases)
    picks: list[Exercise] = []
    for database in databases[start:] + databases[:start]:
        picks += by_database[database][: count - len(picks)]
        if len(picks) == count:
            break
    return [Recommendation("spider", e.id, e.question, e.database) for e in picks]
