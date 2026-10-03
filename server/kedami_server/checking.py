"""Checks a student's response against a stored answer, by answer kind.

A malformed response raises InvalidResponse and does not count as an attempt.
"""

import math
import random
import re
from typing import Any

import sympy

from .lesson import (
    Answer,
    ChoiceAnswer,
    ExpressionAnswer,
    MultiChoiceAnswer,
    NumericAnswer,
    SelfCheckAnswer,
)
from .mathparse import MathParseError, parse_math

MAX_TEXT = 5000
NUMBER = re.compile(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?")

# Numeric sampling for expressions: positive values, since physical quantities usually are.
SAMPLE_RANGE = (0.5, 3.0)
SAMPLE_POINTS = 8
SAMPLE_TRIES = 40
SAMPLE_TOLERANCE = 1e-6
MAX_SIMPLIFY_OPS = 200


class InvalidResponse(ValueError):
    pass


def check(answer: Answer, response: Any) -> bool:
    match answer:
        case NumericAnswer():
            return check_numeric(answer, response)
        case ExpressionAnswer():
            return check_expression(answer, response)
        case ChoiceAnswer():
            return _index(response, len(answer.options)) == answer.correct_index
        case MultiChoiceAnswer():
            return _index_set(response, len(answer.options)) == set(answer.correct_indexes)
        case SelfCheckAnswer():
            return check_self(response)
    raise TypeError(f"unknown answer kind {answer!r}")


def check_numeric(answer: NumericAnswer, response: Any) -> bool:
    if not isinstance(response, str) or not NUMBER.fullmatch(response.strip()):
        raise InvalidResponse("Enter a number, such as 2.36 or 1.5e3.")
    value = float(response.strip())
    if not math.isfinite(value):
        raise InvalidResponse("Enter a finite number.")
    # An answer of zero has no scale, so the tolerance is used as an absolute one.
    allowed = answer.rel_tolerance * (abs(answer.value) or 1)
    return abs(value - answer.value) <= allowed * (1 + 1e-9)


def check_expression(answer: ExpressionAnswer, response: Any) -> bool:
    if not isinstance(response, str) or not response.strip():
        raise InvalidResponse("Enter an expression.")
    expected = parse_math(answer.expression)
    names = {symbol.name for symbol in expected.free_symbols}
    try:
        given = parse_math(response, names)
    except MathParseError as error:
        raise InvalidResponse(f"Could not read that expression: {error}.") from error
    return equivalent(given, expected)


def equivalent(a: sympy.Expr, b: sympy.Expr) -> bool:
    """Symbolic equivalence first, then agreement at sampled points."""
    difference = a - b
    if sympy.count_ops(difference) <= MAX_SIMPLIFY_OPS and sympy.simplify(difference) == 0:
        return True
    return _agree_at_samples(a, b)


def _agree_at_samples(a: sympy.Expr, b: sympy.Expr) -> bool:
    symbols = sorted(a.free_symbols | b.free_symbols, key=lambda s: s.name)
    rng = random.Random(0)  # Fixed, so the same response always gets the same result.
    agreed = 0
    for _ in range(SAMPLE_TRIES):
        point = {symbol: rng.uniform(*SAMPLE_RANGE) for symbol in symbols}
        va, vb = _value(a, point), _value(b, point)
        if va is None or vb is None:
            continue
        if abs(va - vb) > SAMPLE_TOLERANCE * max(1.0, abs(va), abs(vb)):
            return False
        agreed += 1
        if agreed == SAMPLE_POINTS or not symbols:
            return True
    return False


def _value(expr: sympy.Expr, point: dict) -> complex | None:
    try:
        value = complex(expr.evalf(subs=point))
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None
    if not (math.isfinite(value.real) and math.isfinite(value.imag)):
        return None
    return value


def _index(response: Any, count: int) -> int:
    if isinstance(response, bool) or not isinstance(response, int) or not 0 <= response < count:
        raise InvalidResponse("Choose one of the options.")
    return response


def _index_set(response: Any, count: int) -> set[int]:
    if not isinstance(response, list) or not response:
        raise InvalidResponse("Select at least one option.")
    indexes = [_index(item, count) for item in response]
    if len(set(indexes)) != len(indexes):
        raise InvalidResponse("Each option can be selected once.")
    return set(indexes)


def check_self(response: Any) -> bool:
    """The student's own judgment after seeing the rubric is the result."""
    if not isinstance(response, dict) or set(response) != {"text", "correct"}:
        raise InvalidResponse("A self check needs the answer text and a judgment.")
    if not isinstance(response["text"], str) or len(response["text"]) > MAX_TEXT:
        raise InvalidResponse(f"Keep the answer under {MAX_TEXT} characters.")
    if not isinstance(response["correct"], bool):
        raise InvalidResponse("A self check needs a judgment.")
    return response["correct"]
