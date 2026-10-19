"""Import LeetCodeDataset's problems and tests into the data folder.

Run as `python -m kedami_server.import_leetcode DATA_DIR FILE...`, with the dataset's JSONL files.
Writes `leetcode.jsonl`, replacing any earlier import, with the checked-in fixes applied. See
architecture/code-problems.md, Dataset and Fixes.

Tests are read with Python's `ast` parser and never run here: their arguments and expected
values are kept as source text, evaluated only in the sandboxed runner.
"""

import ast
import json
import os
import re
import sys
import warnings
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import get_args

from .lesson import Comparison

OUTPUT = "leetcode.jsonl"

# Hand-made fixes for the dataset's tests, by problem number. See architecture/code-problems.md, Fixes.
FIXES = Path(__file__).with_name("leetcode_fixes.json")

COMPARISONS = get_args(Comparison)

# The dataset names each problem's entry point as "Solution().methodName".
_ENTRY_POINT = re.compile(r"^Solution\(\)\.(?P<method>[A-Za-z_]\w*)$")

# The two helpers the dataset's tests compare linked lists and trees with, by our comparison name.
_NODE_COMPARISONS = {"is_same_list": "same_list", "is_same_tree": "same_tree"}


class Dropped(ValueError):
    """A problem left out of the import, with the reason the summary counts it under."""


@dataclass(frozen=True)
class CodeTest:
    args: str
    expected: str
    compare: str


@dataclass(frozen=True)
class Problem:
    number: int
    slug: str
    difficulty: str
    description: str
    starter_code: str
    method: str
    tests: list[CodeTest]


def convert(record: dict) -> Problem:
    """One dataset record as a problem, or Dropped with the reason."""
    try:
        number, slug, check = record["question_id"], record["task_id"], record["test"]
        entry_point, starter_code = record["entry_point"], record["starter_code"]
        difficulty, description = record["difficulty"], record["problem_description"]
    except (KeyError, TypeError):
        raise Dropped("not a problem record") from None
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        raise Dropped("not a problem record")
    if not all(isinstance(v, str) for v in (slug, check, entry_point, starter_code, difficulty, description)):
        raise Dropped("not a problem record")
    match = _ENTRY_POINT.match(entry_point)
    if not match:
        raise Dropped("its entry point isn't a Solution method")
    method = match["method"]
    if re.search(rf"def\s+{method}\s*\(.*\)\s*->\s*None\s*:", starter_code):
        raise Dropped("it changes its input in place")
    tests = parse_tests(check)
    if not tests:
        raise Dropped("it has no tests")
    return Problem(number, slug, difficulty, description.strip(), starter_code, method, tests)


def parse_tests(source: str) -> list[CodeTest]:
    """Each top-level assert in the check function, as a test. Raises Dropped for any other shape."""
    try:
        with warnings.catch_warnings():
            # The dataset's strings hold escapes such as "\:" that Python warns about but reads.
            warnings.simplefilter("ignore", SyntaxWarning)
            module = ast.parse(source)
    except SyntaxError:
        raise Dropped("its tests can't be read") from None
    text = _Source(source)
    checks = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "check"]
    if len(checks) != 1:
        raise Dropped("its tests can't be read")
    tests = []
    for statement in checks[0].body:
        if isinstance(statement, ast.Pass):
            continue
        if not isinstance(statement, ast.Assert):
            raise Dropped("a test has another shape")
        tests.append(_test(text, statement.test))
    return tests


def _test(source: "_Source", node: ast.expr) -> CodeTest:
    # candidate(args) == expected
    if (
        isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.Eq)
        and _is_candidate_call(node.left)
    ):
        return CodeTest(_args(source, node.left), source.segment(node.comparators[0]), "equal")
    # is_same_list(candidate(args), expected), and the same for trees
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _NODE_COMPARISONS
        and len(node.args) == 2
        and not node.keywords
        and _is_candidate_call(node.args[0])
    ):
        return CodeTest(_args(source, node.args[0]), source.segment(node.args[1]), _NODE_COMPARISONS[node.func.id])
    raise Dropped("a test has another shape")


def _is_candidate_call(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "candidate"
        and not any(isinstance(a, ast.Starred) for a in node.args)
        and not any(k.arg is None for k in node.keywords)
    )


def _args(source: "_Source", call: ast.Call) -> str:
    """The call's arguments as written, such as "nums = [3, 3], target = 6"."""
    return ", ".join(source.segment(node) for node in [*call.args, *call.keywords])


class _Source:
    """A node's text as written. Like `ast.get_source_segment`, which splits the whole source on every
    call and so takes minutes over the dataset's hundred-assert check functions."""

    def __init__(self, source: str):
        # Node columns are byte offsets into each line's UTF-8 encoding. Bytes split only at \n and \r,
        # as Python's parser does; str.splitlines would also split at characters such as \x85 in strings.
        self._lines = source.encode().splitlines(keepends=True)

    def segment(self, node: ast.AST) -> str:
        if node.end_lineno is None or node.end_col_offset is None:
            raise Dropped("its tests can't be read")
        first, last = node.lineno - 1, node.end_lineno - 1
        if first == last:
            return self._lines[first][node.col_offset : node.end_col_offset].decode()
        middle = self._lines[first + 1 : last]
        parts = [self._lines[first][node.col_offset :], *middle, self._lines[last][: node.end_col_offset]]
        return b"".join(parts).decode()


def load_fixes(path: Path = FIXES) -> dict[int, dict]:
    """The fixes file, by problem number. Raises ValueError if it names a comparison the runner lacks."""
    fixes = {int(number): fix for number, fix in json.loads(path.read_text(encoding="utf-8")).items()}
    for number, fix in fixes.items():
        if fix.get("compare", "equal") not in COMPARISONS:
            raise ValueError(f"the fix for #{number} names an unknown comparison {fix['compare']!r}")
    return fixes


@dataclass
class Fixed:
    problems: int = 0
    tests_dropped: int = 0
    skipped: list[str] = field(default_factory=list)


def apply_fixes(problems: dict[int, Problem], fixes: dict[int, dict]) -> Fixed:
    """Apply each fix to its problem in place. A fix whose slug differs from the dataset's is skipped whole;
    a dropped test the dataset lacks is skipped alone. A fix that would leave no tests is skipped too."""
    fixed = Fixed()
    for number, fix in sorted(fixes.items()):
        problem = problems.get(number)
        if problem is None:
            fixed.skipped.append(f"#{number} {fix['slug']}: not in the dataset")
            continue
        if problem.slug != fix["slug"]:
            fixed.skipped.append(f"#{number} {fix['slug']}: the dataset's #{number} is {problem.slug}")
            continue
        drop = {(t["args"], t["expected"]) for t in fix.get("drop", [])}
        tests = [t for t in problem.tests if (t.args, t.expected) not in drop]
        if not tests:
            fixed.skipped.append(f"#{number} {fix['slug']}: it would drop every test")
            continue
        present = {(t.args, t.expected) for t in problem.tests}
        fixed.skipped += [
            f"#{number} {fix['slug']}: no test {_short(args)} == {_short(expected)}"
            for args, expected in sorted(drop - present)
        ]
        if "compare" in fix:
            tests = [replace(t, compare=fix["compare"]) for t in tests]
        problems[number] = replace(problem, tests=tests)
        fixed.problems += 1
        fixed.tests_dropped += len(problem.tests) - len(tests)
    return fixed


def _short(text: str) -> str:
    return text if len(text) <= 60 else text[:57] + "..."


@dataclass
class Summary:
    kept: int
    dropped: Counter
    fixed: Fixed = field(default_factory=Fixed)

    def __str__(self) -> str:
        lines = [f"kept {self.kept:,} problems, dropped {sum(self.dropped.values()):,}"]
        lines += [f"  {count:,}: {reason}" for reason, count in self.dropped.most_common()]
        lines.append(f"fixed {self.fixed.problems:,} problems, dropped {self.fixed.tests_dropped:,} tests")
        if self.fixed.skipped:
            lines.append(f"skipped {len(self.fixed.skipped):,} fixes")
            lines += [f"  {skip}" for skip in self.fixed.skipped]
        return "\n".join(lines)


def import_files(data_dir: Path, files: list[Path], fixes: dict[int, dict] | None = None) -> Summary:
    """Convert every record in `files`, apply `fixes`, and write the kept problems to the data folder,
    ordered by number."""
    problems: dict[int, Problem] = {}
    dropped: Counter = Counter()
    for path in files:
        with path.open(encoding="utf-8") as lines:
            for line in lines:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    problem = convert(record)
                except json.JSONDecodeError:
                    dropped["not a problem record"] += 1
                    continue
                except Dropped as reason:
                    dropped[str(reason)] += 1
                    continue
                if problem.number in problems:
                    dropped["it was listed more than once"] += 1
                    continue
                problems[problem.number] = problem
    fixed = apply_fixes(problems, fixes or {})
    _write(data_dir / OUTPUT, [problems[n] for n in sorted(problems)])
    return Summary(len(problems), dropped, fixed)


def _write(path: Path, problems: list[Problem]) -> None:
    # Written beside the target and moved into place, so a failed import leaves the earlier one whole.
    partial = path.with_name(path.name + ".partial")
    with partial.open("w", encoding="utf-8") as out:
        for problem in problems:
            # ASCII only: descriptions and tests hold characters such as \x85 that some readers take as line breaks.
            out.write(json.dumps(asdict(problem)) + "\n")
    os.replace(partial, path)


# Each written line starts with its number, so a lookup parses only the problems it asks for.
_NUMBER_PREFIX = re.compile(r'^\{"number": (\d+),')


def read(data_dir: Path, numbers: set[int]) -> dict[int, dict]:
    """The imported problems with these numbers, as written. Empty if nothing has been imported."""
    path = data_dir / OUTPUT
    if not numbers or not path.is_file():
        return {}
    found: dict[int, dict] = {}
    with path.open(encoding="utf-8") as lines:
        for line in lines:
            match = _NUMBER_PREFIX.match(line)
            if not match or int(match[1]) not in numbers:
                continue
            try:
                found[int(match[1])] = json.loads(line)
            except json.JSONDecodeError:
                continue
    return found


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: python -m kedami_server.import_leetcode DATA_DIR FILE...")
    data_dir, files = Path(sys.argv[1]), [Path(f) for f in sys.argv[2:]]
    if not data_dir.is_dir():
        raise SystemExit(f"no data folder at {data_dir}")
    missing = [str(f) for f in files if not f.is_file()]
    if missing:
        raise SystemExit(f"no file at {', '.join(missing)}")
    print(import_files(data_dir, files, load_fixes()))


if __name__ == "__main__":
    main()
