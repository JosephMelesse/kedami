import pytest
from pydantic import ValidationError

from kedami_server.generation.schemas import AnswerDraft, BlockDraft
from kedami_server.lesson import ChoiceAnswer, MultiChoiceAnswer, NumericAnswer

NULLS = dict(value=None, rel_tolerance=None, unit=None, expression=None, rubric=None, options=None, correct=None)


def answer(**fields):
    return AnswerDraft.model_validate({**NULLS, **fields}).typed


def test_numeric_defaults_its_tolerance():
    typed = answer(kind="numeric", value=2.36, unit="s")
    assert typed == NumericAnswer(kind="numeric", value=2.36, rel_tolerance=0.01, unit="s")


def test_fields_for_other_kinds_are_ignored():
    typed = answer(kind="expression", expression="v0*t", value=3.0, rubric="ignored")
    assert typed.model_dump() == {"kind": "expression", "expression": "v0*t"}


def test_choice_and_multi_choice():
    assert answer(kind="choice", options=["a", "b"], correct=[1]) == ChoiceAnswer(kind="choice", options=["a", "b"], correct_index=1)
    assert answer(kind="multi_choice", options=["a", "b", "c"], correct=[0, 2]) == MultiChoiceAnswer(
        kind="multi_choice", options=["a", "b", "c"], correct_indexes=[0, 2]
    )


@pytest.mark.parametrize(
    "fields, message",
    [
        (dict(kind="numeric"), "invalid numeric answer"),
        (dict(kind="expression", expression="2x"), "invalid expression answer"),
        (dict(kind="choice", options=["a", "b"], correct=[0, 1]), "exactly one correct index"),
        (dict(kind="choice", options=["a", "b"], correct=None), "exactly one correct index"),
        (dict(kind="multi_choice", options=["a", "b"], correct=[5]), "invalid multi_choice answer"),
        (dict(kind="self_check"), "invalid self_check answer"),
    ],
)
def test_bad_answers_are_rejected_with_the_reason(fields, message):
    with pytest.raises(ValidationError, match=message):
        answer(**fields)


def test_problem_block_converts_part_answers():
    block = BlockDraft.model_validate({
        "type": "problem", "source_ref": "PS1 #1", "body": "ignored",
        "parts": [{"label": "(a)", "answer": {**NULLS, "kind": "numeric", "value": 4.0}}],
    }).typed
    assert block.type == "problem" and block.parts[0].answer.value == 4.0


def test_plot_block_converts():
    block = BlockDraft.model_validate({
        "type": "plot", "functions": [{"expression": "x**2", "label": "y"}], "parameters": [],
        "x_domain": [0, 2], "y_domain": None, "caption": "c",
    }).typed
    assert block.x_domain == (0, 2) and block.y_domain is None


@pytest.mark.parametrize(
    "fields, message",
    [
        ({"type": "explanation"}, "invalid explanation block"),
        ({"type": "checkpoint", "prompt": "Q?"}, "invalid checkpoint block"),
        ({"type": "plot", "functions": [{"expression": "x", "label": "y"}], "x_domain": [0], "caption": "c"}, "invalid plot block"),
        ({"type": "problem", "source_ref": "PS1 #1"}, "invalid problem block"),
    ],
)
def test_blocks_missing_their_fields_are_rejected(fields, message):
    with pytest.raises(ValidationError, match=message):
        BlockDraft.model_validate(fields)
