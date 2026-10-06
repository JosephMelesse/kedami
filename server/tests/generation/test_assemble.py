import pytest

from kedami_server.generation.assemble import SectionError, assemble_lesson, assemble_section
from kedami_server.generation.plan import place_problems
from kedami_server.generation.schemas import SectionDraft

from .factories import extraction, plan

NUMERIC = {"kind": "numeric", "value": 8.66, "rel_tolerance": 0.01, "unit": "m/s"}


@pytest.fixture
def section_plan():
    [section] = place_problems(plan(("Projectiles", ["vectors", "gravity", "range"])), extraction())
    return section


def draft(*blocks):
    return SectionDraft.model_validate({"blocks": list(blocks)})


def problem1(**overrides):
    return {
        "type": "problem",
        "source_ref": "PS1 #1",
        "parts": [{"label": "(a)", "answer": NUMERIC}, {"label": "(b)", "answer": {**NUMERIC, "value": 5}}],
        **overrides,
    }


def problem2():
    return {"type": "problem", "source_ref": "PS1 #2", "parts": [{"label": "2", "answer": {**NUMERIC, "value": 9.2}}]}


EXPLANATION = {"type": "explanation", "body": "Split $v$ into parts."}


def test_blocks_keep_the_model_order_and_get_ids(section_plan):
    section = assemble_section(section_plan, draft(EXPLANATION, problem1(), EXPLANATION, problem2()))
    assert [(b.type, b.id) for b in section.blocks] == [
        ("explanation", "projectiles-block-1"),
        ("problem", "ps1-1"),
        ("explanation", "projectiles-block-3"),
        ("problem", "ps1-2"),
    ]
    assert (section.id, section.title, section.goal) == ("projectiles", "Projectiles", "Learn Projectiles.")


def test_problem_text_comes_from_extraction(section_plan):
    section = assemble_section(section_plan, draft(problem1(), problem2()))
    block = section.blocks[0]
    assert block.prompt == "A ball is thrown at $10$ m/s."
    assert [(p.id, p.label, p.prompt) for p in block.parts] == [("a", "(a)", "Find $v_x$."), ("b", "(b)", "Find $v_y$.")]
    assert block.parts[1].answer.value == 5


def test_part_answers_are_matched_by_label_not_order(section_plan):
    reordered = problem1(parts=[{"label": "(b)", "answer": {**NUMERIC, "value": 5}}, {"label": "a", "answer": NUMERIC}])
    block = assemble_section(section_plan, draft(reordered, problem2())).blocks[0]
    assert [p.answer.value for p in block.parts] == [8.66, 5]


def test_nothing_is_verified_and_there_are_no_hints_yet(section_plan):
    checkpoint = {"type": "checkpoint", "prompt": "Find $v$.", "answer": NUMERIC}
    section = assemble_section(section_plan, draft(checkpoint, problem1(), problem2()))
    assert section.blocks[0].verified is False and section.blocks[0].hints == []
    assert all(not p.verified and p.hints == [] for p in section.blocks[1].parts)


@pytest.mark.parametrize(
    "blocks, message",
    [
        ([problem1()], "missing from the section: PS1 #2"),
        ([problem1(), problem2(), problem2()], "repeated: ps1-2"),
        ([problem1(), problem2(), {**problem2(), "source_ref": "PS9 #9"}], "don't belong in this section: ps9-9"),
        ([problem1(parts=[{"label": "(a)", "answer": NUMERIC}]), problem2()], r"needs one answer for each part \(\(a\), \(b\)\)"),
        ([problem1(parts=[{"label": "(a)", "answer": NUMERIC}, {"label": "(c)", "answer": NUMERIC}]), problem2()], "got: \\(a\\), \\(c\\)"),
        ([problem1(parts=[{"label": "(a)", "answer": NUMERIC}, {"label": "a", "answer": NUMERIC}]), problem2()], "needs one answer"),
    ],
)
def test_problem_placement_errors(section_plan, blocks, message):
    with pytest.raises(SectionError, match=message):
        assemble_section(section_plan, draft(*blocks))


def test_invalid_plot_is_a_section_error(section_plan):
    bad_plot = {"type": "plot", "functions": [{"expression": "t**2", "label": "y"}], "x_domain": [0, 1], "caption": "c"}
    with pytest.raises(SectionError, match="unknown name 't'"):
        assemble_section(section_plan, draft(bad_plot, problem1(), problem2()))


def test_lesson_assembly_validates(section_plan):
    section = assemble_section(section_plan, draft(EXPLANATION, problem1(), problem2()))
    lesson = assemble_lesson("abc-123", "Projectiles", "physics", ["problem-set.md"], [section])
    assert lesson.find_block("ps1-2").parts[0].id == "2"


# Options listed in the problem set


def choice(options, correct=(0,), kind="choice"):
    return {"kind": kind, "options": options, "correct": list(correct)}


@pytest.fixture
def options_plan():
    problems = [
        {
            "source_ref": "Review #1",
            "prompt": "",
            "parts": [{"label": "1", "prompt": "SRAM does not need refreshing.", "options": ["true", "false"]}],
            "concepts": ["vectors"],
        },
        {
            "source_ref": "Review #2",
            "prompt": "",
            "parts": [{"label": "2", "prompt": "Which are buses?", "options": ["Data bus", "Clock", "Address bus"]}],
            "concepts": ["vectors"],
        },
    ]
    [section] = place_problems(plan(("Memory", ["vectors"])), extraction(problems, concepts=("vectors",)))
    return section


def review(first, second=None):
    second = second or choice(["Data bus", "Clock", "Address bus"], (0, 2), "multi_choice")
    return draft(
        {"type": "problem", "source_ref": "Review #1", "parts": [{"label": "1", "answer": first}]},
        {"type": "problem", "source_ref": "Review #2", "parts": [{"label": "2", "answer": second}]},
    )


def test_listed_options_are_shown_once_as_written(options_plan):
    reworded = choice(["data", "clk", "addr"], (0, 2), "multi_choice")
    section = assemble_section(options_plan, review(choice(["True", "False"]), reworded))
    first, second = (block.parts[0] for block in section.blocks)
    assert first.prompt == "SRAM does not need refreshing."
    assert (first.answer.options, first.answer.correct_index) == (["true", "false"], 0)
    assert (second.answer.options, second.answer.correct_indexes) == (["Data bus", "Clock", "Address bus"], [0, 2])


@pytest.mark.parametrize(
    "answer, message",
    [
        ({"kind": "self_check", "rubric": "True."}, "Review #1 1 lists options, so its answer must be choice"),
        (choice(["True", "False", "Unsure"]), "Review #1 1 must offer its 2 options as given, in order"),
    ],
)
def test_a_part_with_options_needs_a_choice_with_as_many(options_plan, answer, message):
    with pytest.raises(SectionError, match=message):
        assemble_section(options_plan, review(answer))


def test_options_are_checked_like_lesson_text():
    part = {"label": "1", "prompt": "Q", "options": ["$\\\\Delta U = 0$", "$Q = 0$"]}
    problems = [{"source_ref": "R #1", "prompt": "", "parts": [part], "concepts": ["vectors"]}]
    [section_plan] = place_problems(plan(("Heat", ["vectors"])), extraction(problems, concepts=("vectors",)))
    answer = {"type": "problem", "source_ref": "R #1", "parts": [{"label": "1", "answer": choice(["a", "b"])}]}
    part = assemble_section(section_plan, draft(answer)).blocks[0].parts[0]
    assert part.answer.options == ["$\\Delta U = 0$", "$Q = 0$"]


def test_a_part_offers_at_least_two_options():
    with pytest.raises(ValueError, match="at least 2"):
        part = {"label": "1", "prompt": "Q", "options": ["yes"]}
        extraction([{"source_ref": "R #1", "prompt": "", "parts": [part], "concepts": []}])


def test_the_section_request_shows_the_options(options_plan):
    from kedami_server.generation.prompts import section_request

    text = section_request(options_plan, [options_plan])["text"]
    assert '"options": [\n' in text and '"Address bus"' in text
