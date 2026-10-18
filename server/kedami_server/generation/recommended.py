"""The recommended problems of a SQL chapter lesson, parsed without the model.

The renderer writes them as the problem set, one per line: "1. spider:{exercise id} {question}" or
"2. pgexercises:{path} {title}", numbered from 1 in order. Blank lines, Markdown headings, and the page markers
added in stage 1 are ignored. Any other line, a gap in the numbers, a repeated problem, or an exercise or page
the server doesn't have is an error, so a list can't silently change. The text after the ID is for reading; the
bank's question and the page's title are what the lesson uses.

A Spider problem is a query answer on its bank database; a pgexercises problem is solved there and marked done.
See architecture/sql-lessons.md, In a lesson.
"""

import re
from dataclasses import dataclass

from ..ids import slugify
from ..lesson import ExternalAnswer, QueryAnswer
from ..practice import Exercise
from ..queries import is_ordered
from ..recommend import MAX_COUNT
from ..sql_chapters import page
from .leetcode import ProblemListError, check_covers
from .schemas import ConceptMap, ExtractedPart, ExtractedProblem, Extraction

_PROBLEM = re.compile(r"^(?P<number>\d{1,3})\.\s+(?P<source>spider|pgexercises):(?P<id>\S+)(?:\s+.*)?$")
_HEADING = re.compile(r"^#{1,6}\s+\D")
_PAGE_MARKER = re.compile(r"^\[.+, page \d+\]$")


@dataclass(frozen=True)
class RecommendedProblem:
    number: int
    text: str
    answer: QueryAnswer | ExternalAnswer

    @property
    def source_ref(self) -> str:
        return f"Problem {self.number}"


def parse_recommended(text: str, bank: list[Exercise]) -> list[RecommendedProblem]:
    exercises = {e.id: e for e in bank}
    problems: list[RecommendedProblem] = []
    errors: list[str] = []
    seen: dict[tuple[str, str], int] = {}
    # Numbered by line, so one bad line doesn't make every later number look wrong.
    expected = 0
    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or _HEADING.match(line) or _PAGE_MARKER.match(line):
            continue
        match = _PROBLEM.match(line)
        if not match:
            errors.append(f"line {line_number} isn't a recommended problem: {line!r}")
            continue
        number, source, key = int(match["number"]), match["source"], match["id"]
        expected += 1
        if number != expected:
            errors.append(f"line {line_number} is problem {number}, but the next problem is {expected}")
        elif (source, key) in seen:
            errors.append(f"line {line_number} repeats problem {seen[source, key]}")
        elif problem := _problem(number, source, key, exercises):
            seen[source, key] = number
            problems.append(problem)
        else:
            what = "exercise" if source == "spider" else "page"
            errors.append(f"line {line_number} names a {source} {what} Kedami doesn't have: {key!r}")
    if errors:
        shown = "; ".join(errors[:10]) + (f"; and {len(errors) - 10} more" if len(errors) > 10 else "")
        raise ProblemListError(f"The recommended problems can't be read: {shown}.")
    if not problems:
        raise ProblemListError("Recommend at least one problem.")
    if len(problems) > MAX_COUNT:
        raise ProblemListError(f"A chapter lesson takes at most {MAX_COUNT} problems.")
    return problems


def _problem(number: int, source: str, key: str, exercises: dict[str, Exercise]) -> RecommendedProblem | None:
    if source == "spider":
        exercise = exercises.get(key)
        if exercise is None:
            return None
        answer = QueryAnswer(
            kind="query",
            database=f"bank/{exercise.database}",
            reference=exercise.query,
            ordered=is_ordered(exercise.query),
            exercise=exercise.id,
        )
        return RecommendedProblem(number, exercise.question, answer)
    found = page(key)
    if found is None:
        return None
    answer = ExternalAnswer(kind="external", platform="pgexercises", path=found.path, title=found.title)
    return RecommendedProblem(number, f'Solve "{found.title}" on pgexercises.', answer)


def bank_databases(problems: list[RecommendedProblem]) -> list[str]:
    """The bank databases the problems use, each once, in the order they first come up."""
    names = [p.answer.database for p in problems if isinstance(p.answer, QueryAnswer)]
    return list(dict.fromkeys(names))


def build_extraction(problems: list[RecommendedProblem], concept_map: ConceptMap) -> Extraction:
    """The stage 2 output for a chapter lesson: the recommended problems, with the model's concepts.

    Raises ConceptMapError if the model didn't cover every problem exactly once.
    """
    check_covers({p.number for p in problems}, concept_map)
    concepts_for = {p.number: p.concepts for p in concept_map.problems}
    extracted = [
        ExtractedProblem(
            source_ref=p.source_ref,
            prompt="",
            parts=[ExtractedPart(label=str(p.number), prompt=p.text)],
            concepts=concepts_for[p.number],
        )
        for p in problems
    ]
    answers = {slugify(p.source_ref): p.answer for p in problems}
    return Extraction(concepts=concept_map.concepts, problems=extracted, answers=answers)
