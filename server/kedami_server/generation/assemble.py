"""Builds lesson sections from the model's drafts.

Homework text comes from extraction and reference text from the passages, never from the
section draft, so what a student reads is their course material, word for word. Every
check here raises SectionError, which sends the section back to the model with the message.
"""

from pydantic import ValidationError

from ..ids import slugify
from ..lesson import (
    ChoiceAnswer,
    Lesson,
    MultiChoiceAnswer,
    Part,
    ProblemBlock,
    Section,
)
from .diagrams import layout_problems
from .passages import Passage
from .plan import SectionPlan
from .retry import Rejected
from .schemas import DiagramDraft, ProblemDraft, SectionDraft, SimulationDraft, SourceDraft, Unit
from .units import source_runs


class SectionError(Rejected):
    pass


def assemble_section(
    plan: SectionPlan,
    draft: SectionDraft,
    passages: list[Passage],
    drop_bad_diagrams: bool = False,
) -> Section:
    """Build a section. A diagram with layout problems is a SectionError, unless `drop_bad_diagrams` is set for
    the last attempt, and then it is left out."""
    targets = {slugify(p.source_ref): p for p in plan.problems}
    typed = [block.typed for block in draft.blocks]
    _check_units([block.unit for block in typed if isinstance(block, SourceDraft)], plan.units)
    placed = [_problem_id(block) for block in typed if isinstance(block, ProblemDraft)]
    _check_problems(placed, targets)
    simulations = sum(isinstance(block, SimulationDraft) for block in typed)
    wanted = 1 if plan.simulation else 0
    if simulations != wanted:
        raise SectionError(f"this section needs exactly {wanted} simulation block(s); got {simulations}")
    bad_diagrams = {
        index: problems
        for index, block in enumerate(typed, start=1)
        if isinstance(block, DiagramDraft) and (problems := layout_problems(block.svg))
    }
    if bad_diagrams and not drop_bad_diagrams:
        raise SectionError(_diagram_feedback(bad_diagrams))

    units = {unit.id: unit for unit in plan.units}
    blocks: list[dict] = []
    for index, block in enumerate(typed, start=1):
        # A teaching block's ID is its place in the draft, so dropping a diagram doesn't move the others.
        block_id = f"{plan.id}-block-{index}"
        if index in bad_diagrams:
            continue
        if isinstance(block, SourceDraft):
            sources = _source_blocks(units[block.unit], passages)
            # A unit is one block unless something it holds, such as a figure, splits its text.
            blocks += [{**b, "id": block_id if n == 1 else f"{block_id}-{n}"} for n, b in enumerate(sources, start=1)]
        elif isinstance(block, ProblemDraft):
            blocks.append(_problem(block, targets[_problem_id(block)]))
        elif isinstance(block, SimulationDraft):
            # The code is written on request, after the lesson is ready.
            blocks.append(
                {"type": "simulation", "id": block_id, "caption": block.caption, "brief": plan.simulation, "code": ""}
            )
        else:
            blocks.append({**block.model_dump(), "id": block_id})

    try:
        return Section.model_validate({"id": plan.id, "title": plan.title, "goal": plan.goal, "blocks": blocks})
    except ValidationError as error:
        raise SectionError(f"the section content is invalid: {error}") from error


def _check_units(placed: list[str], wanted: list[Unit]) -> None:
    """Every unit of the section, once each, in the plan's order."""
    order = [unit.id for unit in wanted]
    if placed == order:
        return
    unknown = sorted(set(placed) - set(order))
    if unknown:
        raise SectionError(f"these units don't belong in this section: {', '.join(unknown)}")
    repeated = sorted({u for u in placed if placed.count(u) > 1})
    if repeated:
        raise SectionError(f"each unit must appear once; repeated: {', '.join(repeated)}")
    missing = [u for u in order if u not in placed]
    if missing:
        raise SectionError(f"these units are missing from the section: {', '.join(missing)}")
    raise SectionError(f"place the units in this order: {', '.join(order)}; got: {', '.join(placed)}")


def _source_blocks(unit: Unit, passages: list[Passage]) -> list[dict]:
    """A unit's text, word for word: one source block for each run of its text passages."""
    return [
        {
            "type": "source",
            "body": "\n\n".join(p.text for p in run),
            "file": run[0].file,
            "first_page": run[0].page,
            "last_page": run[-1].page,
        }
        for run in source_runs(unit, passages)
    ]


def _diagram_feedback(bad: dict[int, list[str]]) -> str:
    found = "\n".join(f"- block {index}: {problem}" for index, problems in bad.items() for problem in problems)
    return (
        "these diagrams are laid out badly. Each character of monospace text is 0.6 x its font-size wide; move or "
        f"shorten the text, enlarge the shapes, or widen the viewBox:\n{found}"
    )


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


def _problem(draft: ProblemDraft, extracted) -> dict:
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

    for part in extracted.parts:
        if part.options is not None:
            key = slugify(part.label)
            answers[key] = _with_options(answers[key], part.options, f"{extracted.source_ref} {part.label}")
    return _problem_block(extracted, answers)


def _with_options(answer, options: list[str], where: str):
    """The answer with the problem set's options, so the choices read as the student's homework does."""
    if not isinstance(answer, ChoiceAnswer | MultiChoiceAnswer):
        raise SectionError(f"{where} lists options, so its answer must be choice or multi_choice")
    if len(answer.options) != len(options):
        raise SectionError(f"{where} must offer its {len(options)} options as given, in order")
    # Validated afresh, so the options get the same checks as any lesson text.
    return type(answer).model_validate({**answer.model_dump(), "options": options})


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


def assemble_lesson(
    lesson_id: str,
    title: str,
    subject: str,
    source_files: list[str],
    sections: list[Section],
) -> Lesson:
    return Lesson(
        schema_version=1,
        id=lesson_id,
        title=title,
        subject=subject,
        source_files=source_files,
        sections=sections,
    )
