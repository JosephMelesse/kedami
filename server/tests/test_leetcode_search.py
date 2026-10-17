import json
import os

import pytest
from fastapi.testclient import TestClient

from kedami_server import db
from kedami_server.app import create_app
from kedami_server.config import Settings
from kedami_server.generation.leetcode import leetcode_slug
from kedami_server.import_leetcode import OUTPUT
from kedami_server.leetcode_search import MAX_RESULTS, entries, search, title_from_slug

PROBLEMS = [
    (1, "two-sum", "Easy"),
    (15, "3sum", "Medium"),
    (16, "3sum-closest", "Medium"),
    (18, "4sum", "Medium"),
    (50, "powx-n", "Medium"),
    (92, "reverse-linked-list-ii", "Medium"),
    (100, "same-tree", "Easy"),
    (151, "reverse-words-in-a-string", "Medium"),
    (167, "two-sum-ii-input-array-is-sorted", "Medium"),
    (206, "reverse-linked-list", "Easy"),
    (437, "path-sum-iii", "Medium"),
    (1001, "grid-illumination", "Hard"),
    (1679, "max-number-of-k-sum-pairs", "Medium"),
]


def write(data_dir, problems=PROBLEMS, extra=""):
    lines = [json.dumps({"number": n, "slug": s, "difficulty": d, "description": "...", "starter_code": "x",
                         "method": "f", "tests": []}) for n, s, d in problems]
    (data_dir / OUTPUT).write_text("\n".join(lines) + "\n" + extra)


@pytest.fixture
def data_dir(tmp_path):
    write(tmp_path)
    return tmp_path


def numbers(found):
    return [e.number for e in found]


@pytest.mark.parametrize(
    "slug, title",
    [
        ("two-sum", "Two Sum"),
        ("3sum", "3sum"),
        ("powx-n", "Powx N"),
        ("two-sum-ii-input-array-is-sorted", "Two Sum II Input Array Is Sorted"),
        ("path-sum-iii", "Path Sum III"),
        ("reverse-words-in-a-string", "Reverse Words In A String"),
    ],
)
def test_titles_are_made_from_slugs_and_derive_back_to_them(slug, title):
    assert title_from_slug(slug) == title
    assert leetcode_slug(title) == slug


def test_a_number_finds_problems_it_starts_with_exact_first(data_dir):
    assert numbers(search(data_dir, "1")) == [1, 15, 16, 18, 100, 151, 167, 1001][:MAX_RESULTS]
    assert numbers(search(data_dir, "15")) == [15, 151]
    assert numbers(search(data_dir, " 206 ")) == [206]
    assert search(data_dir, "9999") == []


def test_words_match_word_starts_in_any_order(data_dir):
    assert numbers(search(data_dir, "two s")) == [1, 167]
    assert numbers(search(data_dir, "sum two")) == [1, 167]
    assert numbers(search(data_dir, "Reverse")) == [206, 92, 151]
    assert numbers(search(data_dir, "linked rev")) == [206, 92]
    assert search(data_dir, "um") == []  # inside a word, not at its start


def test_the_exact_slug_comes_first_then_slugs_starting_with_the_words(data_dir):
    assert numbers(search(data_dir, "3sum")) == [15, 16]
    assert numbers(search(data_dir, "two sum")) == [1, 167]
    assert numbers(search(data_dir, "reverse linked")) == [206, 92]
    # No slug is "sum" or starts with it, so the matches come by how many words they have.
    assert numbers(search(data_dir, "sum")) == [1, 437, 1679, 167]


def test_a_number_among_words_may_be_the_problems_number(data_dir):
    assert numbers(search(data_dir, "1. two sum")) == [1]
    assert numbers(search(data_dir, "167 two")) == [167]


@pytest.mark.parametrize("query", ["", "   ", "!!", "-"])
def test_nothing_to_search_finds_nothing(data_dir, query):
    assert search(data_dir, query) == []


def test_results_stop_at_the_limit(tmp_path):
    write(tmp_path, [(n, f"sum-{n}", "Easy") for n in range(1, 40)])
    assert len(search(tmp_path, "sum")) == MAX_RESULTS


def test_without_an_import_search_finds_nothing(tmp_path):
    assert search(tmp_path, "two") == []


def test_damaged_lines_are_skipped(tmp_path):
    write(tmp_path, extra='{"number": 2, "slug": "Bad Slug", "difficulty": "Easy"}\nnot json\n{"number": 3, "slug": "ok", "difficulty": "Weird"}\n')
    assert [e.number for e in entries(tmp_path)] == [n for n, _, _ in PROBLEMS]


def test_a_new_import_is_picked_up(data_dir):
    assert numbers(search(data_dir, "two sum")) == [1, 167]
    write(data_dir, [(1, "two-sum", "Easy"), (2, "add-two-numbers", "Medium")])
    stat = (data_dir / OUTPUT).stat()
    os.utime(data_dir / OUTPUT, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    assert numbers(search(data_dir, "two")) == [1, 2]


def test_the_search_route(data_dir):
    db.init(data_dir)
    client = TestClient(create_app(Settings(port=0, token="t", data_dir=data_dir, allowed_origins=())))
    response = client.get("/leetcode/search", params={"q": "two sum ii"}, headers={"Authorization": "Bearer t"})
    assert response.json() == {"problems": [
        {"number": 167, "slug": "two-sum-ii-input-array-is-sorted", "title": "Two Sum II Input Array Is Sorted",
         "difficulty": "Medium"}
    ], "imported": True}
    too_long = client.get("/leetcode/search", params={"q": "x" * 201}, headers={"Authorization": "Bearer t"})
    assert too_long.status_code == 422


def test_the_search_route_says_when_nothing_is_imported(tmp_path):
    db.init(tmp_path)
    client = TestClient(create_app(Settings(port=0, token="t", data_dir=tmp_path, allowed_origins=())))
    response = client.get("/leetcode/search", params={"q": "koko"}, headers={"Authorization": "Bearer t"})
    assert response.json() == {"problems": [], "imported": False}
