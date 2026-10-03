import pytest

from kedami_server.checking import InvalidResponse, check
from kedami_server.lesson import (
    ChoiceAnswer,
    ExpressionAnswer,
    MultiChoiceAnswer,
    NumericAnswer,
    SelfCheckAnswer,
)


def numeric(value, tolerance=0.01):
    return NumericAnswer(kind="numeric", value=value, rel_tolerance=tolerance, unit=None)


def expression(text):
    return ExpressionAnswer(kind="expression", expression=text)


# Numeric


@pytest.mark.parametrize(
    "response, expected",
    [
        ("10", True),
        ("10.1", True),  # exactly at the 1% boundary
        ("9.9", True),
        ("10.11", False),
        ("9.89", False),
        ("  10.05 ", True),
        ("1e1", True),
        ("+10", True),
        ("-10", False),
    ],
)
def test_numeric_tolerance(response, expected):
    assert check(numeric(10), response) is expected


def test_numeric_tolerance_is_relative():
    assert check(numeric(32.559), "32.4")
    assert not check(numeric(32.559), "32.2")
    assert check(numeric(1000, 0.05), "1049")


def test_numeric_negative_value():
    assert check(numeric(-4.9), "-4.9")
    assert not check(numeric(-4.9), "4.9")


def test_numeric_zero_uses_tolerance_as_absolute():
    assert check(numeric(0), "0.005")
    assert not check(numeric(0), "0.02")


@pytest.mark.parametrize("response", ["", "abc", "2,36", "1/2", "nan", "inf", "1_000", "2.3.4", "1e999", 10, None, True])
def test_numeric_rejects_malformed(response):
    with pytest.raises(InvalidResponse):
        check(numeric(10), response)


# Expression


@pytest.mark.parametrize(
    "response",
    [
        "v0**2*sin(theta)**2/(2*g)",
        "(v0*sin(theta))**2/(2*g)",
        "v0^2*sin(theta)^2/(2*g)",
        "v0**2*(1 - cos(theta)**2)/(2*g)",
        "0.5*v0**2*sin(theta)**2/g",
        "v0**2 * sin(theta)**2 / g / 2",
    ],
)
def test_expression_equivalent_forms(response):
    assert check(expression("v0**2*sin(theta)**2/(2*g)"), response)


@pytest.mark.parametrize(
    "response",
    [
        "v0**2*sin(theta)/(2*g)",
        "v0**2*sin(theta)**2/g",
        "v0*sin(theta)**2/(2*g)",
        "v0**2*cos(theta)**2/(2*g)",
        "0",
    ],
)
def test_expression_wrong_forms(response):
    assert not check(expression("v0**2*sin(theta)**2/(2*g)"), response)


def test_expression_float_and_rational_coefficients_agree():
    assert check(expression("10*t - 4.9*t**2"), "10*t - 49/10*t**2")
    assert check(expression("10*t - 4.9*t**2"), "t*(10 - 4.9*t)")


def test_expression_constants():
    assert check(expression("pi/2"), "asin(1)")
    assert not check(expression("pi/2"), "1.57")


def test_expression_result_is_stable_across_repeat_runs():
    answer = expression("sqrt(x**2 + 1)")
    results = {check(answer, "(x**2 + 1)**(1/2)") for _ in range(5)}
    assert results == {True}


def test_expression_large_power_is_checked_by_sampling():
    assert check(expression("(x + 1)**60"), "(1 + x)**60")
    assert not check(expression("(x + 1)**60"), "(x + 1)**59")


@pytest.mark.parametrize("response", ["", "   ", "2x", "q*t", "__import__('os')", "t +", 5])
def test_expression_rejects_malformed_or_unknown_names(response):
    with pytest.raises(InvalidResponse):
        check(expression("10*t - 4.9*t**2"), response)


# Choice


def test_choice():
    answer = ChoiceAnswer(kind="choice", options=["a", "b", "c"], correct_index=1)
    assert check(answer, 1)
    assert not check(answer, 0)


@pytest.mark.parametrize("response", [-1, 3, "1", 1.0, True, None, [1]])
def test_choice_rejects_malformed(response):
    with pytest.raises(InvalidResponse):
        check(ChoiceAnswer(kind="choice", options=["a", "b", "c"], correct_index=1), response)


def test_multi_choice_needs_exact_set():
    answer = MultiChoiceAnswer(kind="multi_choice", options=["a", "b", "c", "d"], correct_indexes=[0, 2])
    assert check(answer, [0, 2])
    assert check(answer, [2, 0])
    assert not check(answer, [0])
    assert not check(answer, [0, 2, 3])


@pytest.mark.parametrize("response", [[], [0, 0], [4], ["0"], 0, None, [True]])
def test_multi_choice_rejects_malformed(response):
    with pytest.raises(InvalidResponse):
        check(MultiChoiceAnswer(kind="multi_choice", options=["a", "b", "c", "d"], correct_indexes=[0]), response)


# Self check


def test_self_check_records_judgment():
    answer = SelfCheckAnswer(kind="self_check", rubric="r")
    assert check(answer, {"text": "my answer", "correct": True})
    assert not check(answer, {"text": "", "correct": False})


@pytest.mark.parametrize(
    "response",
    [None, "text", {"text": "x"}, {"correct": True}, {"text": 1, "correct": True}, {"text": "x", "correct": "yes"},
     {"text": "x" * 5001, "correct": True}, {"text": "x", "correct": True, "extra": 1}],
)
def test_self_check_rejects_malformed(response):
    with pytest.raises(InvalidResponse):
        check(SelfCheckAnswer(kind="self_check", rubric="r"), response)
