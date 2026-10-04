"""The verification pass: a second, independent solve of every part and checkpoint.

The solver sees the course material and each question with the form its answer takes,
never the stored answer, hints, or lesson content. An item is verified only when SymPy
finds the two results equivalent. self_check answers are not verified.
"""

from dataclasses import dataclass

from ..checking import equivalent
from ..lesson import (
    Answer,
    CheckpointBlock,
    ChoiceAnswer,
    ExpressionAnswer,
    MultiChoiceAnswer,
    NumericAnswer,
    ProblemBlock,
    Section,
)
from ..mathparse import MathParseError, parse_math
from . import prompts
from .hints import Call, Target, targets
from .schemas import Solution, Solutions


@dataclass(frozen=True)
class Result:
    target: str
    stored: dict
    solution: dict | None
    verified: bool


def verifiable(section: Section) -> list[Target]:
    """Self checks are the student's own judgment, and external problems are solved elsewhere."""
    return [t for t in targets(section) if t.answer.kind not in ("self_check", "external")]


def answer_format(answer: Answer) -> dict:
    """What the solver is told about the form of an answer, without the answer itself."""
    match answer:
        case NumericAnswer():
            return {"format": "number", "unit": answer.unit}
        case ExpressionAnswer():
            names = sorted(s.name for s in parse_math(answer.expression).free_symbols)
            return {"format": "expression", "use_only_these_names": names}
        case ChoiceAnswer():
            return {"format": "choice", "options": answer.options}
        case MultiChoiceAnswer():
            return {"format": "select_all", "options": answer.options}
    raise ValueError(f"{answer.kind} answers are not verified")


def agrees(answer: Answer, solution: Solution) -> bool:
    match answer:
        case NumericAnswer():
            if solution.value is None:
                return False
            return abs(solution.value - answer.value) <= answer.rel_tolerance * (abs(answer.value) or 1) * (1 + 1e-9)
        case ExpressionAnswer():
            if not solution.expression:
                return False
            stored = parse_math(answer.expression)
            try:
                solved = parse_math(solution.expression, {s.name for s in stored.free_symbols})
            except MathParseError:
                return False
            return equivalent(solved, stored)
        case ChoiceAnswer():
            return solution.correct == [answer.correct_index]
        case MultiChoiceAnswer():
            given = solution.correct or []
            return len(set(given)) == len(given) and set(given) == set(answer.correct_indexes)
    return False


def verify_section(section: Section, materials: list[dict], call: Call) -> tuple[Section, list[Result]]:
    items = verifiable(section)
    if not items:
        return section, []
    reply = call(
        "second_solve",
        system=prompts.SOLVE_SYSTEM,
        prompt=materials + [prompts.solve_request([(t.key, t.question, answer_format(t.answer)) for t in items])],
        output=Solutions,
    )
    solutions = {s.target: s for s in reply.solutions}
    results = [
        Result(
            target=t.key,
            stored=t.answer.model_dump(),
            solution=solutions[t.key].model_dump() if t.key in solutions else None,
            verified=t.key in solutions and agrees(t.answer, solutions[t.key]),
        )
        for t in items
    ]
    return with_verified(section, {r.target for r in results if r.verified}), results


def with_verified(section: Section, verified: set[str]) -> Section:
    blocks = []
    for block in section.blocks:
        if isinstance(block, CheckpointBlock):
            block = block.model_copy(update={"verified": block.id in verified})
        elif isinstance(block, ProblemBlock):
            parts = [p.model_copy(update={"verified": f"{block.id}/{p.id}" in verified}) for p in block.parts]
            block = block.model_copy(update={"parts": parts})
        blocks.append(block)
    return Section.model_validate(section.model_copy(update={"blocks": blocks}).model_dump())
