"""Reading a pasted list of placeholders. One bad line rejects the whole list."""

import pytest

from kedami_server.placeholders import MAX_LINES, MAX_NAME, PlannedLesson, parse_list


def test_names_and_dates():
    planned, problems = parse_list("Week 1\nWeek 2 | 2026-12-01\n")
    assert planned == [PlannedLesson("Week 1"), PlannedLesson("Week 2", "2026-12-01")]
    assert problems == []


@pytest.mark.parametrize("text", [
    "Week 2|2026-12-01", "  Week 2  |  2026-12-01  ", "\tWeek 2\t|\t2026-12-01\t", "﻿Week 2 | 2026-12-01",
])
def test_spacing_around_the_pieces_does_not_matter(text):
    assert parse_list(text) == ([PlannedLesson("Week 2", "2026-12-01")], [])


def test_blank_lines_are_skipped_and_windows_line_endings_read():
    planned, problems = parse_list("\r\nWeek 1\r\n\r\n   \r\nWeek 2\r\n")
    assert [p.name for p in planned] == ["Week 1", "Week 2"]
    assert problems == []


def test_two_lines_may_share_a_name_and_order_is_kept():
    assert [p.name for p in parse_list("B\nA\nB")[0]] == ["B", "A", "B"]


def test_a_past_date_is_allowed():
    assert parse_list("Old | 2001-01-01")[0] == [PlannedLesson("Old", "2001-01-01")]


@pytest.mark.parametrize("line, reason", [
    ("A | B | 2026-12-01", "more than one |"),
    ("A | 2026-12-01 |", "more than one |"),
    ("||", "more than one |"),
    ("| 2026-12-01", "no name"),
    ("   | 2026-12-01", "no name"),
    ("|", "no name"),
    ("Week 1 |", "no date"),
    ("Week 1 |    ", "no date"),
    ("Week 1 | 2026-02-30", "isn't a real date"),
    ("Week 1 | 2027-02-29", "isn't a real date"),
    ("Week 1 | 20261201", "isn't a real date"),
    ("Week 1 | 2026-W44-7", "isn't a real date"),
    ("Week 1 | 12/01/2026", "isn't a real date"),
    ("Week 1 | tomorrow", "isn't a real date"),
    ("x" * (MAX_NAME + 1), "over 120"),
])
def test_a_line_that_cannot_be_read(line, reason):
    planned, problems = parse_list(line)
    assert planned == []
    assert len(problems) == 1
    assert problems[0].line == 1
    assert reason in problems[0].reason


def test_the_longest_name_is_read():
    assert parse_list("x" * MAX_NAME)[0][0].name == "x" * MAX_NAME


def test_one_bad_line_rejects_the_whole_list_and_every_bad_line_is_named():
    planned, problems = parse_list("Good\n\nA | B | C\nAlso good\nBad | 2026-13-01")
    assert planned == []
    assert [(p.line, p.text) for p in problems] == [(3, "A | B | C"), (5, "Bad | 2026-13-01")]


@pytest.mark.parametrize("text", ["", "\n\n", "   \n\t\n", "﻿"])
def test_an_empty_list_is_a_problem(text):
    planned, problems = parse_list(text)
    assert planned == []
    assert [p.reason for p in problems] == ["The list is empty."]


def test_the_longest_list_is_read():
    assert len(parse_list("\n".join(f"L{n}" for n in range(MAX_LINES)))[0]) == MAX_LINES


def test_a_longer_list_is_refused():
    planned, problems = parse_list("\n".join(f"L{n}" for n in range(MAX_LINES + 1)))
    assert planned == []
    assert problems[0].line == 0 and "at most 100" in problems[0].reason
