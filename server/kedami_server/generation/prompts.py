"""Prompts for each generation stage.

System prompts are fixed strings and the course material comes first in every request,
so the shared prefix is cached across a lesson's calls.
"""

import base64
import json
from typing import TYPE_CHECKING

from ..mathparse import CONSTANTS, FUNCTIONS
from .plan import SectionPlan
from .schemas import Extraction, Unit

if TYPE_CHECKING:
    from ..lesson import Answer, Part, ProblemBlock, Section
    from .hints import Target
    from .passages import Passage
    from .schemas import FinalAnswer

MATH_SYNTAX = (
    "Math strings in `expression` fields use SymPy syntax: explicit `*` for multiplication, `**` for powers, "
    f"plain ASCII names (write `theta` for θ and `v0` for v₀), the functions {', '.join(sorted(FUNCTIONS))}, "
    f"and the constants {', '.join(sorted(CONSTANTS))}. No implicit multiplication such as `2x`."
)

MARKDOWN = (
    "Text fields are Markdown with LaTeX: `$...$` for inline math, and for display math put `$$` on its own line "
    "before and after the formula. Do not use HTML."
)


def reference_passages(passages: list["Passage"]) -> str:
    """The reference as later stages see it: each passage marked with its number, under its file and page."""
    lines, page = [], None
    for passage in passages:
        if (passage.file, passage.page) != page:
            page = (passage.file, passage.page)
            lines.append(f"[{passage.file}, page {passage.page}]")
        lines.append(f"[p{passage.number}]\n{passage.text}")
    return "\n\n".join(lines)


def materials(subject: str, problem_set: str, reference: str) -> list[dict]:
    """The course material, as the cached opening of every request for a lesson. The reference is its passages, or
    for a lesson from before them, its normalized text. Only a lesson from before a reference was required has
    none; it can't be rerun, but its solutions and simulations are still written."""
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


FORMAT_SYSTEM = """You format text taken from the text layer of PDF pages of course material as Markdown, so that it
reads well. A text layer wraps lines where the page wrapped them, splits bullets across lines, breaks code apart, and
mixes in running headers and page numbers.

You may only add structure:
- Join wrapped lines, and put a blank line between paragraphs. A word split by a hyphen at a line end may be rejoined.
- Mark headings, lists, tables, and code. Use `-` for a bullet symbol, and put code in fences.

Every letter and digit you keep must stay exactly as written and in the same order. Do not reword, correct, summarize,
reorder, explain, or add anything, even to fix an obvious typo. Do not change capitalization. Do not turn symbols into
LaTeX: leave θ as θ and x2 as x2. A bullet written as a letter stays that letter.

You may drop only running headers, running footers, and page numbers. Consecutive pages show you what repeats. List
each line you drop in `dropped_lines`, as it is written on the page. Anything else stays, however short it is.

Return every page you are given. Do not use HTML."""


def format_request(file: str, pages: list[tuple[int, str]]) -> dict:
    data = [{"page": number, "text": text} for number, text in pages]
    return {
        "type": "text",
        "text": f"Format each page extracted from {file}:\n\n{json.dumps(data, indent=2, ensure_ascii=False)}",
    }


# Stage 2: extraction

EXTRACT_SYSTEM = f"""You extract the structure of a homework assignment and its reference material, so the two
can be taught as one lesson built from the material itself.

From the problem set, capture every problem with:
- its source reference (for example "PS3 #4"; build one from the assignment name and problem number if none is written),
- its shared text and each part, copied verbatim, keeping every number, unit, and symbol,
- for a part that asks the student to pick from listed options, including True/False, its options in `options`,
  as written and in order, left out of the part's text so they aren't shown twice,
- the IDs of the units a student needs to solve it.

A problem with no lettered parts has one part whose label is the problem number.

The reference is split into numbered passages, each marked like [p12]. Cut it into units and skipped ranges:
- A unit is a run of consecutive passages that teaches one idea, given by its first and last passage numbers, with
  an ID, a title, and a one-line summary. The lesson shows its passages word for word, so cut where the material
  moves to a new idea. A unit stays within one file.
- A skipped range is material that doesn't teach: course logistics, a table of contents, a bibliography, or a
  repeated slide. Give a reason for each. Material that no problem needs still teaches, so it goes in a unit.
- Every passage belongs to exactly one unit or skipped range, with no gaps and no overlaps. A [Figure: ...] passage
  only describes a figure, and may fall anywhere.

{MARKDOWN}"""


def extract_request(feedback: str | None = None) -> dict:
    return _with_feedback("Extract the problems from the problem set, and cut the reference into units.", feedback)


# Stage 3: plan

PLAN_SYSTEM = """You plan the order of a lesson that teaches a homework assignment from its reference material.

Group the units into sections and order them so that each builds on the ones before it. Every unit goes in exactly
one section. Within one file, keep the units in the order of the file; sections may move between files. The server
places each problem in the section of the last unit it needs, so the order of units decides when each problem comes
up. Prefer sections that each end with a problem or two over one long section of reading followed by all the
problems.

Give the lesson a short title and each section a title and a one-line goal.

A section may call for one interactive simulation: give a one-line brief in `simulation` only where dragging or
watching something move would teach what a static plot or diagram can't, such as how components change as a vector
rotates. Most sections should have none. A simulation is illustrative; it never shows a homework answer."""


def plan_request(extraction: Extraction, feedback: str | None = None) -> dict:
    data = {
        "units": [_unit(u) for u in extraction.units],
        "problems": [{"source_ref": p.source_ref, "units": p.units} for p in extraction.problems],
    }
    return _with_feedback(f"Plan the lesson for these units and problems:\n\n{json.dumps(data, indent=2)}", feedback)


def _unit(unit: "Unit") -> dict:
    span = f"p{unit.first}" if unit.first == unit.last else f"p{unit.first}-p{unit.last}"
    return {"id": unit.id, "title": unit.title, "summary": unit.summary, "passages": span}


# Stage 4: section content

SECTION_SYSTEM = f"""You build one section of an interactive lesson from its course material. Finishing the lesson
means the student has done their homework. The reference material is the lesson's main reading: you place it, and
write only what it doesn't supply.

Return the section's blocks in the order the student meets them. Each block is one object with a `type`; fill
the fields for that type and set every other field to null. Each answer is one object with a `kind`; fill the fields
for that kind and set the others to null (`correct` holds the one correct index for `choice`, or every correct index
for `multi_choice`).
- `source`: marks where one of this section's units goes. Give its `unit` ID. Its passages are inserted word for
  word, so never restate, quote, or summarize them.
- `explanation`: a short passage of your own that connects two units or fills a gap the problems need. It is
  labeled as added. Most units need none.
- `worked_example`: a similar problem solved in steps that are revealed one at a time.
- `plot`: functions of `x` over `x_domain`, with optional `parameters` the student can drag. Expressions may use only
  `x` and the parameter names. Give `y_domain` when the default would be misleading.
- `diagram`: a small static SVG with a `viewBox`. Color everything with `currentColor` (stroke or fill); no `style`
  elements or attributes, `transform`, scripts, images, links, or `foreignObject`. Set `font-family="monospace"` and
  a `font-size` on the root `svg`, and no other font family. Each character is 0.6 x its font-size wide, so 10
  characters at size 12 take 72 units; lay text out from that. Keep text inside the `viewBox`, clear of other text,
  and either wholly inside or wholly outside each rect and circle. Each `text` holds plain text, no `tspan`. To center
  text in a box, give it `text-anchor="middle"` at the box's center.
- `checkpoint`: a short practice question with its answer.
- `simulation`: marks where the section's interactive simulation goes, with a `caption` saying what to try. Include
  one only when `this_section` has a `simulation_brief`, and then exactly one; its code is written separately.
- `problem`: marks where one of this section's homework problems goes. Give its `source_ref` and an answer for every
  part, using the part labels exactly as given. Do not restate the problem; its text is inserted for you.

Rules:
- Place every one of this section's units exactly once, in the order given, and no others.
- Include every one of this section's homework problems exactly once, after the units it needs, and no others.
- A [Figure: ...] passage describes a figure in the reference that the lesson can't show. A `diagram` may draw it.
- Worked examples and checkpoints must never use an actual homework problem; change the scenario and the numbers.
- Choose each answer kind to match the question. Keep a homework part's form: never turn a free-response part into
  multiple choice. Use `numeric` for a number (the student types only the number; give `unit` separately and a
  `rel_tolerance` that allows for rounding), `expression` for a formula, `choice` or `multi_choice` only when the
  question offers options, and `self_check` with a rubric for explanations, proofs, and sketches. A homework part
  with `options` takes a `choice` or `multi_choice` answer with exactly those options, in that order.
- Work every answer out carefully; students are graded against it.
- {MATH_SYNTAX}
- {MARKDOWN}"""


def section_request(section: SectionPlan, outline: list[SectionPlan], feedback: str | None = None) -> dict:
    data = {
        "lesson_outline": [{"title": s.title, "goal": s.goal} for s in outline],
        "this_section": {
            "title": section.title,
            "goal": section.goal,
            "units": [_unit(u) for u in section.units],
            "homework_problems": [p.model_dump(exclude={"units"}) for p in section.problems],
            "simulation_brief": section.simulation,
        },
    }
    return _with_feedback(f"Write this section:\n\n{json.dumps(data, indent=2, ensure_ascii=False)}", feedback)


# Added to the section prompt for general lessons.
GENERAL_SECTION_RULES = """

For this lesson:
- Write code in the language of the course material, in fenced blocks tagged with that language.
- A homework part with a short factual answer, such as a term or a name, is a `self_check` whose rubric gives the
  answer. A True/False question is a `choice` with the options True and False, in that order."""


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


# Solutions on request

_FINAL = f"""`final` repeats the final answer in the form requested, so it can be compared with the answer key:
- number: `value`, in the unit given.
- expression: `expression`, using only the names listed. {MATH_SYNTAX}
- choice: `correct` with the one correct option's index (0-based).
- select_all: `correct` with the index of every correct option (0-based).
- shown: the answer is the working itself; set every field of `final` to null.
Set the fields a format doesn't use to null."""

_LINES = """Every line of math is LaTeX without $ delimiters, displayed on its own line. No sentences: a line is math,
with at most a short \\text{} label. Use the course material's notation and methods. If the part needs a result
from an earlier part of the same problem, state that result in one line instead of re-deriving it."""

MATH_STEPS_SYSTEM = f"""You write a short step-by-step solution to one part of a math homework problem, for a student
who asked to see it.

- `method`: the method in a few words, such as "Integration by parts" or "Completing the square". Plain text.
- `steps`: the working, one step per line, from the starting expression to the final answer. Each line follows from
  the one before. The last line puts the final answer in \\boxed{{}}.

{_LINES}

{_FINAL}"""

PHYSICS_STEPS_SYSTEM = f"""You write a short step-by-step solution to one part of a physics homework problem, for a
student who asked to see it.

- `given`: each known quantity from the problem, with its symbol, value, and unit, such as `m = 2.0\\,\\mathrm{{kg}}`.
  Include values the problem implies, such as `g = 9.8\\,\\mathrm{{m/s^2}}`.
- `required`: each quantity asked for, as its symbol, such as `v_f`.
- `steps`: the solution, one step per line. The first line is the formula used, in symbols. Then rearrange,
  substitute values with units, and compute. The last line puts the final answer, with its unit, in \\boxed{{}}.

{_LINES}

{_FINAL}"""


GENERAL_STEPS_SYSTEM = f"""You write a short step-by-step solution to one part of a homework problem from a course, for
a student who asked to see it.

- `steps`: a few short Markdown lines, each one fact or step of reasoning drawn from the course material. The last
  line is the final answer alone, such as `**80** bits` or `Carry flag (CF)`; it is shown under an Answer label.
  Short sentences are fine; put math in inline LaTeX with `$...$`. Use the course material's terms and notation.
  If the part needs a result from an earlier part of the same problem, state that result in one line instead of
  re-deriving it.

{_FINAL}"""

STEPS_SYSTEMS = {"math": MATH_STEPS_SYSTEM, "physics": PHYSICS_STEPS_SYSTEM, "general": GENERAL_STEPS_SYSTEM}


def steps_system(subject: str) -> str:
    return STEPS_SYSTEMS[subject]


def steps_request(
    block: "ProblemBlock", part: "Part", form: dict, feedback: str | None = None, disagreement: str | None = None
) -> dict:
    data = {
        "problem": block.source_ref,
        "shared_text": block.prompt,
        "parts": [{"label": p.label, "text": p.prompt} for p in block.parts],
        "solve_part": part.label,
        **form,
    }
    text = f"Write the solution to this part:\n\n{json.dumps(data, indent=2, ensure_ascii=False)}"
    if disagreement:
        text += f"\n\n{disagreement}"
    return _with_feedback(text, feedback)


def describe_answer(answer: "Answer") -> str:
    match answer.kind:
        case "numeric":
            return f"{answer.value:g} {answer.unit}" if answer.unit else f"{answer.value:g}"
        case "expression":
            return answer.expression
        case "choice":
            return f"option {answer.correct_index}: {answer.options[answer.correct_index]}"
        case "multi_choice":
            return "options " + ", ".join(f"{i}: {answer.options[i]}" for i in answer.correct_indexes)
    raise ValueError(f"{answer.kind} answers are not compared")


def disagreement(answer: "Answer", final: "FinalAnswer") -> str:
    return (
        f"Your last solution ended at {json.dumps(final.model_dump())}, but the answer key has {describe_answer(answer)}. "
        "Recheck the working. If the key is right, write the corrected solution; if you are sure it is wrong, keep yours."
    )


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
    teaching = [b.body for b in section.blocks if b.type in ("source", "explanation")]
    data = {"section": section.title, "goal": section.goal, "brief": brief, "caption": caption, "teaching": teaching}
    text = f"Write the simulation for this section:\n\n{json.dumps(data, indent=2, ensure_ascii=False)}"
    if failure:
        text += f"\n\nThe last version did not work: {failure}. Write a new, simpler one."
    return {"type": "text", "text": text}
