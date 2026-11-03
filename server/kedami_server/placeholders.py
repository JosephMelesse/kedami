"""Reading a pasted list of placeholder lessons. See Placeholder lessons in architecture/ui.md."""

from dataclasses import dataclass

from .deadlines import parse_due_date

MAX_NAME = 120
MAX_LINES = 100
# Enough for the longest list; anything past it is refused before it is read.
MAX_LIST_TEXT = 100_000


@dataclass(frozen=True)
class PlannedLesson:
    name: str
    due_date: str | None = None


@dataclass(frozen=True)
class ListProblem:
    # 1 for the first line, counting blank ones, so it matches the text the student sees. 0 for the list as a whole.
    line: int
    text: str
    reason: str


def _parse_line(line: str) -> PlannedLesson:
    """A line as `Name` or `Name | YYYY-MM-DD`. Raises ValueError with why it can't be read."""
    pieces = line.split("|")
    if len(pieces) > 2:
        raise ValueError("It has more than one |.")
    name = pieces[0].strip()
    if not name:
        raise ValueError("It has no name.")
    if len(name) > MAX_NAME:
        raise ValueError(f"Its name is over {MAX_NAME} characters.")
    if len(pieces) == 1:
        return PlannedLesson(name)
    date = pieces[1].strip()
    if not date:
        raise ValueError("It has a | with no date after it.")
    try:
        return PlannedLesson(name, parse_due_date(date))
    except ValueError:
        raise ValueError(f"{date} isn't a real date written YYYY-MM-DD.") from None


def parse_list(text: str) -> tuple[list[PlannedLesson], list[ListProblem]]:
    """The placeholders in a pasted list, or none and every problem: one bad line rejects the whole list."""
    planned: list[PlannedLesson] = []
    problems: list[ListProblem] = []
    for number, line in enumerate(text.removeprefix("﻿").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            planned.append(_parse_line(line))
        except ValueError as error:
            problems.append(ListProblem(number, line.strip(), str(error)))
    if not planned and not problems:
        problems.append(ListProblem(0, "", "The list is empty."))
    if len(planned) + len(problems) > MAX_LINES:
        problems.append(ListProblem(0, "", f"A list can have at most {MAX_LINES} placeholders."))
    return ([] if problems else planned), problems
