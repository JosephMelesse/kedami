"""Code parts are served the import's current tests, so a new fix or import reaches every lesson without a
rerun. The lesson JSON keeps its own copy, served when the problem is no longer imported under the same slug.
See architecture/code-problems.md, In a lesson.
"""

from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from . import import_leetcode
from .lesson import CodeAnswer, CodeTest, Lesson, ProblemBlock

_TESTS = TypeAdapter(list[CodeTest])


def with_current_tests(data_dir: Path, lesson: Lesson) -> Lesson:
    """A copy of the lesson whose code parts have the import's current tests. The lesson itself is unchanged."""
    if not _code_answers(lesson):
        return lesson
    served = lesson.model_copy(deep=True)
    answers = _code_answers(served)
    records = import_leetcode.read(data_dir, {a.number for a in answers})
    for answer in answers:
        record = records.get(answer.number)
        if record is None or record.get("slug") != answer.slug:
            continue
        try:
            tests = _TESTS.validate_python(record.get("tests"))
        except ValidationError:
            continue
        if tests:
            answer.tests = tests
    return served


def _code_answers(lesson: Lesson) -> list[CodeAnswer]:
    return [
        part.answer
        for section in lesson.sections
        for block in section.blocks
        if isinstance(block, ProblemBlock)
        for part in block.parts
        if isinstance(part.answer, CodeAnswer)
    ]
