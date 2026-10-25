"""Step-by-step solutions to problem parts: which parts have one, and the shape each subject's takes.

Claude Code writes a solution when the student asks for one; see agent/requests.py.
"""

from ..lesson import Part
from .schemas import GeneralSteps, MathSteps, PhysicsSteps

Steps = MathSteps | PhysicsSteps | GeneralSteps
OUTPUTS: dict[str, type[Steps]] = {"math": MathSteps, "physics": PhysicsSteps, "general": GeneralSteps}


def has_solution(subject: str, part: Part) -> bool:
    return subject in OUTPUTS and part.answer.kind not in ("external", "code", "query")
