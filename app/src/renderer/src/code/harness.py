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
    return {
        "passed": _matches(compare, got, expected),
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


def _matches(compare: str, got, expected) -> bool:
    try:
        if compare == "equal":
            return bool(got == expected)
        if compare == "same_list":
            return _same_list(got, expected)
        if compare == "same_tree":
            return _same_tree(got, expected)
    except Exception:  # noqa: BLE001 - a returned value that can't be compared doesn't match
        return False
    raise ValueError(f"unknown comparison {compare!r}")


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
