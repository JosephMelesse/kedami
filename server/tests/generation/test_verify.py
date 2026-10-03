import json

import pytest

from kedami_server.generation.schemas import Solution, Solutions
from kedami_server.generation.verify import agrees, answer_format, verify_section
from kedami_server.lesson import (
    ChoiceAnswer,
    ExpressionAnswer,
    MultiChoiceAnswer,
    NumericAnswer,
    Section,
)

from .test_pipeline import FakeModel


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


# The pass over a section


@pytest.fixture
def section():
    return Section.model_validate({
        "id": "s", "title": "S", "goal": "G",
        "blocks": [
            {"type": "checkpoint", "id": "cp", "prompt": "Find $v_x$.", "hints": ["Use cosine."],
             "answer": numeric(10, unit="m/s").model_dump()},
            {"type": "problem", "id": "ps1-1", "source_ref": "PS1 #1", "prompt": "A ball at 18 m/s.",
             "parts": [
                 {"id": "a", "label": "(a)", "prompt": "Time?", "hints": ["Symmetry."], "answer": numeric(2.3613).model_dump()},
                 {"id": "b", "label": "(b)", "prompt": "Why?", "answer": {"kind": "self_check", "rubric": "Mentions sin 2θ."}},
                 {"id": "c", "label": "(c)", "prompt": "Height?",
                  "answer": {"kind": "expression", "expression": "v0**2*sin(theta)**2/(2*g)"}},
             ]},
        ],
    })


def solved(*solutions):
    return {"solutions": [{"value": None, "expression": None, "correct": None, **s} for s in solutions]}


def verified(section):
    cp, problem = section.blocks
    return cp.verified, [p.verified for p in problem.parts]


def test_matching_items_are_verified_and_others_are_not(section):
    fake = FakeModel({Solutions: [solved(
        {"target": "cp", "value": 10.0},
        {"target": "ps1-1/a", "value": 2.5},
        {"target": "ps1-1/c", "expression": "(v0*sin(theta))**2/(2*g)"},
    )]})
    result, records = verify_section(section, [], fake)
    assert verified(result) == (True, [False, False, True])
    assert [(r.target, r.verified) for r in records] == [("cp", True), ("ps1-1/a", False), ("ps1-1/c", True)]
    assert records[1].solution["value"] == 2.5 and records[1].stored["value"] == 2.3613


def test_the_solver_never_sees_answers_hints_or_self_checks(section):
    fake = FakeModel({Solutions: [solved()]})
    verify_section(section, [{"type": "text", "text": "MATERIAL"}], fake)
    call = fake.calls[Solutions][0]
    assert call["role"] == "second_solve"
    assert call["prompt"][0]["text"] == "MATERIAL"
    request = call["prompt"][-1]["text"]
    items = json.loads(request.split("\n\n", 1)[1])
    assert [i["target"] for i in items] == ["cp", "ps1-1/a", "ps1-1/c"]
    for forbidden in ["2.3613", "Use cosine", "Symmetry", "sin(theta)**2", "sin 2θ", "rel_tolerance", "\"answer\""]:
        assert forbidden not in request
    assert "A ball at 18 m/s." in items[1]["question"] and "Time?" in items[1]["question"]


def test_missing_solutions_leave_items_unverified(section):
    fake = FakeModel({Solutions: [solved({"target": "cp", "value": 10.0}, {"target": "nope", "value": 1.0})]})
    result, records = verify_section(section, [], fake)
    assert verified(result) == (True, [False, False, False])
    assert records[1].solution is None


def test_verification_overwrites_any_earlier_flag(section):
    marked = section.model_copy(deep=True)
    marked.blocks[1].parts[0].verified = True
    fake = FakeModel({Solutions: [solved({"target": "ps1-1/a", "value": 99.0})]})
    result, _ = verify_section(marked, [], fake)
    assert verified(result) == (False, [False, False, False])


def test_section_with_only_self_checks_makes_no_call():
    plain = Section.model_validate({"id": "s", "title": "S", "goal": "G", "blocks": [
        {"type": "problem", "id": "q", "source_ref": "Q", "prompt": "",
         "parts": [{"id": "1", "label": "1", "prompt": "Prove it.", "answer": {"kind": "self_check", "rubric": "r"}}]},
    ]})
    fake = FakeModel({})
    assert verify_section(plain, [], fake) == (plain, [])
    assert not fake.calls
