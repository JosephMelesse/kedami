import pytest
from pydantic import ValidationError

from kedami_server.generation.schemas import GeneralSteps, MathSteps, PhysicsSteps
from kedami_server.generation.solutions import has_solution
from kedami_server.lesson import Part

FINAL_NONE = {"value": None, "expression": None, "correct": None}


def physics(value, steps=None):
    return {
        "given": ["v_0 = 10\\,\\mathrm{m/s}", "\\theta = 30^\\circ"],
        "required": ["v_x"],
        "steps": steps or ["v_x = v_0 \\cos\\theta", "v_x = (10)(\\cos 30^\\circ)", f"\\boxed{{v_x = {value}\\,\\mathrm{{m/s}}}}"],
        "final": {**FINAL_NONE, "value": value},
    }


def math(value):
    return {
        "method": "Direct substitution",
        "steps": ["f(x) = 10\\cos x", f"\\boxed{{{value}}}"],
        "final": {**FINAL_NONE, "value": value},
    }


def general(value):
    return {
        "steps": ["The FPU registers hold extended-precision values.", f"**{value}** bits"],
        "final": {**FINAL_NONE, "value": value},
    }


# The shape of a reply


def test_stray_dollar_delimiters_are_removed():
    steps = MathSteps.model_validate({**math(1), "steps": ["$$x = 1$$", " $\\boxed{1}$ "]})
    assert steps.steps == ["x = 1", "\\boxed{1}"]


@pytest.mark.parametrize(
    "change, message",
    [
        ({"method": ""}, "method must be"),
        ({"method": "x" * 81}, "method must be"),
        ({"steps": []}, "at least one line"),
        ({"steps": ["x = 1", "  $$ "]}, "empty line"),
        ({"steps": ["x"] * 25}, "more than 24 lines"),
        ({"steps": ["x" * 601]}, "longer than 600"),
    ],
)
def test_unusable_math_steps_are_rejected(change, message):
    with pytest.raises(ValidationError, match=message):
        MathSteps.model_validate({**math(1), **change})


def test_physics_needs_what_is_required_but_not_given_values():
    assert PhysicsSteps.model_validate({**physics(1), "given": []}).given == []
    with pytest.raises(ValidationError, match="required needs at least one line"):
        PhysicsSteps.model_validate({**physics(1), "required": []})


def test_general_steps_keep_markdown_and_inline_math():
    steps = GeneralSteps.model_validate({**general(80), "steps": [" Uses $2^{64}$ bytes. ", "**80** bits"]})
    assert steps.steps == ["Uses $2^{64}$ bytes.", "**80** bits"]


@pytest.mark.parametrize(
    "change, message",
    [
        ({"steps": []}, "at least one line"),
        ({"steps": ["x", "  "]}, "empty line"),
        ({"steps": ["x"] * 25}, "more than 24 lines"),
        ({"steps": ["x" * 601]}, "longer than 600"),
    ],
)
def test_unusable_general_steps_are_rejected(change, message):
    with pytest.raises(ValidationError, match=message):
        GeneralSteps.model_validate({**general(1), **change})


def test_only_math_physics_and_general_parts_have_solutions():
    part = Part.model_validate({"label": "(a)", "prompt": "x", "answer": {"kind": "numeric", "value": 1}})
    assert has_solution("math", part) and has_solution("physics", part) and has_solution("general", part)
    assert not has_solution("computer_science", part)


# Writing on request
