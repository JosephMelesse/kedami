"""Prompts for each generation stage.

System prompts are fixed strings and the course material comes first in every request,
so the shared prefix is cached across a lesson's calls.
"""

import json
from typing import TYPE_CHECKING

from ..mathparse import CONSTANTS, FUNCTIONS
from .plan import SectionPlan
from .schemas import Extraction

if TYPE_CHECKING:
    from .hints import Target

MATH_SYNTAX = (
    "Math strings in `expression` fields use SymPy syntax: explicit `*` for multiplication, `**` for powers, "
    f"plain ASCII names (write `theta` for θ and `v0` for v₀), the functions {', '.join(sorted(FUNCTIONS))}, "
    f"and the constants {', '.join(sorted(CONSTANTS))}. No implicit multiplication such as `2x`."
)

MARKDOWN = (
    "Text fields are Markdown with LaTeX: `$...$` for inline math, and for display math put `$$` on its own line "
    "before and after the formula. Do not use HTML."
)


def materials(subject: str, problem_set: str, reference: str) -> list[dict]:
    """The course material, as the cached opening of every request for a lesson."""
    text = f"Subject: {subject}\n\n<problem_set>\n{problem_set}\n</problem_set>"
    if reference.strip():
        text += f"\n\n<reference_material>\n{reference}\n</reference_material>"
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def _with_feedback(text: str, feedback: str | None) -> dict:
    if feedback:
        text += (
            "\n\nYour previous reply to this request was rejected for this reason:\n"
            f"{feedback}\n\nReply again with the problem fixed."
        )
    return {"type": "text", "text": text}


# Stage 2: extraction

EXTRACT_SYSTEM = f"""You extract the structure of a homework assignment so it can be taught as one lesson.

From the problem set, capture every problem with:
- its source reference (for example "PS3 #4"; build one from the assignment name and problem number if none is written),
- its shared text and each part, copied verbatim, keeping every number, unit, and symbol,
- the concepts a student needs to solve it.

A problem with no lettered parts has one part whose label is the problem number.

Concepts are the ideas the lesson must teach. Draw them from the reference material when it is given, otherwise
from what the problems require. Keep them specific enough to teach in a few paragraphs, and list each once.

{MARKDOWN}"""


def extract_request(feedback: str | None = None) -> dict:
    return _with_feedback("Extract the problems and concepts from the problem set above.", feedback)


# Stage 3: plan

PLAN_SYSTEM = """You plan the order of a lesson that teaches the concepts a homework assignment needs.

Group the concepts into sections and order them so that each builds on the ones before it. Every concept that a
problem needs must be introduced in exactly one section. The server places each problem in the section where the
last concept it needs is introduced, so the order of concepts decides when each problem comes up. Prefer sections
that each end with a problem or two over one long section of theory followed by all the problems.

Give the lesson a short title and each section a title and a one-line goal."""


def plan_request(extraction: Extraction, feedback: str | None = None) -> dict:
    data = {
        "concepts": [c.model_dump() for c in extraction.concepts],
        "problems": [{"source_ref": p.source_ref, "concepts": p.concepts} for p in extraction.problems],
    }
    return _with_feedback(f"Plan the lesson for these concepts and problems:\n\n{json.dumps(data, indent=2)}", feedback)


# Stage 4: section content

SECTION_SYSTEM = f"""You write one section of an interactive lesson. Finishing the lesson means the student has done
their homework, so each section teaches exactly what its problems need, grounded in the course material.

Return the section's blocks in the order the student meets them. Each block is one object with a `type`; fill
the fields for that type and set every other field to null. Each answer is one object with a `kind`; fill the fields
for that kind and set the others to null (`correct` holds the one correct index for `choice`, or every correct index
for `multi_choice`).
- `explanation`: teaches a concept.
- `worked_example`: a similar problem solved in steps that are revealed one at a time.
- `plot`: functions of `x` over `x_domain`, with optional `parameters` the student can drag. Expressions may use only
  `x` and the parameter names. Give `y_domain` when the default would be misleading.
- `diagram`: a small static SVG with a `viewBox`. Color everything with `currentColor` (stroke or fill); no `style`
  elements, scripts, images, links, or `foreignObject`.
- `checkpoint`: a short practice question with its answer.
- `problem`: marks where one of this section's homework problems goes. Give its `source_ref` and an answer for every
  part, using the part labels exactly as given. Do not restate the problem; its text is inserted for you.

Rules:
- Include every one of this section's homework problems exactly once, after the teaching it needs, and no others.
- Worked examples and checkpoints must never use an actual homework problem; change the scenario and the numbers.
- Choose each answer kind to match the question. Keep a homework part's form: never turn a free-response part into
  multiple choice. Use `numeric` for a number (the student types only the number; give `unit` separately and a
  `rel_tolerance` that allows for rounding), `expression` for a formula, `choice` or `multi_choice` only when the
  question offers options, and `self_check` with a rubric for explanations, proofs, and sketches.
- Work every answer out carefully; students are graded against it.
- {MATH_SYNTAX}
- {MARKDOWN}"""


def section_request(section: SectionPlan, outline: list[SectionPlan], feedback: str | None = None) -> dict:
    data = {
        "lesson_outline": [{"title": s.title, "goal": s.goal} for s in outline],
        "this_section": {
            "title": section.title,
            "goal": section.goal,
            "concepts": [c.model_dump() for c in section.concepts],
            "homework_problems": [p.model_dump(exclude={"concepts"}) for p in section.problems],
        },
    }
    return _with_feedback(f"Write this section:\n\n{json.dumps(data, indent=2, ensure_ascii=False)}", feedback)


# Hints

HINTS_SYSTEM = f"""You write hints for questions in a lesson. Give up to three hints per question, ordered from gentle
to specific. A hint points the student toward the method; it never states the answer, a number equal to the answer,
or the correct option, and it never works the problem through to the end.

{MARKDOWN}"""


def hints_request(found: list["Target"]) -> dict:
    data = [{"target": t.key, "question": t.question, "answer": t.answer.model_dump()} for t in found]
    return {
        "type": "text",
        "text": f"Write hints for each of these questions, using the target IDs as given:\n\n"
        f"{json.dumps(data, indent=2, ensure_ascii=False)}",
    }


def replacement_request(failing: dict, by_key: dict, hints: dict) -> dict:
    data = [
        {
            "target": key,
            "index": index,
            "question": by_key[key].question,
            "answer": by_key[key].answer.model_dump(),
            "rejected_hint": hints[key][index],
            "reason": reason,
        }
        for (key, index), reason in failing.items()
    ]
    return {
        "type": "text",
        "text": "These hints were rejected. Write one replacement for each, at the same position and just as gentle "
        f"or specific, that does not give the answer away:\n\n{json.dumps(data, indent=2, ensure_ascii=False)}",
    }


# Hint judge

JUDGE_SYSTEM = """You check hints written for students. For each hint, decide whether it gives the answer away: it
states the answer or an equivalent value, names the correct option, or works the problem so far that nothing is left
for the student to do. A hint that only names the method, the relevant formula, or a first step does not give the
answer away. Rule on every hint you are given."""


def judge_request(to_judge: list[tuple[str, int, str]], by_key: dict) -> dict:
    data = [
        {
            "target": key,
            "index": index,
            "question": by_key[key].question,
            "answer": by_key[key].answer.model_dump(),
            "hint": hint,
        }
        for key, index, hint in to_judge
    ]
    return {"type": "text", "text": f"Rule on each of these hints:\n\n{json.dumps(data, indent=2, ensure_ascii=False)}"}


# Verification: an independent second solve

SOLVE_SYSTEM = f"""You solve questions from a course from scratch, working each one out carefully, so your answers can
be checked against a stored answer key. You are not shown that key.

For each question, give only the final answer in the form requested:
- number: `value`, in the unit given (or the natural unit of the question if none is given).
- expression: `expression`, using only the names listed.
- choice: `correct` with the one correct option's index (0-based).
- select_all: `correct` with the index of every correct option (0-based).
Set the other fields to null. A question that builds on an earlier part of the same problem uses your own earlier
results. {MATH_SYNTAX}"""


def solve_request(items: list[tuple[str, str, dict]]) -> dict:
    data = [{"target": key, "question": question, **form} for key, question, form in items]
    return {
        "type": "text",
        "text": f"Solve each of these questions, using the target IDs as given:\n\n{json.dumps(data, indent=2, ensure_ascii=False)}",
    }
