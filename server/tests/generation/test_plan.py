import pytest
from pydantic import ValidationError

from kedami_server.generation.plan import PlanError, place_problems

from .factories import extraction, plan


def placed(sections):
    return [(s.id, [c.id for c in s.concepts], [p.source_ref for p in s.problems]) for s in sections]


def test_problem_goes_where_its_last_prerequisite_is_covered():
    sections = place_problems(plan(("Vectors", ["vectors"]), ("Gravity", ["gravity"]), ("Range", ["range"])), extraction())
    assert placed(sections) == [
        ("vectors", ["vectors"], ["PS1 #1"]),
        ("gravity", ["gravity"], []),
        ("range", ["range"], ["PS1 #2"]),
    ]


def test_concepts_order_within_a_plan_decides_placement():
    sections = place_problems(plan(("Everything", ["range", "gravity", "vectors"])), extraction())
    assert placed(sections) == [("everything", ["range", "gravity", "vectors"], ["PS1 #1", "PS1 #2"])]


def test_every_problem_appears_exactly_once():
    sections = place_problems(plan(("A", ["vectors", "gravity"]), ("B", ["range"])), extraction())
    refs = [p.source_ref for s in sections for p in s.problems]
    assert sorted(refs) == ["PS1 #1", "PS1 #2"]


def test_problem_with_no_prerequisites_goes_first():
    data = extraction(
        problems=[{"source_ref": "Q1", "prompt": "", "parts": [{"label": "1", "prompt": "x"}], "concepts": []}]
    )
    sections = place_problems(plan(("A", ["vectors"]), ("B", ["gravity"])), data)
    assert placed(sections)[0][2] == ["Q1"]


def test_missing_prerequisite_is_rejected():
    with pytest.raises(PlanError, match="range"):
        place_problems(plan(("A", ["vectors", "gravity"])), extraction())


def test_unknown_concept_is_rejected():
    with pytest.raises(PlanError, match="unknown concept 'optics'"):
        place_problems(plan(("A", ["vectors", "gravity", "range", "optics"])), extraction())


def test_concept_introduced_twice_is_rejected():
    with pytest.raises(PlanError, match="more than one section"):
        place_problems(plan(("A", ["vectors", "gravity"]), ("B", ["range", "vectors"])), extraction())


def test_unneeded_concepts_may_be_taught():
    data = extraction(concepts=("vectors", "gravity", "range", "drag"))
    sections = place_problems(plan(("A", ["vectors", "gravity", "range"]), ("Extra", ["drag"])), data)
    assert placed(sections)[1] == ("extra", ["drag"], [])


def test_empty_sections_are_dropped():
    sections = place_problems(plan(("Intro", []), ("A", ["vectors", "gravity", "range"])), extraction())
    assert [s.id for s in sections] == ["a"]


def test_section_ids_are_unique_slugs():
    sections = place_problems(plan(("Review", ["vectors"]), ("Review!", ["gravity"]), ("???", ["range"])), extraction())
    assert [s.id for s in sections] == ["review", "review-2", "section-3"]


def test_same_input_gives_same_sections():
    make = lambda: placed(place_problems(plan(("A", ["vectors"]), ("B", ["gravity", "range"])), extraction()))
    assert make() == make()


# Extraction consistency


def test_extraction_rejects_unknown_problem_concepts():
    with pytest.raises(ValidationError, match="unknown concepts: optics"):
        extraction(problems=[{"source_ref": "Q1", "prompt": "", "parts": [{"label": "1", "prompt": "x"}], "concepts": ["optics"]}])


def test_extraction_rejects_problems_with_the_same_id():
    part = [{"label": "1", "prompt": "x"}]
    with pytest.raises(ValidationError, match="source references"):
        extraction(problems=[
            {"source_ref": "PS1 #1", "prompt": "", "parts": part, "concepts": []},
            {"source_ref": "ps1-1", "prompt": "", "parts": part, "concepts": []},
        ])


def test_extraction_rejects_part_labels_with_the_same_id():
    with pytest.raises(ValidationError, match="part labels"):
        extraction(problems=[{"source_ref": "Q1", "prompt": "", "concepts": [],
                              "parts": [{"label": "(a)", "prompt": "x"}, {"label": "a.", "prompt": "y"}]}])


def test_extraction_rejects_duplicate_concepts():
    with pytest.raises(ValidationError, match="concept ids"):
        extraction(concepts=("vectors", "vectors", "gravity", "range"))


def test_extraction_needs_a_problem():
    with pytest.raises(ValidationError):
        extraction(problems=[])
