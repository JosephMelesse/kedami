"""Turns the model's plan into sections with their target problems.

The model orders sections and assigns concepts; the server places problems, so the
sequencing rules in architecture/pipeline.md hold by construction:
- a concept is introduced before any problem that needs it,
- each problem appears in the section where its last prerequisite is covered,
- every problem appears exactly once.
"""

from dataclasses import dataclass

from ..ids import slugify
from .schemas import Concept, Extraction, ExtractedProblem, Plan


class PlanError(ValueError):
    pass


@dataclass(frozen=True)
class SectionPlan:
    id: str
    title: str
    goal: str
    concepts: list[Concept]
    problems: list[ExtractedProblem]


def place_problems(plan: Plan, extraction: Extraction) -> list[SectionPlan]:
    concepts = {c.id: c for c in extraction.concepts}
    section_of: dict[str, int] = {}
    for index, section in enumerate(plan.sections):
        for concept_id in section.concepts:
            if concept_id not in concepts:
                raise PlanError(f"section '{section.title}' introduces unknown concept '{concept_id}'")
            if concept_id in section_of:
                raise PlanError(f"concept '{concept_id}' is introduced in more than one section")
            section_of[concept_id] = index

    needed = {concept_id for problem in extraction.problems for concept_id in problem.concepts}
    missing = sorted(needed - section_of.keys())
    if missing:
        raise PlanError(f"these concepts are needed by problems but never introduced: {', '.join(missing)}")

    problems_in: list[list[ExtractedProblem]] = [[] for _ in plan.sections]
    for problem in extraction.problems:
        # A problem with no prerequisites goes in the first section.
        problems_in[max((section_of[c] for c in problem.concepts), default=0)].append(problem)

    sections = []
    used_ids: set[str] = set()
    for index, section in enumerate(plan.sections):
        if not section.concepts and not problems_in[index]:
            continue
        section_id = _unique(_slug_or(section.title, f"section-{index + 1}"), used_ids)
        sections.append(
            SectionPlan(
                id=section_id,
                title=section.title,
                goal=section.goal,
                concepts=[concepts[c] for c in section.concepts],
                problems=problems_in[index],
            )
        )
    return sections


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
