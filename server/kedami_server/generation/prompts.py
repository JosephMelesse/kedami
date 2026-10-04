"""Prompts for each generation stage.

System prompts are fixed strings and the course material comes first in every request,
so the shared prefix is cached across a lesson's calls.
"""

import base64
import json
from typing import TYPE_CHECKING

from ..mathparse import CONSTANTS, FUNCTIONS
from .plan import SectionPlan
from .schemas import Extraction

if TYPE_CHECKING:
    from ..lesson import Section
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


# Stage 1: ingestion

TEXT_CHECK_SYSTEM = """You check text extracted from the text layer of PDF pages of course material. For each page,
decide whether the text is clean: a student could read every problem and formula from it alone. It is not clean if
math is garbled or flattened (exponents, subscripts, fractions, roots, or symbols lost or run together, such as
"x2" for x squared), characters are replaced by boxes or wrong symbols, words are split or merged, or text is out of
order. When unsure, say it is not clean. Rule on every page you are given."""


def text_check_request(file: str, pages: list[tuple[int, str]]) -> dict:
    data = [{"page": number, "text": text} for number, text in pages]
    return {
        "type": "text",
        "text": f"Rule on each page extracted from {file}:\n\n{json.dumps(data, indent=2, ensure_ascii=False)}",
    }


TRANSCRIBE_SYSTEM = f"""You transcribe one page of course material from an image into Markdown with LaTeX.

Copy the page exactly: every problem number, part label, word, number, unit, and symbol, in reading order. Do not
solve, summarize, correct, or comment. Describe a figure in one line as [Figure: ...] with any labels and values it
shows. If the page is blank, return an empty string.

{MARKDOWN}"""


def transcribe_request(file: str, page: int, png: bytes) -> list[dict]:
    return [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(png).decode()}},
        {"type": "text", "text": f"Transcribe page {page} of {file}."},
    ]


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


CS_EXTRACT_SYSTEM = f"""You map the problems of a data structures and algorithms assignment to the concepts a lesson
must teach. The problems are LeetCode problems, given by number and title.

For each listed problem, give its number and the IDs of the concepts a student needs to solve it, such as hash maps,
two pointers, or binary search on the answer. Draw the concepts from the reference material when it is given,
otherwise from what the problems require. Keep each concept specific enough to teach in a few paragraphs, list each
once, and cover every listed problem exactly once using the numbers given.

{MARKDOWN}"""


def cs_extract_request(problems: list, feedback: str | None = None) -> dict:
    data = [{"number": p.number, "title": p.title} for p in problems]
    return _with_feedback(
        f"Map these LeetCode problems to the concepts they need:\n\n{json.dumps(data, indent=2, ensure_ascii=False)}",
        feedback,
    )


# Stage 3: plan

PLAN_SYSTEM = """You plan the order of a lesson that teaches the concepts a homework assignment needs.

Group the concepts into sections and order them so that each builds on the ones before it. Every concept that a
problem needs must be introduced in exactly one section. The server places each problem in the section where the
last concept it needs is introduced, so the order of concepts decides when each problem comes up. Prefer sections
that each end with a problem or two over one long section of theory followed by all the problems.

Give the lesson a short title and each section a title and a one-line goal.

A section may call for one interactive simulation: give a one-line brief in `simulation` only where dragging or
watching something move would teach what a static plot or diagram can't, such as how components change as a vector
rotates. Most sections should have none. A simulation is illustrative; it never shows a homework answer."""


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
- `simulation`: marks where the section's interactive simulation goes, with a `caption` saying what to try. Include
  one only when `this_section` has a `simulation_brief`, and then exactly one; its code is written separately.
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
            "simulation_brief": section.simulation,
        },
    }
    return _with_feedback(f"Write this section:\n\n{json.dumps(data, indent=2, ensure_ascii=False)}", feedback)


# Added to the section prompt for computer science lessons.
CS_SECTION_RULES = """

For this computer science lesson:
- The homework problems are LeetCode problems the student solves on LeetCode. Place each like any homework problem,
  with `parts` as an empty list. Never solve, outline, or give code for an assigned LeetCode problem anywhere in the
  section, including worked examples.
- Write all code in Python, in fenced ```python blocks, short and runnable.
- Use checkpoints as comprehension checks: `choice` or `multi_choice` for time and space complexity and for which
  approach fits, `numeric` for what a snippet prints or how many times a loop runs, and `self_check` with a rubric
  for explaining why an approach works."""


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


# Simulations

TOKEN_NAMES = ["bg", "surface", "surfaceRaised", "border", "text", "textMuted", "accent", "correct", "retry", "inProgress"]

SIMULATION_SYSTEM = f"""You write a small interactive simulation for one section of a lesson, as the body of this
JavaScript function:

    function simulation(root, canvas, tokens, ready) {{ /* your code */ }}

- `root` is an empty <div> about 640 px wide to build in. `canvas` is a <canvas> already inside it, sized to fill
  the width and 320 px tall, with `canvas.getContext("2d")` scaled for the screen.
- Add any controls (sliders, buttons, labels) to `root` with plain DOM calls.
- `tokens` holds the app's colors as CSS color strings: {", ".join(TOKEN_NAMES)}, plus `font`. Use them for every
  color, including controls: `tokens.text` for text and lines, `tokens.textMuted` for secondary marks and axes,
  `tokens.accent` only for the one thing the student moves, `tokens.border` for grid lines. The page background is
  `tokens.surface`.
- Call `ready()` once the simulation is drawn and working, within a second.
- Use requestAnimationFrame for animation. No network, imports, libraries, storage, alert, or HTML strings.
- Keep it short and focused on the brief. Label what is shown, with units. It is illustrative: never show the answer
  to a homework problem.

Return only the function body."""


def simulation_request(section: "Section", caption: str, brief: str | None, failure: str | None = None) -> dict:
    teaching = [b.body for b in section.blocks if b.type == "explanation"]
    data = {"section": section.title, "goal": section.goal, "brief": brief, "caption": caption, "teaching": teaching}
    text = f"Write the simulation for this section:\n\n{json.dumps(data, indent=2, ensure_ascii=False)}"
    if failure:
        text += f"\n\nThe last version did not work: {failure}. Write a new, simpler one."
    return {"type": "text", "text": text}
