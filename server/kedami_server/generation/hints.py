"""Hints for every problem part and checkpoint in a section.

Each hint passes two checks: the answer does not appear in it, checked here, and the plugin's
hint-checker subagent judges that it doesn't give the answer away. See architecture/agent-mode.md.
"""

import re
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


def with_hints(section: Section, hints: dict[str, list[str]]) -> Section:
    blocks = []
    for block in section.blocks:
        if isinstance(block, CheckpointBlock):
            block = block.model_copy(update={"hints": hints.get(block.id, [])})
        elif isinstance(block, ProblemBlock):
            parts = [p.model_copy(update={"hints": hints.get(f"{block.id}/{p.id}", [])}) for p in block.parts]
            block = block.model_copy(update={"parts": parts})
        blocks.append(block)
    return Section.model_validate(section.model_copy(update={"blocks": blocks}).model_dump())
