"""Choosing practice exercises by SQL feature. See architecture/sql-lessons.md, In a lesson."""

import random

import pytest

from kedami_server.practice import Exercise, choose


def ex(id: str, database: str, *features: str) -> Exercise:
    return Exercise(id, database, f"Question {id}", f"SELECT {id}", frozenset({"selecting", *features}))


BANK = [
    ex("plain-1", "music"),
    ex("plain-2", "music"),
    ex("where-1", "music", "filtering"),
    ex("where-2", "music", "filtering"),
    ex("where-3", "zoo", "filtering"),
    ex("where-sort", "music", "filtering", "sorting"),
    ex("sort-1", "zoo", "sorting"),
    ex("count-1", "music", "aggregates"),
    ex("count-where", "music", "aggregates", "filtering"),
    ex("group-1", "zoo", "aggregates", "grouping"),
    ex("group-2", "zoo", "aggregates", "grouping"),
    ex("group-having", "zoo", "aggregates", "grouping", "having"),
    ex("join-1", "school", "joins"),
    ex("join-where", "school", "joins", "filtering"),
    ex("join-group", "school", "joins", "aggregates", "grouping"),
]
by_id = {e.id: e for e in BANK}


def ids(chosen):
    return [[e.id for e in section] for section in chosen]


def test_each_exercise_uses_only_what_is_taught_by_its_section_and_something_the_section_teaches():
    sections = [{"selecting"}, {"filtering"}, {"sorting"}, {"aggregates", "grouping"}, {"having"}, {"joins"}]
    taught = set()
    for teaches, chosen in zip(sections, choose(BANK, sections)):
        taught |= teaches | {"selecting"}
        for exercise in chosen:
            assert exercise.features <= taught, exercise.id
            assert exercise.features & teaches, exercise.id


def test_a_section_teaching_selecting_gets_plain_selects():
    assert ids(choose(BANK, [{"selecting"}])) == [["plain-1", "plain-2"]]


def test_selecting_counts_as_taught_even_when_no_section_names_it():
    assert ids(choose(BANK, [{"joins"}])) == [["join-1"]]


def test_fewer_features_come_first_and_a_section_keeps_to_one_database_where_it_can():
    # Filtering alone: music has where-1 and where-2; zoo has only where-3.
    assert ids(choose(BANK, [{"filtering"}])) == [["where-1", "where-2", "where-3"]]
    assert ids(choose(BANK, [{"filtering"}], per_section=2)) == [["where-1", "where-2"]]


def test_a_later_section_needs_a_feature_it_teaches_not_only_earlier_ones():
    chosen = ids(choose(BANK, [{"filtering"}, {"sorting"}], per_section=5))
    assert chosen[0] == ["where-1", "where-2", "where-3"]
    assert sorted(chosen[1]) == ["sort-1", "where-sort"]


def test_an_exercise_using_a_feature_taught_later_waits_for_it():
    chosen = ids(choose(BANK, [{"aggregates"}, {"grouping"}], per_section=5))
    assert "group-1" not in chosen[0] and "group-1" in chosen[1]
    assert "count-where" not in chosen[0]


def test_no_exercise_is_chosen_twice():
    chosen = ids(choose(BANK, [{"filtering"}, {"filtering"}, {"filtering"}]))
    flat = [i for section in chosen for i in section]
    assert len(flat) == len(set(flat))
    assert chosen[2] == []


@pytest.mark.parametrize("sections", [[set()], [{"window functions"}]])
def test_a_section_teaching_no_listed_feature_gets_none(sections):
    assert ids(choose(BANK, sections)) == [[]]


def test_an_empty_bank_gives_no_practice():
    assert ids(choose([], [{"selecting"}, {"joins"}])) == [[], []]


def test_the_choice_doesnt_depend_on_the_banks_order():
    sections = [{"selecting"}, {"filtering"}, {"aggregates", "grouping"}, {"joins"}]
    expected = ids(choose(BANK, sections))
    for seed in range(5):
        shuffled = BANK[:]
        random.Random(seed).shuffle(shuffled)
        assert ids(choose(shuffled, sections)) == expected


def test_a_short_database_is_topped_up_from_others_in_feature_order():
    bank = [ex("a1", "a", "joins"), ex("b1", "b", "joins"), ex("b2", "b", "joins", "filtering"), ex("c1", "c", "joins")]
    assert ids(choose(bank, [{"joins", "filtering"}], per_section=3)) == [["b1", "b2", "a1"]]
