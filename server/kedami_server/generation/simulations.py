"""Simulation code: written after a section exists, and rewritten on request.

Regenerated code is stored apart from the lesson JSON, which is never edited in place.
"""

from collections.abc import Callable

from ..lesson import Section, SimulationBlock
from . import prompts
from .retry import retrying
from .schemas import SimulationCode


def write_code(section: Section, brief: str | None, materials: list[dict], call: Callable) -> Section:
    """Fill in the code of each simulation block in the section."""
    blocks = []
    for block in section.blocks:
        if isinstance(block, SimulationBlock):
            block = block.model_copy(update={"code": new_code(section, block, brief, materials, call)})
        blocks.append(block)
    return Section.model_validate(section.model_copy(update={"blocks": blocks}).model_dump())


def new_code(
    section: Section,
    block: SimulationBlock,
    brief: str | None,
    materials: list[dict],
    call: Callable,
    failure: str | None = None,
) -> str:
    reply = retrying(
        f"Simulation for {block.id}",
        lambda feedback: call(
            "generate",
            system=prompts.SIMULATION_SYSTEM,
            prompt=materials + [prompts.simulation_request(section, block.caption, brief, feedback or failure)],
            output=SimulationCode,
        ),
    )
    return reply.code
