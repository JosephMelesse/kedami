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
