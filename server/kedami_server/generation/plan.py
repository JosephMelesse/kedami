"""Turns the model's plan into sections with their units and target problems.

The model orders sections and assigns units; the server checks the order and places problems, so the sequencing
rules in architecture/pipeline.md hold:
- every unit appears in exactly one section,
- within one file, units keep the order of the file,
- a unit comes before any problem that needs it, and each problem appears in the section of its last unit,
- every problem appears exactly once.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..ids import slugify
from .retry import Rejected
from .schemas import Extraction, ExtractedProblem, Plan, Unit

if TYPE_CHECKING:
    from .passages import Passage


class PlanError(Rejected):
    pass


@dataclass(frozen=True)
class SectionPlan:
    id: str
    title: str
    goal: str
    units: list[Unit]
    problems: list[ExtractedProblem]
    # A brief for the section's simulation, if the plan calls for one.
    simulation: str | None = None


def place_problems(plan: Plan, extraction: Extraction, passages: list[Passage]) -> list[SectionPlan]:
    units = {u.id: u for u in extraction.units}
    section_of: dict[str, int] = {}
    problems: list[str] = []
    for index, section in enumerate(plan.sections):
        for unit_id in section.units:
            if unit_id not in units:
                problems.append(f"section '{section.title}' has unknown unit '{unit_id}'")
            elif unit_id in section_of:
                problems.append(f"unit '{unit_id}' is in more than one section")
            else:
                section_of[unit_id] = index
    missing = [u.id for u in extraction.units if u.id not in section_of]
    if missing:
        problems.append(f"these units are in no section: {', '.join(missing)}")
    if problems:
        raise PlanError("\n".join(problems))
    _check_file_order([units[u] for section in plan.sections for u in section.units], passages)

    problems_in: list[list[ExtractedProblem]] = [[] for _ in plan.sections]
    for problem in extraction.problems:
        # A problem that needs no unit goes in the first section.
        problems_in[max((section_of[u] for u in problem.units), default=0)].append(problem)

    sections = []
    used_ids: set[str] = set()
    for index, section in enumerate(plan.sections):
        if not section.units and not problems_in[index]:
            continue
        section_id = _unique(_slug_or(section.title, f"section-{index + 1}"), used_ids)
        sections.append(
            SectionPlan(
                id=section_id,
                title=section.title,
                goal=section.goal,
                units=[units[u] for u in section.units],
                problems=problems_in[index],
                simulation=section.simulation,
            )
        )
    return sections


def _check_file_order(ordered: list[Unit], passages: list[Passage]) -> None:
    """Within one file, each unit must come after the one before it in the file. Files may alternate."""
    last_in: dict[str, Unit] = {}
    out_of_order = []
    for unit in ordered:
        file = passages[unit.first - 1].file
        before = last_in.get(file)
        if before is not None and unit.first < before.first:
            out_of_order.append(f"'{unit.id}' (p{unit.first}) comes after '{before.id}' (p{before.first})")
        last_in[file] = unit
    if out_of_order:
        raise PlanError(
            "within one file, units must keep the order of the file, but the plan puts "
            + "; ".join(out_of_order)
        )


def _slug_or(text: str, fallback: str) -> str:
    try:
        return slugify(text)
    except ValueError:
        return fallback


def _unique(base: str, used: set[str]) -> str:
    candidate, n = base, 2
    while candidate in used:
        candidate, n = f"{base}-{n}", n + 1
    used.add(candidate)
    return candidate
