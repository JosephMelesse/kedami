"""Step-by-step solutions to problem parts, written when the student asks for one.

Lesson generation writes nothing for them, as with simulations. The call sees the course
material and the whole problem, never the stored answer, hints, or lesson content. Its
final answer is compared with the stored answer the way verification compares a second
solve; a disagreement is sent back once with the stored answer, and a second one leaves
the solution marked as not matching.
"""

from dataclasses import dataclass

from ..lesson import Part, ProblemBlock
from . import prompts
from .hints import Call
from .retry import retrying
from .schemas import GeneralSteps, MathSteps, PhysicsSteps
from .verify import agrees, answer_format

Steps = MathSteps | PhysicsSteps | GeneralSteps
OUTPUTS: dict[str, type[Steps]] = {"math": MathSteps, "physics": PhysicsSteps, "general": GeneralSteps}


@dataclass(frozen=True)
class WrittenSolution:
    steps: Steps
    # None when the part's answer isn't compared: a self check is the student's own judgment.
    matches: bool | None


def has_solution(subject: str, part: Part) -> bool:
    return subject in OUTPUTS and part.answer.kind != "external"


def write_solution(subject: str, block: ProblemBlock, part: Part, materials: list[dict], call: Call) -> WrittenSolution:
    compared = part.answer.kind != "self_check"
    form = answer_format(part.answer) if compared else {"format": "shown"}
    output = OUTPUTS[subject]

    def ask(disagreement: str | None) -> Steps:
        return retrying(
            f"Solution for {block.id}/{part.id}",
            lambda feedback: call(
                "solution",
                system=prompts.steps_system(subject),
                prompt=materials + [prompts.steps_request(block, part, form, feedback, disagreement)],
                output=output,
            ),
        )

    steps = ask(None)
    if not compared:
        return WrittenSolution(steps, None)
    if agrees(part.answer, steps.final):
        return WrittenSolution(steps, True)
    steps = ask(prompts.disagreement(part.answer, steps.final))
    return WrittenSolution(steps, agrees(part.answer, steps.final))
