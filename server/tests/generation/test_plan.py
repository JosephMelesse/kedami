"""The plan's order rules. See Stage 3: sequencing rules in architecture/pipeline.md."""

import pytest
from pydantic import ValidationError

from kedami_server.generation.passages import TEXT, Passage
from kedami_server.generation.plan import PlanError, place_problems

from .factories import PASSAGES, extraction, plan


def placed(sections):
    return [(s.id, [u.id for u in s.units], [p.source_ref for p in s.problems]) for s in sections]


def place(the_plan, data=None, passages=PASSAGES):
    return place_problems(the_plan, data or extraction(), passages)


def test_problem_goes_where_its_last_unit_is_covered():
    sections = place(plan(("Vectors", ["vectors"]), ("Gravity", ["gravity"]), ("Range", ["range"])))
    assert placed(sections) == [
        ("vectors", ["vectors"], ["PS1 #1"]),
        ("gravity", ["gravity"], []),
        ("range", ["range"], ["PS1 #2"]),
    ]


def test_every_problem_appears_exactly_once():
    sections = place(plan(("A", ["vectors", "gravity"]), ("B", ["range"])))
    refs = [p.source_ref for s in sections for p in s.problems]
    assert sorted(refs) == ["PS1 #1", "PS1 #2"]


def test_problem_that_needs_no_unit_goes_first():
    data = extraction(problems=[{"source_ref": "Q1", "prompt": "", "parts": [{"label": "1", "prompt": "x"}], "units": []}])
    sections = place(plan(("A", ["vectors"]), ("B", ["gravity", "range"])), data)
    assert placed(sections)[0][2] == ["Q1"]


def test_a_unit_no_problem_needs_still_gets_a_section():
    data = extraction(
        problems=[{"source_ref": "Q1", "prompt": "", "parts": [{"label": "1", "prompt": "x"}], "units": ["vectors"]}]
    )
    sections = place(plan(("A", ["vectors"]), ("Extra", ["gravity", "range"])), data)
    assert placed(sections)[1] == ("extra", ["gravity", "range"], [])


def test_a_unit_in_no_section_is_rejected():
    with pytest.raises(PlanError, match="these units are in no section: range"):
        place(plan(("A", ["vectors", "gravity"])))


def test_an_unneeded_unit_left_out_is_still_rejected():
    data = extraction(problems=[{"source_ref": "Q1", "prompt": "", "parts": [{"label": "1", "prompt": "x"}], "units": []}])
    with pytest.raises(PlanError, match="in no section: gravity, range"):
        place(plan(("A", ["vectors"])), data)


def test_unknown_unit_is_rejected():
    with pytest.raises(PlanError, match="unknown unit 'optics'"):
        place(plan(("A", ["vectors", "gravity", "range", "optics"])))


def test_unit_in_two_sections_is_rejected():
    with pytest.raises(PlanError, match="'vectors' is in more than one section"):
        place(plan(("A", ["vectors", "gravity"]), ("B", ["range", "vectors"])))


def test_every_problem_with_the_plan_is_reported_at_once():
    with pytest.raises(PlanError) as raised:
        place(plan(("A", ["vectors", "optics"]), ("B", ["vectors"])))
    assert all(text in str(raised.value) for text in ("optics", "more than one section", "gravity, range"))


# Order within a file


def test_units_out_of_file_order_are_rejected():
    with pytest.raises(PlanError, match=r"'gravity' \(p2\) comes after 'range' \(p3\)"):
        place(plan(("A", ["vectors", "range"]), ("B", ["gravity"])))


def test_order_within_a_section_counts_too():
    with pytest.raises(PlanError, match="keep the order of the file"):
        place(plan(("A", ["gravity", "vectors", "range"])))


TWO_FILES = [
    Passage(1, TEXT, "lecture.pdf", 1, "Vectors."),
    Passage(2, TEXT, "lecture.pdf", 2, "Gravity."),
    Passage(3, TEXT, "book.pdf", 1, "Range."),
]


def test_sections_may_alternate_between_files():
    sections = place(plan(("A", ["range"]), ("B", ["vectors"]), ("C", ["gravity"])), passages=TWO_FILES)
    assert [s.id for s in sections] == ["a", "b", "c"]


def test_file_order_is_kept_apart_for_each_file():
    with pytest.raises(PlanError, match="'vectors' \\(p1\\) comes after 'gravity' \\(p2\\)"):
        place(plan(("A", ["range", "gravity"]), ("B", ["vectors"])), passages=TWO_FILES)


# Sections


def test_empty_sections_are_dropped():
    sections = place(plan(("Intro", []), ("A", ["vectors", "gravity", "range"])))
    assert [s.id for s in sections] == ["a"]


def test_section_ids_are_unique_slugs():
    sections = place(plan(("Review", ["vectors"]), ("Review!", ["gravity"]), ("???", ["range"])))
    assert [s.id for s in sections] == ["review", "review-2", "section-3"]


def test_same_input_gives_same_sections():
    make = lambda: placed(place(plan(("A", ["vectors"]), ("B", ["gravity", "range"]))))
    assert make() == make()


# Extraction consistency


def test_extraction_rejects_problems_with_the_same_id():
    part = [{"label": "1", "prompt": "x"}]
    with pytest.raises(ValidationError, match="source references"):
        extraction(problems=[
            {"source_ref": "PS1 #1", "prompt": "", "parts": part, "units": []},
            {"source_ref": "ps1-1", "prompt": "", "parts": part, "units": []},
        ])


def test_extraction_rejects_part_labels_with_the_same_id():
    with pytest.raises(ValidationError, match="part labels"):
        extraction(problems=[{"source_ref": "Q1", "prompt": "", "units": [],
                              "parts": [{"label": "(a)", "prompt": "x"}, {"label": "a.", "prompt": "y"}]}])


def test_extraction_needs_a_problem():
    with pytest.raises(ValidationError):
        extraction(problems=[])
