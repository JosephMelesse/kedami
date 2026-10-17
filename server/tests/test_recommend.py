"""Recommending problems for a SQL chapter. See architecture/sql-lessons.md, Recommending problems."""

import pytest

from kedami_server.practice import Exercise
from kedami_server.queries import FEATURES
from kedami_server.recommend import Recommendation, available, eligible, recommend
from kedami_server.sql_chapters import CHAPTERS, PAGE_PATH, chapter, known_features, page


def ex(id: str, database: str, *features: str) -> Exercise:
    return Exercise(id, database, f"Question {id}", f"SELECT {id}", frozenset({"selecting", *features}))


GROUPING = chapter(8)
BANK = [
    ex("plain", "music"),
    ex("count", "music", "aggregates"),
    ex("group-a1", "music", "aggregates", "grouping"),
    ex("group-a2", "music", "aggregates", "grouping", "filtering"),
    ex("group-b1", "zoo", "aggregates", "grouping"),
    ex("group-b2", "zoo", "grouping", "having", "aggregates"),
    ex("group-b3", "zoo", "aggregates", "grouping", "sorting"),
    ex("group-c1", "farm", "aggregates", "grouping"),
    ex("group-join", "zoo", "aggregates", "grouping", "joins"),
    ex("group-sub", "zoo", "aggregates", "grouping", "subqueries"),
]


def ids(recommendations):
    return [r.id for r in recommendations]


# Chapters


def test_chapters_are_numbered_in_order_and_each_recommends_from_one_source():
    assert [c.number for c in CHAPTERS] == list(range(1, 16))
    for c in CHAPTERS:
        assert bool(c.features) != bool(c.pages), c.name


def test_each_spider_feature_belongs_to_one_chapter():
    owned = [f for c in CHAPTERS for f in c.features]
    assert len(owned) == len(set(owned))
    assert set(owned) == set(FEATURES)


def test_every_pgexercises_page_is_a_section_and_a_page_name():
    for c in CHAPTERS:
        for p in c.pages:
            assert PAGE_PATH.match(p.path), p.path
            assert page(p.path) == p
    assert page("joins/nowhere.html") is None


def test_a_chapter_knows_its_features_and_every_earlier_chapters():
    assert known_features(8) == {
        "selecting", "filtering", "patterns", "sorting", "limiting", "distinct", "aggregates", "grouping", "having"
    }
    assert "joins" not in known_features(8)
    assert known_features(1) == {"selecting"}


def test_an_unknown_chapter_is_refused():
    with pytest.raises(KeyError):
        chapter(16)


# Eligibility


def test_a_problem_must_use_the_chapter_and_nothing_from_a_later_one():
    chosen = ids(eligible(BANK, GROUPING))
    assert "group-a2" in chosen and "group-b2" in chosen and "group-b3" in chosen
    assert "count" not in chosen and "plain" not in chosen  # doesn't group
    assert "group-join" not in chosen and "group-sub" not in chosen  # joins and subqueries come later


def test_the_selecting_chapter_takes_only_plain_selects():
    assert ids(eligible(BANK, chapter(1))) == ["plain"]


# Recommending


def test_a_recommendation_keeps_to_the_database_with_the_most_problems_fewest_features_first():
    recs = recommend(BANK, GROUPING, 3)
    assert ids(recs) == ["group-b1", "group-b2", "group-b3"]
    assert recs[0] == Recommendation("spider", "group-b1", "Question group-b1", "zoo")


def test_a_short_database_is_topped_up_from_the_next():
    assert ids(recommend(BANK, GROUPING, 5)) == ["group-b1", "group-b2", "group-b3", "group-a1", "group-a2"]


def test_recommend_again_starts_from_the_next_database_and_wraps_around():
    first = ids(recommend(BANK, GROUPING, 2, round_=0))
    second = ids(recommend(BANK, GROUPING, 2, round_=1))
    third = ids(recommend(BANK, GROUPING, 2, round_=2))
    assert first == ["group-b1", "group-b2"]
    assert second == ["group-a1", "group-a2"]
    assert third == ["group-c1", "group-b1"]
    assert ids(recommend(BANK, GROUPING, 2, round_=3)) == first


def test_the_number_of_problems_is_kept_between_one_and_ten():
    assert len(recommend(BANK, GROUPING, 0)) == 1
    many = [ex(f"g{n:02d}", "big", "aggregates", "grouping") for n in range(20)]
    assert len(recommend(many, GROUPING, 50)) == 10


def test_a_pgexercises_chapter_recommends_its_pages_up_to_the_number():
    dates = chapter(15)
    recs = recommend([], dates, 3)
    assert [r.source for r in recs] == ["pgexercises"] * 3
    assert recs[0] == Recommendation("pgexercises", "basic/date.html", "Working with dates")
    outer = recommend([], chapter(10), 5)
    assert ids(outer) == ["joins/self.html", "joins/self2.html"]


def test_with_nothing_imported_a_spider_chapter_recommends_nothing():
    assert recommend([], GROUPING, 5) == []
    assert available([], GROUPING) == 0


def test_available_counts_what_a_chapter_can_recommend():
    assert available(BANK, GROUPING) == 6
    assert available(BANK, chapter(13)) == 3


def test_the_recommendation_doesnt_depend_on_the_banks_order():
    assert ids(recommend(list(reversed(BANK)), GROUPING, 5)) == ids(recommend(BANK, GROUPING, 5))
