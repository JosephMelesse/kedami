"""Unit coverage: every shown passage is in exactly one unit or skipped range. See Stage 2 in architecture/pipeline.md."""

import pytest
from pydantic import ValidationError

from kedami_server.generation.passages import NOTE, TEXT, Passage
from kedami_server.generation.schemas import Extraction
from kedami_server.generation.units import UnitError, check_units, skipped_passages, source_runs

from .factories import passages


def unit(id, first, last):
    return {"id": id, "title": id.title(), "summary": f"About {id}.", "first": first, "last": last}


QUESTION = {"source_ref": "Q1", "prompt": "", "parts": [{"label": "1", "prompt": "x"}], "units": []}


def cut(units, skipped=(), problems=(QUESTION,)):
    return Extraction.model_validate(
        {
            "units": units,
            "skipped": [{"first": a, "last": b, "reason": r} for a, b, r in skipped],
            "problems": list(problems),
        }
    )


def problem_text(units, skipped=(), shown=None):
    with pytest.raises(UnitError) as raised:
        check_units(cut(units, skipped), shown or passages("a", "b", "c", "d", "e"))
    return str(raised.value)


def test_units_and_skipped_ranges_that_cover_every_passage_once_pass():
    check_units(cut([unit("a", 1, 2), unit("b", 4, 5)], [(3, 3, "a repeated slide")]), passages(*"abcde"))


def test_a_single_unit_may_cover_everything():
    check_units(cut([unit("all", 1, 5)]), passages(*"abcde"))


def test_a_gap_is_reported_with_its_passage_numbers():
    text = problem_text([unit("a", 1, 1), unit("b", 5, 5)])
    assert "in no unit or skipped range: p2-p4" in text


def test_separate_gaps_are_each_listed():
    text = problem_text([unit("a", 2, 2), unit("b", 4, 4)])
    assert "p1, p3, p5" in text


def test_an_overlap_between_units_names_both():
    text = problem_text([unit("a", 1, 3), unit("b", 3, 5)])
    assert "p3 is in more than one place: unit a, unit b" in text


def test_an_overlap_with_a_skipped_range_names_it():
    text = problem_text([unit("a", 1, 5)], [(5, 5, "bibliography")])
    assert "p5 is in more than one place: unit a, skipped range 1" in text


@pytest.mark.parametrize("first, last", [(0, 2), (4, 6), (6, 7)])
def test_a_range_outside_the_passages_is_rejected(first, last):
    text = problem_text([unit("a", first, last)])
    assert f"unit a (p{first}-p{last}) is outside the passages, p1-p5" in text


def test_a_range_that_ends_before_it_starts_is_rejected():
    assert "unit a starts at p4 after it ends at p2" in problem_text([unit("a", 4, 2)])


def test_a_skipped_range_out_of_bounds_is_rejected():
    assert "skipped range 1 (p5-p9)" in problem_text([unit("a", 1, 4)], [(5, 9, "logistics")])


def test_every_problem_is_listed_in_one_reply():
    text = problem_text([unit("a", 1, 2), unit("b", 2, 3)])
    assert "p2 is in more than one place" in text and "p4-p5" in text


def test_a_unit_stays_in_one_file():
    shown = passages("a", "b") + [Passage(3, TEXT, "more.pdf", 1, "c")]
    text = problem_text([unit("a", 1, 3)], shown=shown)
    assert "unit a runs across files (reference.md, more.pdf)" in text


def test_a_skipped_range_may_run_across_files():
    shown = passages("a", "b") + [Passage(3, TEXT, "more.pdf", 1, "c")]
    check_units(cut([unit("a", 1, 1)], [(2, 3, "contents")]), shown)


def with_notes():
    """p1 text, p2 note, p3 text, p4 note."""
    return [
        Passage(1, TEXT, "r.pdf", 1, "Lenses bend light."),
        Passage(2, NOTE, "r.pdf", 1, "[Figure: a ray diagram]"),
        Passage(3, TEXT, "r.pdf", 2, "Mirrors reflect it."),
        Passage(4, NOTE, "r.pdf", 2, "[Figure: a mirror]"),
    ]


def test_a_note_may_fall_outside_every_range():
    check_units(cut([unit("a", 1, 1), unit("b", 3, 3)]), with_notes())


def test_a_note_may_be_in_two_ranges():
    check_units(cut([unit("a", 1, 2)], [(2, 3, "a repeated slide")]), with_notes())


def test_a_unit_of_only_notes_is_rejected():
    text = problem_text([unit("a", 1, 1), unit("fig", 2, 2), unit("b", 3, 4)], shown=with_notes())
    assert "unit fig holds no text, only figure notes" in text


def test_unit_ids_are_unique():
    with pytest.raises(ValidationError, match="unit ids must be unique; repeated: a"):
        cut([unit("a", 1, 2), unit("a", 3, 5)])


def test_a_problem_needing_an_unknown_unit_is_rejected():
    problems = [{"source_ref": "Q1", "prompt": "", "parts": [{"label": "1", "prompt": "x"}], "units": ["optics"]}]
    with pytest.raises(ValidationError, match="Q1 needs unknown units: optics"):
        cut([unit("a", 1, 5)], problems=problems)


def test_an_extraction_needs_a_unit():
    with pytest.raises(ValidationError):
        cut([], [(1, 5, "all logistics")])


def test_skipped_passages_count_only_shown_ones():
    data = cut([unit("a", 1, 1)], [(2, 4, "logistics")])
    assert skipped_passages(data, with_notes()) == 1


# Source blocks


def test_a_unit_is_one_run_of_its_text_passages_without_notes():
    [run] = source_runs(cut([unit("a", 1, 4)]).units[0], with_notes())
    assert [p.number for p in run] == [1, 3]


def test_a_unit_takes_only_its_own_passages():
    data = cut([unit("a", 1, 2), unit("b", 3, 5)])
    [run] = source_runs(data.units[1], passages(*"abcde"))
    assert [p.text for p in run] == ["c", "d", "e"]
