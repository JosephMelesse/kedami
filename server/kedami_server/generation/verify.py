"""Verification: comparing a stored answer with an independent second solve.

The plugin's verifier subagent solves each part and checkpoint from the course material and the
form its answer takes, never the stored answer. An item is verified only when the two agree, by
SymPy for expressions. self_check answers are not verified. See architecture/agent-mode.md.
"""

from collections.abc import Callable
from dataclasses import dataclass

from .. import queries
from ..checking import equivalent
from ..lesson import (
    Answer,
    CheckpointBlock,
    ChoiceAnswer,
    ExpressionAnswer,
    MultiChoiceAnswer,
    NumericAnswer,
    ProblemBlock,
    QueryAnswer,
    Section,
)
from ..mathparse import MathParseError, parse_math
from .hints import Target, targets
from .schemas import FinalAnswer


@dataclass(frozen=True)
class Result:
    target: str
    stored: dict
    solution: dict | None
    verified: bool


# Self checks are the student's own judgment, external problems are solved elsewhere, and code problems'
# tests come from the imported dataset.
NOT_VERIFIED = ("self_check", "external", "code")


# The bytes of the database a query answer names, for checking a solver's query.
ImageFor = Callable[[str], bytes]


def verifiable(section: Section) -> list[Target]:
    # A bank exercise's reference comes from the bank, so it isn't solved again.
    return [t for t in targets(section) if t.answer.kind not in NOT_VERIFIED and not _from_bank(t.answer)]


def _from_bank(answer: Answer) -> bool:
    return isinstance(answer, QueryAnswer) and answer.exercise is not None


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
        case QueryAnswer():
            return {"format": "query", "database": answer.database.partition("/")[2]}
    raise ValueError(f"{answer.kind} answers are not verified")


def agrees(answer: Answer, solution: FinalAnswer, image_for: ImageFor | None = None) -> bool:
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
        case QueryAnswer():
            if not solution.query or image_for is None:
                return False
            try:
                reason, _ = queries.check(image_for(answer.database), answer.reference, answer.ordered, solution.query)
            except (queries.QueryError, queries.BrokenReference, LookupError):
                return False
            return reason is None
    return False


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
