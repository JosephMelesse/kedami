import json

import pytest

from kedami_server.generation.hints import add_hints, leak_reason, targets
from kedami_server.generation.schemas import HintDraft, HintJudgements, HintReplacements
from kedami_server.lesson import (
    ChoiceAnswer,
    ExpressionAnswer,
    MultiChoiceAnswer,
    NumericAnswer,
    Section,
    SelfCheckAnswer,
)

from .test_pipeline import FakeModel


def numeric(value, tolerance=0.01):
    return NumericAnswer(kind="numeric", value=value, rel_tolerance=tolerance, unit=None)


# The cheap check


@pytest.mark.parametrize(
    "hint, leaks",
    [
        ("The ball is in the air for 2.36 s.", True),
        ("About 2.4 seconds.", False),  # outside 1%
        ("It is 2.361 s.", True),
        ("Use $T = 2 v_0 \\sin\\theta / g$.", False),
        ("Divide 23.14 by 9.8.", False),
    ],
)
def test_numeric_leaks(hint, leaks):
    assert (leak_reason(numeric(2.3613), hint) is not None) is leaks


def test_small_integer_answers_are_left_to_the_judge():
    assert leak_reason(numeric(2), "Square it: $t^2$.") is None


def test_expression_leak_ignores_spacing_and_power_style():
    answer = ExpressionAnswer(kind="expression", expression="v0**2*sin(theta)**2/(2*g)")
    assert leak_reason(answer, "It is v0^2 * sin(theta)^2 / (2*g).")
    assert leak_reason(answer, "Set $v_y = 0$ at the top.") is None


def test_choice_leak():
    answer = ChoiceAnswer(kind="choice", options=["Zero", "Equal to $v_0$"], correct_index=0)
    assert leak_reason(answer, "The vertical velocity is zero there.")
    assert leak_reason(answer, "The projectile stops rising at that instant.") is None


def test_multi_choice_leaks_only_when_every_correct_option_is_named():
    answer = MultiChoiceAnswer(kind="multi_choice", options=["Horizontal velocity", "Speed", "Acceleration"], correct_indexes=[0, 2])
    assert leak_reason(answer, "Horizontal velocity is one of them.") is None
    assert leak_reason(answer, "Horizontal velocity and acceleration.")


def test_self_check_has_no_cheap_check():
    assert leak_reason(SelfCheckAnswer(kind="self_check", rubric="sin 2θ"), "sin 2θ") is None


# Generation, judging, regeneration, and dropping


@pytest.fixture
def section():
    return Section.model_validate({
        "id": "s", "title": "S", "goal": "G",
        "blocks": [
            {"type": "checkpoint", "id": "cp", "prompt": "Find $v_x$.", "answer": numeric(10).model_dump()},
            {"type": "problem", "id": "ps1-1", "source_ref": "PS1 #1", "prompt": "A ball.",
             "parts": [{"id": "a", "label": "(a)", "prompt": "Time?", "answer": numeric(2.3613).model_dump()}]},
        ],
    })


def judged(gives_away: set):
    def reply(prompt):
        data = json.loads(prompt[0]["text"].split("\n\n", 1)[1])
        return {"results": [{"target": d["target"], "index": d["index"], "gives_away": (d["target"], d["index"]) in gives_away} for d in data]}
    return reply


def hints(cp, part):
    return {"items": [{"target": "cp", "hints": cp}, {"target": "ps1-1/a", "hints": part}]}


def result(section):
    return section.blocks[0].hints, section.blocks[1].parts[0].hints


def test_targets_name_parts_and_checkpoints(section):
    assert [t.key for t in targets(section)] == ["cp", "ps1-1/a"]
    assert "A ball." in targets(section)[1].question and "Time?" in targets(section)[1].question


def test_passing_hints_are_kept_in_order(section):
    fake = FakeModel({HintDraft: [hints(["c1", "c2"], ["p1", "p2", "p3"])], HintJudgements: [judged(set())]})
    assert result(add_hints(section, [], fake)) == (["c1", "c2"], ["p1", "p2", "p3"])
    assert fake.calls[HintJudgements][0]["role"] == "small_check"
    assert HintReplacements not in fake.calls


def test_failing_hint_is_regenerated_once_and_kept_if_it_passes(section):
    fake = FakeModel({
        HintDraft: [hints(["c1"], ["p1", "It takes 2.36 s.", "p3"])],
        HintJudgements: [judged(set()), judged(set())],
        HintReplacements: [{"replacements": [{"target": "ps1-1/a", "index": 1, "hint": "Use symmetry."}]}],
    })
    assert result(add_hints(section, [], fake)) == (["c1"], ["p1", "Use symmetry.", "p3"])
    request = fake.calls[HintReplacements][0]["prompt"][-1]["text"]
    assert "contains the answer 2.36" in request


def test_hint_failing_twice_is_dropped(section):
    fake = FakeModel({
        HintDraft: [hints(["c1", "c2"], ["p1"])],
        HintJudgements: [judged({("cp", 1)}), judged({("cp", 1)})],
        HintReplacements: [{"replacements": [{"target": "cp", "index": 1, "hint": "Still too much."}]}],
    })
    assert result(add_hints(section, [], fake)) == (["c1"], ["p1"])


def test_hint_with_no_replacement_is_dropped(section):
    fake = FakeModel({
        HintDraft: [hints(["c1", "c2"], ["p1"])],
        HintJudgements: [judged({("cp", 0)})],
        HintReplacements: [{"replacements": []}],
    })
    assert result(add_hints(section, [], fake)) == (["c2"], ["p1"])


def test_hint_the_judge_skips_counts_as_failing(section):
    fake = FakeModel({
        HintDraft: [hints(["c1"], ["p1"])],
        HintJudgements: [{"results": [{"target": "cp", "index": 0, "gives_away": False}]}, {"results": []}],
        HintReplacements: [{"replacements": [{"target": "ps1-1/a", "index": 0, "hint": "p1 again"}]}],
    })
    assert result(add_hints(section, [], fake)) == (["c1"], [])


def test_replacements_for_hints_that_did_not_fail_are_ignored(section):
    fake = FakeModel({
        HintDraft: [hints(["c1"], ["2.36 s"])],
        HintJudgements: [judged(set()), judged(set())],
        HintReplacements: [{"replacements": [{"target": "cp", "index": 0, "hint": "sneaky"},
                                             {"target": "ps1-1/a", "index": 0, "hint": "Use symmetry."}]}],
    })
    assert result(add_hints(section, [], fake)) == (["c1"], ["Use symmetry."])


def test_unknown_targets_and_missing_targets(section):
    fake = FakeModel({
        HintDraft: [{"items": [{"target": "nope", "hints": ["x"]}, {"target": "cp", "hints": ["c1"]}]}],
        HintJudgements: [judged(set())],
    })
    assert result(add_hints(section, [], fake)) == (["c1"], [])


def test_section_without_targets_makes_no_calls():
    plain = Section.model_validate({"id": "s", "title": "S", "goal": "G", "blocks": [{"type": "explanation", "id": "e", "body": "x"}]})
    fake = FakeModel({})
    assert add_hints(plain, [], fake) == plain
    assert not fake.calls
