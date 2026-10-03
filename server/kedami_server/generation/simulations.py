"""Simulation code, written when the student asks for a simulation and rewritten on request.

Lesson generation only places the block and keeps the plan's brief, so it doesn't wait on
code nobody may open. The code is stored apart from the lesson JSON, which is never edited
in place.
"""

from collections.abc import Callable

from ..lesson import Section, SimulationBlock
from . import prompts
from .retry import retrying
from .schemas import SimulationCode


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
