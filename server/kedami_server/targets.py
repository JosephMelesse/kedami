"""The things a student answers: problem parts and checkpoints."""

from dataclasses import dataclass

from .lesson import Answer, CheckpointBlock, Lesson, ProblemBlock


@dataclass(frozen=True)
class Target:
    block_id: str
    part_id: str | None
    answer: Answer
    hints: list[str]


def find_target(lesson: Lesson, block_id: str, part_id: str | None) -> Target | None:
    """A checkpoint is addressed with no part ID; a problem part needs one."""
    block = lesson.find_block(block_id)
    if isinstance(block, CheckpointBlock) and part_id is None:
        return Target(block.id, None, block.answer, block.hints)
    if isinstance(block, ProblemBlock):
        for part in block.parts:
            if part.id == part_id:
                return Target(block.id, part.id, part.answer, part.hints)
    return None
