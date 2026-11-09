"""Units: the reference cut into runs of passages, each teaching one idea. See Stage 2 in architecture/pipeline.md.

The model names a unit by its first and last passage numbers. These checks make sure the cut covers the reference:
every shown passage is in exactly one unit or skipped range, and a unit stays in one file. The server then cuts
the text, so a unit can't differ from the reference.
"""

from collections.abc import Iterable

from .passages import NOTE, TEXT, Passage
from .retry import Rejected
from .schemas import Extraction, PassageRange, Unit

# Passages a student sees, which a unit or skipped range must account for. A note is read by the model only.
SHOWN = (TEXT,)


class UnitError(Rejected):
    """A cut of the reference that doesn't fit its passages. The reply is sent back with the reason."""


def check_units(extraction: Extraction, passages: list[Passage]) -> None:
    """Raise UnitError listing every problem with the cut, so one retry can fix them all."""
    count = len(passages)
    problems: list[str] = []
    ranges: list[tuple[str, PassageRange]] = [(f"unit {u.id}", u) for u in extraction.units]
    ranges += [(f"skipped range {i}", s) for i, s in enumerate(extraction.skipped, start=1)]

    for name, span in ranges:
        if span.first > span.last:
            problems.append(f"{name} starts at p{span.first} after it ends at p{span.last}")
        elif span.first < 1 or span.last > count:
            problems.append(f"{name} (p{span.first}-p{span.last}) is outside the passages, p1-p{count}")
    if problems:
        raise UnitError(_listed(problems))

    for unit in extraction.units:
        inside = passages_of(unit, passages)
        files = list(dict.fromkeys(p.file for p in inside))
        if len(files) > 1:
            problems.append(f"unit {unit.id} runs across files ({', '.join(files)}); a unit stays in one file")
        if not any(p.kind in SHOWN for p in inside):
            problems.append(f"unit {unit.id} holds no text, only figure notes")

    holders: dict[int, list[str]] = {}
    for name, span in ranges:
        for number in range(span.first, span.last + 1):
            holders.setdefault(number, []).append(name)
    shown = [p.number for p in passages if p.kind in SHOWN]
    missing = [n for n in shown if n not in holders]
    if missing:
        problems.append(f"these passages are in no unit or skipped range: {_spans(missing)}")
    for number in shown:
        if len(holders.get(number, [])) > 1:
            problems.append(f"p{number} is in more than one place: {', '.join(holders[number])}")
    if problems:
        raise UnitError(_listed(problems))


def passages_of(span: PassageRange, passages: list[Passage]) -> list[Passage]:
    """The passages a unit or skipped range covers. Passage numbers start at 1 and run without gaps."""
    return passages[span.first - 1 : span.last]


def skipped_passages(extraction: Extraction, passages: list[Passage]) -> int:
    """How many shown passages the cut leaves out of the lesson."""
    return sum(p.kind in SHOWN for span in extraction.skipped for p in passages_of(span, passages))


def source_runs(unit: Unit, passages: list[Passage]) -> list[list[Passage]]:
    """A unit as the runs of passages that each become one source block. A note isn't shown, so it ends no run."""
    runs: list[list[Passage]] = []
    current: list[Passage] = []
    for passage in passages_of(unit, passages):
        if passage.kind == TEXT:
            current.append(passage)
        elif passage.kind != NOTE and current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    return runs


def _listed(problems: Iterable[str]) -> str:
    return "the units don't fit the passages:\n" + "\n".join(f"- {problem}" for problem in problems)


def _spans(numbers: list[int]) -> str:
    """1, 2, 3, 7 as p1-p3, p7."""
    spans: list[list[int]] = []
    for number in numbers:
        if spans and spans[-1][1] + 1 == number:
            spans[-1][1] = number
        else:
            spans.append([number, number])
    return ", ".join(f"p{a}" if a == b else f"p{a}-p{b}" for a, b in spans)
