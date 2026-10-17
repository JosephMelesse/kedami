import json

import pytest

from kedami_server.import_leetcode import OUTPUT, CodeTest, Dropped, convert, import_files, parse_tests, read


def record(**overrides) -> dict:
    """A dataset record shaped like LeetCodeDataset's, with only the fields the import reads changed."""
    base = {
        "task_id": "two-sum",
        "question_id": 1,
        "difficulty": "Easy",
        "tags": ["Array", "Hash Table"],
        "problem_description": "Given an array of integers nums\xa0and an integer target...\n\n",
        "starter_code": "class Solution:\n    def twoSum(self, nums: List[int], target: int) -> List[int]:\n        ",
        "prompt": "from typing import *\n",
        "completion": "class Solution:\n    def twoSum(self, nums, target):\n        ...",
        "entry_point": "Solution().twoSum",
        "test": "def check(candidate):\n"
        "    assert candidate(nums = [3, 3],target = 6) == [0, 1]\n"
        "    assert candidate(nums = [2, 7, 11, 15],target = 9) == [0, 1]\n",
        "input_output": [{"input": "nums = [3,3], target = 6", "output": "[0, 1]"}],
    }
    return base | overrides


def check(*asserts: str) -> str:
    return "def check(candidate):\n" + "".join(f"    assert {a}\n" for a in asserts)


def test_a_record_keeps_only_what_lessons_use():
    problem = convert(record())
    assert (problem.number, problem.slug, problem.difficulty, problem.method) == (1, "two-sum", "Easy", "twoSum")
    assert problem.description == "Given an array of integers nums\xa0and an integer target..."
    assert problem.starter_code.startswith("class Solution:")
    assert problem.tests == [
        CodeTest("nums = [3, 3], target = 6", "[0, 1]", "equal"),
        CodeTest("nums = [2, 7, 11, 15], target = 9", "[0, 1]", "equal"),
    ]


@pytest.mark.parametrize(
    "assertion, test",
    [
        ("candidate(s = \"(()\") == True", CodeTest('s = "(()"', "True", "equal")),
        ("candidate(x = -2.0,n = -2) == 0.25", CodeTest("x = -2.0, n = -2", "0.25", "equal")),
        ("candidate([1, 2], 3) == None", CodeTest("[1, 2], 3", "None", "equal")),
        ("candidate() == inf", CodeTest("", "inf", "equal")),
        (
            "is_same_list(candidate(l1 = list_node([2, 4, 3]),l2 = list_node([5, 6, 4])), list_node([7, 0, 8]))",
            CodeTest("l1 = list_node([2, 4, 3]), l2 = list_node([5, 6, 4])", "list_node([7, 0, 8])", "same_list"),
        ),
        (
            "is_same_tree(candidate(root = tree_node([4, 2, 7, None, 3])), tree_node([4, 7, 2, 3]))",
            CodeTest("root = tree_node([4, 2, 7, None, 3])", "tree_node([4, 7, 2, 3])", "same_tree"),
        ),
        (
            "candidate(words = ['a,b', \"c == d\"]) == ['a,b']",
            CodeTest("words = ['a,b', \"c == d\"]", "['a,b']", "equal"),
        ),
    ],
)
def test_each_assert_shape_becomes_a_test_with_its_text_as_written(assertion, test):
    assert parse_tests(check(assertion)) == [test]


def test_a_multiline_assert_keeps_its_text():
    source = "def check(candidate):\n    assert candidate(grid = [[1, 2],\n        [3, 4]]) == 10\n"
    assert parse_tests(source) == [CodeTest("grid = [[1, 2],\n        [3, 4]]", "10", "equal")]


def test_text_after_non_ascii_characters_is_cut_in_the_right_place():
    assert parse_tests(check('candidate(s = "héllo wörld",k = 2) == "wö"')) == [
        CodeTest('s = "héllo wörld", k = 2', '"wö"', "equal")
    ]


def test_unicode_line_breaks_inside_strings_dont_split_a_test():
    source = check('candidate(s = "a\x85b\u2028c") == "\x85"', 'candidate(s = "d") == "e"')
    assert parse_tests(source) == [
        CodeTest('s = "a\x85b\u2028c"', '"\x85"', "equal"),
        CodeTest('s = "d"', '"e"', "equal"),
    ]


def test_escapes_python_warns_about_still_read():
    assert parse_tests(check('candidate(s = "a\\:b") == 1')) == [CodeTest('s = "a\\:b"', "1", "equal")]


@pytest.mark.parametrize(
    "assertion",
    [
        "candidate(nums = [1]) != 2",
        "candidate(nums = [1]) is None",
        "candidate(nums = [1]) == 1 == 1",
        "1 == candidate(nums = [1])",
        "candidate(nums = [1])",
        "abs(candidate(x = 1.0) - 2.0) < 1e-5",
        "sorted(candidate(nums = [1])) == [1]",
        "is_same_list(list_node([1]), candidate(head = list_node([1])))",
        "is_same_tree(candidate(root = tree_node([1])), tree_node([1]), extra)",
        "is_same_graph(candidate(node = 1), 1)",
        "candidate(*args) == 1",
        "candidate(**kwargs) == 1",
        "other(nums = [1]) == 1",
    ],
)
def test_any_other_assert_shape_drops_the_problem(assertion):
    good = "candidate(nums = [1]) == 1"
    with pytest.raises(Dropped, match="a test has another shape"):
        parse_tests(check(good, assertion))


@pytest.mark.parametrize(
    "source, reason",
    [
        (check("candidate(nums = [1]) == 1") + "    print('done')\n", "a test has another shape"),
        ("def check(candidate):\n    for x in []:\n        assert candidate(x) == x\n", "a test has another shape"),
        ("def check(candidate)\n    assert candidate() == 1\n", "its tests can't be read"),
        ("assert candidate() == 1\n", "its tests can't be read"),
        (check("candidate() == 1") + check("candidate() == 2"), "its tests can't be read"),
    ],
)
def test_check_functions_that_cant_be_read_as_asserts_drop_the_problem(source, reason):
    with pytest.raises(Dropped, match=reason):
        parse_tests(source)


def test_a_check_with_no_asserts_drops_the_problem():
    with pytest.raises(Dropped, match="it has no tests"):
        convert(record(test="def check(candidate):\n    pass\n"))


@pytest.mark.parametrize(
    "starter_code",
    [
        "class Solution:\n    def twoSum(self, nums: List[int], k: int) -> None:\n        ",
        'class Solution:\n    def twoSum(self, nums: List[int]) -> None:\n        """\n        Do not return anything.\n        """\n',
        "class Solution:\n    def twoSum(self, nums: List[int])->None:\n        ",
    ],
)
def test_a_method_that_returns_none_drops_the_problem(starter_code):
    with pytest.raises(Dropped, match="it changes its input in place"):
        convert(record(starter_code=starter_code))


def test_none_returned_by_a_helper_in_the_starter_code_doesnt_drop_the_problem():
    starter = (
        "class Solution:\n    def twoSum(self, nums: List[int], target: int) -> List[int]:\n        \n"
        "    def helper(self) -> None:\n        "
    )
    assert convert(record(starter_code=starter)).method == "twoSum"


@pytest.mark.parametrize("entry_point", ["twoSum", "Solution.twoSum", "Solution().two-sum", "LRUCache().get", ""])
def test_an_entry_point_that_isnt_a_solution_method_drops_the_problem(entry_point):
    with pytest.raises(Dropped, match="its entry point isn't a Solution method"):
        convert(record(entry_point=entry_point))


@pytest.mark.parametrize(
    "broken",
    [
        {"question_id": None},
        {"question_id": "1"},
        {"question_id": 0},
        {"question_id": True},
        {"test": None},
        {"problem_description": 3},
    ],
)
def test_a_record_with_missing_or_wrong_fields_is_dropped(broken):
    with pytest.raises(Dropped, match="not a problem record"):
        convert(record(**broken))


def test_a_record_missing_a_field_is_dropped():
    data = record()
    del data["starter_code"]
    with pytest.raises(Dropped, match="not a problem record"):
        convert(data)


def write_jsonl(path, *lines):
    path.write_text("".join((line if isinstance(line, str) else json.dumps(line)) + "\n" for line in lines))
    return path


def read_output(data_dir):
    return [json.loads(line) for line in (data_dir / OUTPUT).read_text().splitlines()]


def test_import_writes_kept_problems_by_number_and_counts_every_drop(tmp_path):
    train = write_jsonl(
        tmp_path / "train.jsonl",
        record(question_id=15, task_id="3sum"),
        record(question_id=189, starter_code="class Solution:\n    def twoSum(self, nums) -> None:\n        "),
        "{not json",
        "",
        ["not", "a", "record"],
    )
    test = write_jsonl(tmp_path / "test.jsonl", record(), record(task_id="two-sum-again"))
    summary = import_files(tmp_path, [train, test])

    assert summary.kept == 2
    assert dict(summary.dropped) == {
        "it changes its input in place": 1,
        "not a problem record": 2,
        "it was listed more than once": 1,
    }
    assert str(summary).splitlines()[0] == "kept 2 problems, dropped 4"
    problems = read_output(tmp_path)
    assert [(p["number"], p["slug"]) for p in problems] == [(1, "two-sum"), (15, "3sum")]
    assert set(problems[0]) == {"number", "slug", "difficulty", "description", "starter_code", "method", "tests"}
    assert problems[0]["tests"][0] == {"args": "nums = [3, 3], target = 6", "expected": "[0, 1]", "compare": "equal"}
    assert "\xa0" in problems[0]["description"]


def test_each_problem_is_written_on_one_ascii_line(tmp_path):
    import_files(tmp_path, [write_jsonl(tmp_path / "a.jsonl", record(problem_description="a\x85b\u2028c\xa0d"))])
    raw = (tmp_path / OUTPUT).read_bytes()
    assert raw.isascii() and raw.count(b"\n") == 1
    assert read_output(tmp_path)[0]["description"] == "a\x85b\u2028c\xa0d"


def test_a_second_import_replaces_the_first(tmp_path):
    import_files(tmp_path, [write_jsonl(tmp_path / "a.jsonl", record(), record(question_id=15, task_id="3sum"))])
    summary = import_files(tmp_path, [write_jsonl(tmp_path / "b.jsonl", record(question_id=20, task_id="valid"))])
    assert summary.kept == 1
    assert [p["number"] for p in read_output(tmp_path)] == [20]
    assert not (tmp_path / (OUTPUT + ".partial")).exists()


def test_an_import_that_fails_partway_leaves_the_earlier_one(tmp_path):
    import_files(tmp_path, [write_jsonl(tmp_path / "a.jsonl", record())])
    with pytest.raises(FileNotFoundError):
        import_files(tmp_path, [write_jsonl(tmp_path / "b.jsonl", record(question_id=20)), tmp_path / "missing.jsonl"])
    assert [p["number"] for p in read_output(tmp_path)] == [1]


def test_an_import_with_nothing_kept_writes_an_empty_file(tmp_path):
    summary = import_files(tmp_path, [write_jsonl(tmp_path / "a.jsonl", "{bad")])
    assert summary.kept == 0
    assert (tmp_path / OUTPUT).read_text() == ""


def test_read_returns_only_the_problems_asked_for(tmp_path):
    import_files(tmp_path, [write_jsonl(tmp_path / "a.jsonl", record(), record(question_id=15, task_id="3sum"),
                                        record(question_id=150, task_id="evaluate"))])
    found = read(tmp_path, {15, 1, 99})
    assert sorted(found) == [1, 15]
    assert found[15]["slug"] == "3sum" and found[1]["tests"][0]["expected"] == "[0, 1]"


def test_read_without_an_import_or_numbers_finds_nothing(tmp_path):
    assert read(tmp_path, {1}) == {}
    import_files(tmp_path, [write_jsonl(tmp_path / "a.jsonl", record())])
    assert read(tmp_path, set()) == {}


def test_read_skips_damaged_lines(tmp_path):
    (tmp_path / OUTPUT).write_text('{"number": 1, "slug": "two-su\n{"number": 2, "slug": "add"}\nnot json\n')
    assert read(tmp_path, {1, 2}) == {2: {"number": 2, "slug": "add"}}
