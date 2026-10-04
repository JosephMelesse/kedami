"""The LeetCode problem list of a computer science lesson, parsed without the model.

One problem per line, with its number and title: "1. Two Sum", "#15 3Sum", "LeetCode 70 -
Climbing Stairs", "- 1. Two Sum". Blank lines, Markdown headings, and the page markers
added in stage 1 are ignored. Any other line, a missing title, or a repeated number is an
error, so a typo can't silently become the wrong problem.
"""

import re
from dataclasses import dataclass

from ..ids import slugify
from ..lesson import ExternalAnswer
from .schemas import ConceptMap, ExtractedPart, ExtractedProblem, Extraction

MAX_TITLE = 200

_PROBLEM = re.compile(
    r"^(?:[-*+]\s+)?(?:leetcode\s*)?#?\s*(?P<number>\d{1,5})(?:\s*[.):-]\s*|\s+|$)(?P<title>.*)$", re.IGNORECASE
)
_HEADING = re.compile(r"^#{1,6}\s+\D")
_PAGE_MARKER = re.compile(r"^\[.+, page \d+\]$")


class ProblemListError(ValueError):
    """A problem list that can't be read, with a message fit to show the student."""


@dataclass(frozen=True)
class ListedProblem:
    number: int
    title: str

    @property
    def slug(self) -> str:
        return leetcode_slug(self.title)

    @property
    def source_ref(self) -> str:
        return f"LeetCode #{self.number}"


def leetcode_slug(title: str) -> str:
    """LeetCode's URL slug for a title: "Pow(x, n)" becomes "powx-n"."""
    kept = re.sub(r"[^a-z0-9 -]", "", title.lower())
    slug = re.sub(r"-+", "-", re.sub(r"\s+", "-", kept.strip())).strip("-")
    if not slug:
        raise ProblemListError(f"the title {title!r} has no letters or digits")
    return slug


def parse_problem_list(text: str) -> list[ListedProblem]:
    problems: list[ListedProblem] = []
    errors: list[str] = []
    seen: dict[int, int] = {}
    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or _HEADING.match(line) or _PAGE_MARKER.match(line):
            continue
        match = _PROBLEM.match(line)
        if not match:
            errors.append(f"line {line_number} isn't a problem number and title: {line!r}")
            continue
        number, title = int(match["number"]), match["title"].strip()
        if number < 1:
            errors.append(f"line {line_number} has no problem number above 0: {line!r}")
        elif not title:
            errors.append(f"line {line_number} has a number but no title: {line!r}")
        elif len(title) > MAX_TITLE:
            errors.append(f"line {line_number} has a title longer than {MAX_TITLE} characters")
        elif number in seen:
            errors.append(f"line {line_number} repeats problem {number} from line {seen[number]}")
        else:
            try:
                leetcode_slug(title)
            except ProblemListError as error:
                errors.append(f"line {line_number}: {error}")
                continue
            seen[number] = line_number
            problems.append(ListedProblem(number, title))
    if errors:
        shown = "; ".join(errors[:10]) + (f"; and {len(errors) - 10} more" if len(errors) > 10 else "")
        raise ProblemListError(f"The LeetCode problem list has problems: {shown}.")
    if not problems:
        raise ProblemListError("The LeetCode problem list is empty. List one problem per line, such as '1. Two Sum'.")
    return problems


def build_extraction(listed: list[ListedProblem], concept_map: ConceptMap) -> Extraction:
    """The stage 2 output for a computer science lesson: the listed problems, with the model's concepts.

    Raises ConceptMapError if the model didn't cover every listed problem exactly once.
    """
    numbers = [p.number for p in concept_map.problems]
    listed_numbers = {p.number for p in listed}
    repeated = sorted({n for n in numbers if numbers.count(n) > 1})
    unknown = sorted(set(numbers) - listed_numbers)
    missing = sorted(listed_numbers - set(numbers))
    problems_found = []
    if repeated:
        problems_found.append(f"problems listed more than once: {', '.join(map(str, repeated))}")
    if unknown:
        problems_found.append(f"problems that aren't in the list: {', '.join(map(str, unknown))}")
    if missing:
        problems_found.append(f"problems missing: {', '.join(map(str, missing))}")
    if problems_found:
        raise ConceptMapError("Map every listed problem exactly once; " + "; ".join(problems_found))

    concepts_for = {p.number: p.concepts for p in concept_map.problems}
    problems = [
        ExtractedProblem(
            source_ref=p.source_ref,
            prompt="",
            parts=[ExtractedPart(label=str(p.number), prompt=f"Complete LeetCode #{p.number}: {p.title}.")],
            concepts=concepts_for[p.number],
        )
        for p in listed
    ]
    externals = {
        slugify(p.source_ref): ExternalAnswer(
            kind="external", platform="leetcode", number=p.number, title=p.title, slug=p.slug
        )
        for p in listed
    }
    return Extraction(concepts=concept_map.concepts, problems=problems, externals=externals)


class ConceptMapError(ValueError):
    """A concept map that doesn't cover the listed problems; sent back to the model."""
