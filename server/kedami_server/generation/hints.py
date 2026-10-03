"""Hints for every problem part and checkpoint in a section.

Each hint passes two checks: the answer does not appear in it, and a small model judges
that it doesn't give the answer away. A failing hint is regenerated once, then dropped.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from ..lesson import (
    MAX_HINTS,
    Answer,
    CheckpointBlock,
    ChoiceAnswer,
    ExpressionAnswer,
    MultiChoiceAnswer,
    NumericAnswer,
    ProblemBlock,
    Section,
)
from . import prompts
from .schemas import HintDraft, HintJudgements, HintReplacements

NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


@dataclass(frozen=True)
class Target:
    key: str
    question: str
    answer: Answer


def targets(section: Section) -> list[Target]:
    found = []
    for block in section.blocks:
        if isinstance(block, CheckpointBlock):
            found.append(Target(block.id, block.prompt, block.answer))
        elif isinstance(block, ProblemBlock):
            for part in block.parts:
                question = f"{block.prompt}\n\n{part.label} {part.prompt}".strip()
                found.append(Target(f"{block.id}/{part.id}", question, part.answer))
    return found


def leak_reason(answer: Answer, hint: str) -> str | None:
    """Why the hint contains the answer, or None. A cheap check before the model's judgment."""
    lowered = hint.lower()
    match answer:
        case NumericAnswer():
            # Small integers turn up in ordinary working ("t^2", "divide by 2"), so they are left to the judge.
            if answer.value == int(answer.value) and abs(answer.value) < 10:
                return None
            allowed = answer.rel_tolerance * (abs(answer.value) or 1)
            for text in NUMBER.findall(hint):
                if abs(float(text) - answer.value) <= allowed:
                    return f"it contains the answer {text}"
        case ExpressionAnswer():
            if _squash(answer.expression) in _squash(hint):
                return "it contains the answer expression"
        case ChoiceAnswer():
            if _option_in(answer.options[answer.correct_index], lowered):
                return "it names the correct option"
        case MultiChoiceAnswer():
            if all(_option_in(answer.options[i], lowered) for i in answer.correct_indexes):
                return "it names every correct option"
    return None


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text).replace("**", "^").lower()


def _option_in(option: str, lowered_hint: str) -> bool:
    plain = option.replace("$", "").strip().lower()
    return len(plain) >= 3 and plain in lowered_hint


Call = Callable[..., object]


def add_hints(section: Section, materials: list[dict], call: Call) -> Section:
    found = targets(section)
    if not found:
        return section
    by_key = {t.key: t for t in found}

    draft = call("generate", system=prompts.HINTS_SYSTEM, prompt=materials + [prompts.hints_request(found)], output=HintDraft)
    hints = {key: [] for key in by_key}
    for item in draft.items:
        if item.target in hints:
            hints[item.target] = list(item.hints[:MAX_HINTS])

    failing = _failing(hints, by_key, call)
    if failing:
        replacements = call(
            "generate",
            system=prompts.HINTS_SYSTEM,
            prompt=materials + [prompts.replacement_request(failing, by_key, hints)],
            output=HintReplacements,
        )
        replaced = {(r.target, r.index): r.hint for r in replacements.replacements if (r.target, r.index) in failing}
        for (key, index), hint in replaced.items():
            hints[key][index] = hint
        retry = {k: [h if (k, i) in replaced else None for i, h in enumerate(v)] for k, v in hints.items()}
        still_failing = _failing(retry, by_key, call)
        dropped = (failing.keys() - replaced.keys()) | still_failing.keys()
        hints = {k: [h for i, h in enumerate(v) if (k, i) not in dropped] for k, v in hints.items()}

    return _with_hints(section, hints)


def _failing(hints: dict[str, list[str | None]], by_key: dict[str, Target], call: Call) -> dict[tuple[str, int], str]:
    """Hints that fail either check, with the reason. None entries are skipped."""
    failing = {}
    to_judge = []
    for key, items in hints.items():
        for index, hint in enumerate(items):
            if hint is None:
                continue
            reason = leak_reason(by_key[key].answer, hint)
            if reason:
                failing[(key, index)] = reason
            else:
                to_judge.append((key, index, hint))
    if to_judge:
        judged = call(
            "small_check",
            system=prompts.JUDGE_SYSTEM,
            prompt=[prompts.judge_request(to_judge, by_key)],
            output=HintJudgements,
        )
        verdicts = {(r.target, r.index): r.gives_away for r in judged.results}
        for key, index, _ in to_judge:
            # A hint the judge didn't rule on takes the safer route and counts as failing.
            if verdicts.get((key, index), True):
                failing[(key, index)] = "it gives the answer away"
    return failing


def _with_hints(section: Section, hints: dict[str, list[str]]) -> Section:
    blocks = []
    for block in section.blocks:
        if isinstance(block, CheckpointBlock):
            block = block.model_copy(update={"hints": hints.get(block.id, [])})
        elif isinstance(block, ProblemBlock):
            parts = [p.model_copy(update={"hints": hints.get(f"{block.id}/{p.id}", [])}) for p in block.parts]
            block = block.model_copy(update={"parts": parts})
        blocks.append(block)
    return Section.model_validate(section.model_copy(update={"blocks": blocks}).model_dump())
