import pytest

from kedami_server.generation.leetcode import ListedProblem, ProblemListError, leetcode_slug, parse_problem_list


@pytest.mark.parametrize(
    "line, number, title",
    [
        ("1. Two Sum", 1, "Two Sum"),
        ("15 3Sum", 15, "3Sum"),
        ("#20 Valid Parentheses", 20, "Valid Parentheses"),
        ("# 20. Valid Parentheses", 20, "Valid Parentheses"),
        ("LeetCode 70 - Climbing Stairs", 70, "Climbing Stairs"),
        ("leetcode #121: Best Time to Buy and Sell Stock", 121, "Best Time to Buy and Sell Stock"),
        ("- 206) Reverse Linked List", 206, "Reverse Linked List"),
        ("* 50. Pow(x, n)", 50, "Pow(x, n)"),
        ("   3.   Longest Substring Without Repeating Characters   ", 3, "Longest Substring Without Repeating Characters"),
    ],
)
def test_problem_lines(line, number, title):
    assert parse_problem_list(line) == [ListedProblem(number, title)]


def test_a_whole_list_keeps_its_order_and_skips_headings_and_page_markers():
    text = "[problems.md, page 1]\n\n# Week 3: Hashing\n\n1. Two Sum\n\n## Stretch\n217. Contains Duplicate\n"
    assert [(p.number, p.title) for p in parse_problem_list(text)] == [(1, "Two Sum"), (217, "Contains Duplicate")]


@pytest.mark.parametrize(
    "text, message",
    [
        ("Two Sum", "line 1 isn't a problem number and title: 'Two Sum'"),
        ("1. Two Sum\nsolve these by Friday", "line 2 isn't a problem number"),
        ("1.", "line 1 has a number but no title"),
        ("42", "line 1 has a number but no title"),
        ("0. Nothing", "no problem number above 0"),
        ("1. Two Sum\n1. Two Sum Again", "line 2 repeats problem 1 from line 1"),
        ("7. ???", "has no letters or digits"),
        ("1. " + "x" * 201, "longer than 200"),
        ("", "empty"),
        ("# Week 3\n\n", "empty"),
    ],
)
def test_lists_that_cannot_be_read(text, message):
    with pytest.raises(ProblemListError, match=message.replace("?", "\\?").replace("(", "\\(")):
        parse_problem_list(text)


def test_every_bad_line_is_reported_at_once():
    with pytest.raises(ProblemListError) as error:
        parse_problem_list("1. Two Sum\nfoo\n2.\nbar")
    assert "line 2" in str(error.value) and "line 3" in str(error.value) and "line 4" in str(error.value)


def test_long_error_lists_are_cut_short():
    with pytest.raises(ProblemListError, match="and 5 more"):
        parse_problem_list("\n".join(f"bad line {i}" for i in range(15)))


@pytest.mark.parametrize(
    "title, slug",
    [
        ("Two Sum", "two-sum"),
        ("3Sum", "3sum"),
        ("Pow(x, n)", "powx-n"),
        ("Two Sum II - Input Array Is Sorted", "two-sum-ii-input-array-is-sorted"),
        ("Pascal's Triangle", "pascals-triangle"),
        ("  LRU   Cache  ", "lru-cache"),
        ("Best Time to Buy and Sell Stock IV", "best-time-to-buy-and-sell-stock-iv"),
    ],
)
def test_slugs_follow_leetcode(title, slug):
    assert leetcode_slug(title) == slug


def test_source_reference():
    assert ListedProblem(1, "Two Sum").source_ref == "LeetCode #1"
