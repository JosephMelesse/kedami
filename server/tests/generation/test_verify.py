import pytest

from kedami_server.generation.schemas import Solution
from kedami_server.generation.verify import agrees, answer_format
from kedami_server.lesson import (
    ChoiceAnswer,
    ExpressionAnswer,
    MultiChoiceAnswer,
    NumericAnswer,
)


def numeric(value, tolerance=0.01, unit="s"):
    return NumericAnswer(kind="numeric", value=value, rel_tolerance=tolerance, unit=unit)


def solution(**fields):
    return Solution.model_validate({"target": "t", "value": None, "expression": None, "correct": None, **fields})


# Comparison


@pytest.mark.parametrize(
    "value, agreed",
    [(2.3613, True), (2.38, True), (2.34, True), (2.39, False), (2.33, False), (-2.3613, False), (None, False)],
)
def test_numeric_agreement_uses_the_stored_tolerance(value, agreed):
    assert agrees(numeric(2.3613), solution(value=value)) is agreed


def test_numeric_zero_answer():
    assert agrees(numeric(0), solution(value=0.004))
    assert not agrees(numeric(0), solution(value=0.2))


@pytest.mark.parametrize(
    "expression, agreed",
    [
        ("(v0*sin(theta))**2/(2*g)", True),
        ("v0^2*(1 - cos(theta)^2)/(2*g)", True),
        ("v0**2*sin(theta)/(2*g)", False),
        ("v0**2*sin(theta)**2/(2*h)", False),  # a name the stored answer doesn't use
        ("2x", False),
        ("", False),
        (None, False),
    ],
)
def test_expression_agreement_is_symbolic(expression, agreed):
    stored = ExpressionAnswer(kind="expression", expression="v0**2*sin(theta)**2/(2*g)")
    assert agrees(stored, solution(expression=expression)) is agreed


@pytest.mark.parametrize("correct, agreed", [([1], True), ([0], False), ([1, 1], False), ([], False), (None, False)])
def test_choice_agreement(correct, agreed):
    assert agrees(ChoiceAnswer(kind="choice", options=["a", "b"], correct_index=1), solution(correct=correct)) is agreed


@pytest.mark.parametrize(
    "correct, agreed", [([0, 2], True), ([2, 0], True), ([0], False), ([0, 2, 3], False), ([0, 0, 2], False), (None, False)]
)
def test_multi_choice_agreement(correct, agreed):
    answer = MultiChoiceAnswer(kind="multi_choice", options=["a", "b", "c", "d"], correct_indexes=[0, 2])
    assert agrees(answer, solution(correct=correct)) is agreed


def test_answer_format_never_contains_the_answer():
    assert answer_format(numeric(2.3613)) == {"format": "number", "unit": "s"}
    form = answer_format(ExpressionAnswer(kind="expression", expression="v0**2*sin(theta)**2/(2*g)"))
    assert form == {"format": "expression", "use_only_these_names": ["g", "theta", "v0"]}
    assert answer_format(ChoiceAnswer(kind="choice", options=["a", "b"], correct_index=1)) == {"format": "choice", "options": ["a", "b"]}
