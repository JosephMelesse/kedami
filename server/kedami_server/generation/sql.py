"""SQL lessons' generation: settling the model's query answers and adding practice exercises from the bank.
See architecture/sql-lessons.md, In a lesson.

The model writes a reference query for a homework part or checkpoint against the course database. The server
names the database, decides whether row order matters, and refuses a reference that doesn't run or doesn't
return between 1 and 200 rows. Practice exercises come from the bank whole; the model never writes them.
"""

from ..lesson import Section
from ..practice import Exercise
from ..queries import QueryError, is_ordered, run
from .assemble import SectionError

MAX_REFERENCE_ROWS = 200


def settle_queries(section: Section, course: tuple[str, bytes] | None) -> Section:
    """Each model-written query answer, given the course database `(name, bytes)` and whether order matters.
    Raises SectionError with the reason, which is sent back to the model."""
    data = section.model_dump()
    for key, answer in _answers(data):
        if answer["kind"] != "query" or answer["exercise"] is not None:
            continue
        if course is None:
            raise SectionError(
                f"{key} has a query answer, but this lesson has no course database: a part that asks for a query is "
                "a self_check whose rubric says what a correct query does"
            )
        name, image = course
        try:
            result = run(image, answer["reference"])
        except QueryError as error:
            raise SectionError(f"the reference query for {key} doesn't run: {error}") from None
        if not result.rows:
            raise SectionError(f"the reference query for {key} returns no rows; write one whose answer isn't empty")
        if result.truncated or len(result.rows) > MAX_REFERENCE_ROWS:
            raise SectionError(f"the reference query for {key} returns over {MAX_REFERENCE_ROWS} rows")
        answer.update(database=f"course/{name}", ordered=is_ordered(answer["reference"]))
    return Section.model_validate(data)


def refuse_queries(section: Section) -> None:
    """Outside SQL lessons, a query answer is refused."""
    for key, answer in _answers(section.model_dump()):
        if answer["kind"] == "query":
            raise SectionError(f"{key} has a query answer, which only SQL lessons use")


def add_practice(section: Section, exercises: list[Exercise]) -> Section:
    """The section with its practice exercises appended as checkpoints with bank query answers."""
    data = section.model_dump()
    for number, exercise in enumerate(exercises, start=1):
        data["blocks"].append({
            "type": "checkpoint",
            "id": f"{section.id}-practice-{number}",
            "prompt": exercise.question,
            "answer": {
                "kind": "query",
                "database": f"bank/{exercise.database}",
                "reference": exercise.query,
                "ordered": is_ordered(exercise.query),
                "exercise": exercise.id,
            },
            "hints": [],
            "verified": False,
        })
    return Section.model_validate(data)


def _answers(section: dict):
    """Each answer in a dumped section, with a key naming where it is."""
    for block in section["blocks"]:
        if block["type"] == "checkpoint":
            yield block["id"], block["answer"]
        elif block["type"] == "problem":
            for part in block["parts"]:
                yield f"{block['source_ref']} part {part['label']}", part["answer"]
