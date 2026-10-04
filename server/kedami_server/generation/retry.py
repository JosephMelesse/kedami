"""Retrying a stage whose reply was rejected, with the reason fed back."""

from collections.abc import Callable
from typing import TypeVar

from pydantic import ValidationError

from .assemble import SectionError
from .leetcode import ConceptMapError
from .plan import PlanError

ATTEMPTS = 3
MAX_FEEDBACK = 4000

T = TypeVar("T")


class GenerationError(Exception):
    pass


def retrying(stage: str, attempt: Callable[[str | None], T]) -> T:
    """Run an attempt, feeding back why the last reply was rejected."""
    feedback = None
    for _ in range(ATTEMPTS):
        try:
            return attempt(feedback)
        except (ValidationError, PlanError, SectionError, ConceptMapError) as error:
            feedback = str(error)[:MAX_FEEDBACK]
    raise GenerationError(f"{stage} failed after {ATTEMPTS} attempts. Last problem: {feedback}")
