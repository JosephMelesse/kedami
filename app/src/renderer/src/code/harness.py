"""Runs a student's solution against a LeetCode problem's tests, inside Pyodide in the runner frame.

`run_json` takes a request as JSON and returns the results as JSON, passing each test's result to `report`
as it finishes. Each request starts from a fresh namespace. Time limits are the frame's job: it ends the
worker. See architecture/code-problems.md, Runner.
"""

import io
import json
import linecache
import traceback
import warnings
from contextlib import redirect_stderr, redirect_stdout

SOLUTION_FILE = "solution.py"

# Longest text sent back for a returned value, printed output, or an error.
LIMIT = 1000

# Most nodes walked when showing a returned list or tree, so a cycle can't hang the display.
MAX_NODES = 10_000

# What LeetCode's Python environment provides before the student's code runs.
PRELUDE = """\
import bisect, collections, datetime, functools, heapq, itertools, math, operator, random, re, string
from typing import *
from bisect import *
from collections import *
from functools import *
from heapq import *
from itertools import *
from math import *
from operator import *
from string import *
from sortedcontainers import SortedDict, SortedList, SortedSet

inf = float('inf')


class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next


class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right
"""


def run_json(request: str, report=None) -> str:
    on_result = (lambda result: report(json.dumps(result))) if report else None
    return json.dumps(run(**json.loads(request), on_result=on_result))


def run(code: str, method: str, tests: list[dict], stop_at_failure: bool, on_result=None) -> dict:
    namespace: dict = {"__name__": "solution"}
    exec(PRELUDE, namespace)
    values = _values(namespace["ListNode"], namespace["TreeNode"])

    linecache.cache[SOLUTION_FILE] = (len(code), None, code.splitlines(keepends=True), SOLUTION_FILE)
    output = io.StringIO()
    try:
        with redirect_stdout(output), redirect_stderr(output):
            exec(compile(code, SOLUTION_FILE, "exec"), namespace)
    except BaseException as error:  # noqa: BLE001 - the student's code may raise anything, even SystemExit
        return _ran(_describe(error), output, [])

    solution = namespace.get("Solution")
    if not isinstance(solution, type) or not callable(getattr(solution, method, None)):
        return _ran(f"Define a class Solution with a method {method}.", output, [])

    results = []
    for test in tests:
        result = _run_test(solution, method, test, values)
        results.append(result)
        if on_result:
            on_result(result)
        if stop_at_failure and not result["passed"]:
            break
    return _ran(None, output, results)


def _run_test(solution: type, method: str, test: dict, values: dict) -> dict:
    try:
        with warnings.catch_warnings():
            # The dataset's strings hold escapes such as "\:" that Python warns about but reads.
            warnings.simplefilter("ignore", SyntaxWarning)
            args, kwargs = eval(f"__call({test['args']})", values)
            expected = eval(test["expected"], values)
    except Exception:  # noqa: BLE001 - a broken test, not the student's error
        return {"passed": False, "got": None, "output": "", "error": "This test can't be read."}

    output = io.StringIO()
    try:
        with redirect_stdout(output), redirect_stderr(output):
            got = getattr(solution(), method)(*args, **kwargs)
    except BaseException as error:  # noqa: BLE001
        return {"passed": False, "got": None, "output": _tail(output.getvalue()), "error": _describe(error)}

    compare = test["compare"]
    if compare in CHECKERS:
        # Read again, since the solution may have changed its arguments. The checkers use them by name.
        _, kwargs = eval(f"__call({test['args']})", values)
    return {
        "passed": _matches(compare, got, expected, kwargs),
        "got": _show(compare, got),
        "output": _tail(output.getvalue()),
        "error": None,
    }


def _values(list_node_class: type, tree_node_class: type) -> dict:
    """The names a test's arguments and expected value may use."""

    def list_node(values: list):
        head = None
        for value in reversed(values):
            head = list_node_class(value, head)
        return head

    def tree_node(values: list):
        # LeetCode's level order, with None for a missing child. Built as the dataset's helper builds it,
        # since its expected values were made with that helper.
        if not values:
            return None
        root = tree_node_class(values[0])
        parents, i = [root], 1
        for parent in parents:
            if i >= len(values):
                break
            for side in ("left", "right"):
                if i < len(values) and values[i] is not None:
                    child = tree_node_class(values[i])
                    setattr(parent, side, child)
                    parents.append(child)
                i += 1
        return root

    return {
        "__call": lambda *args, **kwargs: (args, kwargs),
        "list_node": list_node,
        "tree_node": tree_node,
        "inf": float("inf"),
    }


# The comparisons that check the returned value against the test's arguments.
CHECKERS = ("longest_palindrome", "course_order", "alien_order")

# How far a float may be from the expected number, relative to it when it is above 1, as LeetCode allows.
TOLERANCE = 1e-5


def _matches(compare: str, got, expected, args: dict) -> bool:
    """Whether the returned value passes. See the comparisons table in architecture/code-problems.md, Runner."""
    try:
        if compare == "equal":
            return _equal(_lists(got), _lists(expected))
        if compare == "same_list":
            return _same_list(got, expected)
        if compare == "same_tree":
            return _same_tree(got, expected)
        if compare == "unordered":
            return _unordered(got, expected, nested=False)
        if compare == "unordered_nested":
            return _unordered(got, expected, nested=True)
        if compare == "longest_palindrome":
            s = args["s"]
            return isinstance(got, str) and got == got[::-1] and got in s and len(got) == len(expected)
        if compare == "course_order":
            return got == [] if expected == [] else _course_order(args["numCourses"], args["prerequisites"], got)
        if compare == "alien_order":
            return got == "" if expected == "" else _alien_order(args["words"], got)
    except Exception:  # noqa: BLE001 - a returned value that can't be compared doesn't match
        return False
    raise ValueError(f"unknown comparison {compare!r}")


def _lists(value):
    """Tuples read as lists, at any depth."""
    return [_lists(v) for v in value] if isinstance(value, (list, tuple)) else value


def _equal(got, expected) -> bool:
    if isinstance(got, list) and isinstance(expected, list):
        return len(got) == len(expected) and all(_equal(a, b) for a, b in zip(got, expected))
    if _is_number(got) and _is_number(expected) and (isinstance(got, float) or isinstance(expected, float)):
        return bool(got == expected) or abs(got - expected) <= TOLERANCE * max(1, abs(expected))
    return bool(got == expected)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _unordered(got, expected, nested: bool) -> bool:
    """The same items, each as many times, in any order; with `nested`, each list item in any order too."""
    if not isinstance(got, (list, tuple)):
        return False

    def counted(items: list) -> list:
        if nested:
            items = [sorted(x, key=repr) if isinstance(x, list) else x for x in items]
        return sorted(items, key=repr)

    return counted(_lists(got)) == counted(_lists(expected))


def _course_order(courses: int, prerequisites: list, order) -> bool:
    """Every course once, each after its prerequisites."""
    if not isinstance(order, list) or sorted(order) != list(range(courses)):
        return False
    position = {course: i for i, course in enumerate(order)}
    return all(position[before] < position[after] for after, before in prerequisites)


def _alien_order(words: list, order) -> bool:
    """Each letter in the words once, in an order that sorts the words as given."""
    letters = {c for word in words for c in word}
    if not isinstance(order, str) or len(order) != len(letters) or set(order) != letters:
        return False
    rank = {c: i for i, c in enumerate(order)}
    keys = [[rank[c] for c in word] for word in words]
    return all(a <= b for a, b in zip(keys, keys[1:]))


def _same_list(got, expected) -> bool:
    # Walks only as far as the expected list, so a cycle in the returned one ends the walk.
    while got is not None and expected is not None:
        if got.val != expected.val:
            return False
        got, expected = got.next, expected.next
    return got is None and expected is None


def _same_tree(got, expected) -> bool:
    pairs = [(got, expected)]
    while pairs:
        a, b = pairs.pop()
        if a is None and b is None:
            continue
        if a is None or b is None or a.val != b.val:
            return False
        pairs += [(a.left, b.left), (a.right, b.right)]
    return True


def _show(compare: str, value) -> str:
    try:
        if compare == "same_list" and value is not None:
            return _cut(_list_values(value))
        if compare == "same_tree" and value is not None:
            return _cut(_tree_values(value))
        return _cut(repr(value))
    except Exception:  # noqa: BLE001
        return "(can't be shown)"


def _list_values(head) -> str:
    values, seen = [], set()
    while head is not None:
        if id(head) in seen or len(values) >= MAX_NODES:
            return repr(values)[:-1] + ", ...]"
        seen.add(id(head))
        values.append(head.val)
        head = head.next
    return repr(values)


def _tree_values(root) -> str:
    # Level order with None for a missing child and trailing Nones dropped, as LeetCode shows trees.
    values, queue, seen, cut = [], [root], set(), False
    for node in queue:
        if node is None:
            values.append(None)
            continue
        if id(node) in seen or len(values) >= MAX_NODES:
            cut = True
            break
        seen.add(id(node))
        values.append(node.val)
        queue += [node.left, node.right]
    while values and values[-1] is None:
        values.pop()
    return repr(values)[:-1] + ", ...]" if cut else repr(values)


def _describe(error: BaseException) -> str:
    """The error with only the student's own lines in its traceback."""
    frames = [frame for frame in traceback.extract_tb(error.__traceback__) if frame.filename == SOLUTION_FILE]
    lines = traceback.format_exception_only(type(error), error)
    if frames:
        lines = ["Traceback (most recent call last):\n", *traceback.StackSummary.from_list(frames).format(), *lines]
    return _tail("".join(lines).rstrip("\n"))


def _ran(error: str | None, output: io.StringIO, results: list[dict]) -> dict:
    return {"error": error, "output": _tail(output.getvalue()), "results": results}


def _cut(text: str) -> str:
    return text if len(text) <= LIMIT else text[: LIMIT - 3] + "..."


def _tail(text: str) -> str:
    # Printed output and errors keep their end, where the last lines and the error itself are.
    return text if len(text) <= LIMIT else "..." + text[-(LIMIT - 3) :]
