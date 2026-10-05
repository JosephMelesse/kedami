import pytest
from pydantic import ValidationError

from kedami_server.lesson import Lesson


def blocks(data):
    return {block["id"]: block for section in data["sections"] for block in section["blocks"]}


def test_fixture_is_valid(lesson_data):
    lesson = Lesson.model_validate(lesson_data)
    assert lesson.find_block("ps3-4").parts[2].id == "c"


def test_round_trip_is_stable(lesson_data):
    first = Lesson.model_validate(lesson_data).model_dump(mode="json")
    second = Lesson.model_validate(first).model_dump(mode="json")
    assert first == second


def test_defaults_are_filled(lesson_data):
    part = blocks(lesson_data)["ps3-4"]["parts"][0]
    del part["answer"]["rel_tolerance"]
    del part["verified"]
    del part["hints"]
    lesson = Lesson.model_validate(lesson_data)
    dumped = lesson.find_block("ps3-4").parts[0]
    assert dumped.answer.rel_tolerance == 0.01
    assert dumped.verified is False
    assert dumped.hints == []


# IDs


def test_problem_id_is_derived_when_missing(lesson_data):
    del blocks(lesson_data)["ps3-4"]["id"]
    assert Lesson.model_validate(lesson_data).find_block("ps3-4") is not None


def test_problem_id_must_match_source_ref(lesson_data):
    blocks(lesson_data)["ps3-4"]["id"] = "problem-4"
    with pytest.raises(ValidationError, match="does not match source_ref"):
        Lesson.model_validate(lesson_data)


def test_part_id_is_derived_when_missing(lesson_data):
    del blocks(lesson_data)["ps3-4"]["parts"][1]["id"]
    assert Lesson.model_validate(lesson_data).find_block("ps3-4").parts[1].id == "b"


def test_part_id_must_match_label(lesson_data):
    blocks(lesson_data)["ps3-4"]["parts"][1]["id"] = "part-b"
    with pytest.raises(ValidationError, match="does not match label"):
        Lesson.model_validate(lesson_data)


def test_part_labels_that_slug_the_same_are_rejected(lesson_data):
    parts = blocks(lesson_data)["ps3-4"]["parts"]
    parts[1]["label"] = "a."
    parts[1]["id"] = "a"
    with pytest.raises(ValidationError, match="unique"):
        Lesson.model_validate(lesson_data)


def test_source_ref_with_no_alphanumerics_is_rejected(lesson_data):
    problem = blocks(lesson_data)["ps3-4"]
    problem["source_ref"] = "#"
    del problem["id"]
    with pytest.raises(ValidationError):
        Lesson.model_validate(lesson_data)


def test_block_ids_unique_across_sections(lesson_data):
    lesson_data["sections"][1]["blocks"][0]["id"] = "components-intro"
    with pytest.raises(ValidationError, match="components-intro"):
        Lesson.model_validate(lesson_data)


def test_problem_id_colliding_with_another_block_is_rejected(lesson_data):
    lesson_data["sections"][0]["blocks"][0]["id"] = "ps3-4"
    with pytest.raises(ValidationError, match="unique"):
        Lesson.model_validate(lesson_data)


def test_section_ids_unique(lesson_data):
    lesson_data["sections"][1]["id"] = "velocity-components"
    with pytest.raises(ValidationError, match="section ids"):
        Lesson.model_validate(lesson_data)


@pytest.mark.parametrize("bad_id", ["Has Caps", "trailing-", "../etc", "", "a_b"])
def test_block_id_must_be_a_slug(lesson_data, bad_id):
    lesson_data["sections"][0]["blocks"][0]["id"] = bad_id
    with pytest.raises(ValidationError):
        Lesson.model_validate(lesson_data)


# Structure


def test_unknown_fields_are_rejected(lesson_data):
    blocks(lesson_data)["ps3-4"]["parts"][0]["solution"] = "spoiler"
    with pytest.raises(ValidationError):
        Lesson.model_validate(lesson_data)


def test_unknown_block_type_is_rejected(lesson_data):
    lesson_data["sections"][0]["blocks"][0]["type"] = "video"
    with pytest.raises(ValidationError):
        Lesson.model_validate(lesson_data)


@pytest.mark.parametrize("field, value", [("schema_version", 2), ("subject", "chemistry")])
def test_lesson_header_values(lesson_data, field, value):
    lesson_data[field] = value
    with pytest.raises(ValidationError):
        Lesson.model_validate(lesson_data)


def test_problem_needs_a_part(lesson_data):
    blocks(lesson_data)["ps3-4"]["parts"] = []
    with pytest.raises(ValidationError):
        Lesson.model_validate(lesson_data)


def test_lesson_needs_a_section(lesson_data):
    lesson_data["sections"] = []
    with pytest.raises(ValidationError):
        Lesson.model_validate(lesson_data)


# Hints


def test_three_hints_allowed(lesson_data):
    blocks(lesson_data)["ps3-4"]["parts"][0]["hints"] = ["one", "two", "three"]
    Lesson.model_validate(lesson_data)


def test_more_than_three_hints_on_a_part_rejected(lesson_data):
    blocks(lesson_data)["ps3-4"]["parts"][0]["hints"] = ["one", "two", "three", "four"]
    with pytest.raises(ValidationError):
        Lesson.model_validate(lesson_data)


def test_more_than_three_hints_on_a_checkpoint_rejected(lesson_data):
    blocks(lesson_data)["components-check"]["hints"] = ["one", "two", "three", "four"]
    with pytest.raises(ValidationError):
        Lesson.model_validate(lesson_data)


# Answers


def answer(lesson_data):
    return blocks(lesson_data)["components-check"]


@pytest.mark.parametrize("tolerance", [0, -0.01])
def test_numeric_tolerance_must_be_positive(lesson_data, tolerance):
    answer(lesson_data)["answer"]["rel_tolerance"] = tolerance
    with pytest.raises(ValidationError):
        Lesson.model_validate(lesson_data)


@pytest.mark.parametrize("index", [-1, 4])
def test_choice_index_out_of_range(lesson_data, index):
    blocks(lesson_data)["apex-check"]["answer"]["correct_index"] = index
    with pytest.raises(ValidationError, match="out of range"):
        Lesson.model_validate(lesson_data)


def test_choice_needs_two_options(lesson_data):
    blocks(lesson_data)["apex-check"]["answer"]["options"] = ["Zero"]
    with pytest.raises(ValidationError):
        Lesson.model_validate(lesson_data)


@pytest.mark.parametrize("indexes", [[], [0, 0], [0, 4], [-1]])
def test_multi_choice_indexes(lesson_data, indexes):
    blocks(lesson_data)["ps3-5"]["parts"][0]["answer"]["correct_indexes"] = indexes
    with pytest.raises(ValidationError):
        Lesson.model_validate(lesson_data)


@pytest.mark.parametrize("expression", ["__import__('os')", "x.__class__", "2x", "eval(x)", "x +"])
def test_expression_answer_must_parse(lesson_data, expression):
    blocks(lesson_data)["height-expression-check"]["answer"]["expression"] = expression
    with pytest.raises(ValidationError):
        Lesson.model_validate(lesson_data)


def test_answer_kind_must_be_known(lesson_data):
    answer(lesson_data)["answer"]["kind"] = "essay"
    with pytest.raises(ValidationError):
        Lesson.model_validate(lesson_data)


# Plots


def plot(lesson_data):
    return blocks(lesson_data)["height-plot"]


def test_plot_expression_may_only_use_x(lesson_data):
    plot(lesson_data)["functions"][0]["expression"] = "15*t - 4.9*t**2"
    with pytest.raises(ValidationError, match="unknown name 't'"):
        Lesson.model_validate(lesson_data)


def test_plot_expression_may_use_parameters(lesson_data):
    plot(lesson_data)["functions"][0]["expression"] = "v*x - 4.9*x**2"
    plot(lesson_data)["parameters"] = [{"name": "v", "min": 5, "max": 20, "default": 15}]
    Lesson.model_validate(lesson_data)


@pytest.mark.parametrize(
    "parameter",
    [
        {"name": "v", "min": 20, "max": 5, "default": 10},
        {"name": "v", "min": 5, "max": 20, "default": 30},
        {"name": "x", "min": 5, "max": 20, "default": 10},
        {"name": "2v", "min": 5, "max": 20, "default": 10},
    ],
)
def test_bad_plot_parameters(lesson_data, parameter):
    plot(lesson_data)["parameters"] = [parameter]
    with pytest.raises(ValidationError):
        Lesson.model_validate(lesson_data)


def test_duplicate_plot_parameters(lesson_data):
    parameter = {"name": "v", "min": 5, "max": 20, "default": 10}
    plot(lesson_data)["parameters"] = [parameter, parameter]
    with pytest.raises(ValidationError, match="unique"):
        Lesson.model_validate(lesson_data)


@pytest.mark.parametrize("field, bounds", [("x_domain", [3, 0]), ("x_domain", [1, 1]), ("y_domain", [5, -5])])
def test_plot_domains_must_be_ordered(lesson_data, field, bounds):
    plot(lesson_data)[field] = bounds
    with pytest.raises(ValidationError):
        Lesson.model_validate(lesson_data)


def test_fixture_is_written_in_the_served_shape(lesson_data):
    """The renderer's tests read the fixture directly, so it must match what the server sends."""
    assert Lesson.model_validate(lesson_data).model_dump(mode="json") == lesson_data


# Plain-text fields: literal \uXXXX escapes a model double-escaped are decoded on read


@pytest.mark.parametrize(
    "text, decoded",
    [
        ("Apply \\u0394U = Q - W", "Apply ΔU = Q - W"),
        ("C_V, C_p and \\u03b3", "C_V, C_p and γ"),
        ("\\u03B3 in upper case", "γ in upper case"),
        ("\\ud83d\\ude00 a surrogate pair", "😀 a surrogate pair"),
        ("Already ΔU", "Already ΔU"),
        ("No escapes at all", "No escapes at all"),
        # LaTeX commands that start with \u are not escapes.
        ("\\underline{x} and \\uparrow", "\\underline{x} and \\uparrow"),
        # Too short, a lone surrogate, and a control character are left as written.
        ("\\u039 short", "\\u039 short"),
        ("\\ud83d alone", "\\ud83d alone"),
        ("\\u0000 null", "\\u0000 null"),
    ],
)
def test_decode_escapes(text, decoded):
    from kedami_server.lesson import decode_escapes

    assert decode_escapes(text) == decoded


def test_plain_text_fields_are_decoded_but_markdown_is_left_alone(lesson_data):
    lesson_data["title"] = "Heat \\u0026 work"
    section = lesson_data["sections"][0]
    section["title"] = "The \\u0394U section"
    section["goal"] = "Apply \\u0394U = Q - W"
    section["blocks"][0]["body"] = "Markdown keeps \\u0394 as written."
    section["blocks"].append(
        {"type": "simulation", "id": "sim", "code": "", "caption": "Drag.", "brief": "Change \\u03b3 and watch."}
    )
    lesson = Lesson.model_validate(lesson_data)
    first = lesson.sections[0]
    assert (lesson.title, first.title, first.goal) == ("Heat & work", "The ΔU section", "Apply ΔU = Q - W")
    assert lesson.find_block("sim").brief == "Change γ and watch."
    assert first.blocks[0].body == "Markdown keeps \\u0394 as written."


def test_new_plans_are_decoded():
    from kedami_server.generation.schemas import Plan

    plan = Plan.model_validate(
        {
            "title": "Thermo \\u0394",
            "sections": [
                {"title": "First law", "goal": "Find \\u0394U.", "concepts": ["first-law"], "simulation": "Vary \\u03b3."}
            ],
        }
    )
    section = plan.sections[0]
    assert (plan.title, section.goal, section.simulation) == ("Thermo Δ", "Find ΔU.", "Vary γ.")


# Markdown fields: math a model double-escaped is repaired on read


@pytest.mark.parametrize(
    "text, repaired",
    [
        ("$A\\\\rightarrow B$ (isobaric)", "$A\\rightarrow B$ (isobaric)"),
        ("$W = p\\\\,\\\\Delta V = 8000\\\\text{ J}$", "$W = p\\,\\Delta V = 8000\\text{ J}$"),
        ("$$\n\\\\Delta U = Q - W\n$$", "$$\n\\Delta U = Q - W\n$$"),
        # A doubled line break inside doubled math is halved too.
        ("$\\\\begin{aligned}a&=1\\\\\\\\b&=2\\\\end{aligned}$", "$\\begin{aligned}a&=1\\\\b&=2\\end{aligned}$"),
        # Only the doubled span changes.
        ("$\\Delta U$ and $\\\\Delta V$", "$\\Delta U$ and $\\Delta V$"),
        # Correct math, real line breaks, and math with no commands are left as written.
        ("$A\\rightarrow B$", "$A\\rightarrow B$"),
        ("$\\begin{aligned}a&=1\\\\b&=2\\end{aligned}$", "$\\begin{aligned}a&=1\\\\b&=2\\end{aligned}$"),
        ("$a\\\\b$", "$a\\\\b$"),
        ("$W_{BC}=0$", "$W_{BC}=0$"),
        # Backslashes outside math, such as in code, are left as written.
        ("`path = \"C:\\\\Users\\\\me\"`", "`path = \"C:\\\\Users\\\\me\"`"),
    ],
)
def test_undouble_math(text, repaired):
    from kedami_server.lesson import undouble_math

    assert undouble_math(text) == repaired


def test_markdown_fields_have_doubled_math_repaired(lesson_data):
    section = lesson_data["sections"][0]
    section["blocks"].append(
        {"type": "worked_example", "id": "loop", "prompt": "Find $\\\\Delta U$.", "steps": ["$A\\\\rightarrow B$"]}
    )
    block = Lesson.model_validate(lesson_data).find_block("loop")
    assert (block.prompt, block.steps) == ("Find $\\Delta U$.", ["$A\\rightarrow B$"])
