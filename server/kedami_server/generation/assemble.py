"""Builds lesson sections from the model's drafts.

Homework text comes from extraction, never from the section draft, so the problem a
student sees is the one in their problem set. Every check here raises SectionError,
which sends the section back to the model with the message.
"""

from pydantic import ValidationError

from ..ids import slugify
from ..lesson import ExternalAnswer, Lesson, Part, ProblemBlock, Section
from .plan import SectionPlan
from .schemas import ProblemDraft, SectionDraft, SimulationDraft


class SectionError(ValueError):
    pass


def assemble_section(plan: SectionPlan, draft: SectionDraft, externals: dict[str, ExternalAnswer] | None = None) -> Section:
    """Build a section. Problems in `externals` are solved elsewhere, so their parts get that answer."""
    externals = externals or {}
    targets = {slugify(p.source_ref): p for p in plan.problems}
    typed = [block.typed for block in draft.blocks]
    placed = [_problem_id(block) for block in typed if isinstance(block, ProblemDraft)]
    _check_problems(placed, targets)
    simulations = sum(isinstance(block, SimulationDraft) for block in typed)
    wanted = 1 if plan.simulation else 0
    if simulations != wanted:
        raise SectionError(f"this section needs exactly {wanted} simulation block(s); got {simulations}")

    blocks = []
    for index, block in enumerate(typed, start=1):
        if isinstance(block, ProblemDraft):
            problem_id = _problem_id(block)
            blocks.append(_problem(block, targets[problem_id], externals.get(problem_id)))
        elif isinstance(block, SimulationDraft):
            # The code is written on request, after the lesson is ready.
            blocks.append(
                {
                    "type": "simulation",
                    "id": f"{plan.id}-block-{index}",
                    "caption": block.caption,
                    "brief": plan.simulation,
                    "code": "",
                }
            )
        else:
            blocks.append({**block.model_dump(), "id": f"{plan.id}-block-{index}"})

    try:
        return Section.model_validate({"id": plan.id, "title": plan.title, "goal": plan.goal, "blocks": blocks})
    except ValidationError as error:
        raise SectionError(f"the section content is invalid: {error}") from error


def _problem_id(block: ProblemDraft) -> str:
    try:
        return slugify(block.source_ref)
    except ValueError as error:
        raise SectionError(f"unknown problem '{block.source_ref}'") from error


def _check_problems(placed: list[str], targets: dict) -> None:
    unknown = sorted(set(placed) - targets.keys())
    if unknown:
        raise SectionError(f"these problems don't belong in this section: {', '.join(unknown)}")
    repeated = sorted({p for p in placed if placed.count(p) > 1})
    if repeated:
        raise SectionError(f"each problem must appear once; repeated: {', '.join(repeated)}")
    missing = [targets[p].source_ref for p in targets if p not in placed]
    if missing:
        raise SectionError(f"these problems are missing from the section: {', '.join(missing)}")


def _problem(draft: ProblemDraft, extracted, external: ExternalAnswer | None = None) -> dict:
    if external is not None:
        # Solved on another site: every part takes that answer, whatever the draft gave.
        answers = {slugify(part.label): external for part in extracted.parts}
        return _problem_block(extracted, answers)
    answers = {}
    for part in draft.parts:
        try:
            answers[slugify(part.label)] = part.answer
        except ValueError as error:
            raise SectionError(f"{extracted.source_ref} has an unknown part label '{part.label}'") from error
    expected = [slugify(part.label) for part in extracted.parts]
    if sorted(answers) != sorted(expected) or len(draft.parts) != len(expected):
        given = ", ".join(part.label for part in draft.parts)
        wanted = ", ".join(part.label for part in extracted.parts)
        raise SectionError(f"{extracted.source_ref} needs one answer for each part ({wanted}); got: {given}")

    return _problem_block(extracted, answers)


def _problem_block(extracted, answers: dict) -> dict:
    block = ProblemBlock(
        type="problem",
        source_ref=extracted.source_ref,
        prompt=extracted.prompt,
        parts=[
            Part(label=part.label, prompt=part.prompt, answer=answers[slugify(part.label)], hints=[], verified=False)
            for part in extracted.parts
        ],
    )
    return block.model_dump()


def assemble_lesson(lesson_id: str, title: str, subject: str, source_files: list[str], sections: list[Section]) -> Lesson:
    return Lesson(
        schema_version=1,
        id=lesson_id,
        title=title,
        subject=subject,
        source_files=source_files,
        sections=sections,
    )
