"""The /agent/ routes, called only by the MCP server. See architecture/agent-mode.md, Agent routes.

The token check in app.py covers these like every other route.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, TypeVar

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints

from ..generation.schemas import Plan, ProblemsAndConcepts, SectionDraft, Solutions
from . import draft, requests

T = TypeVar("T")

Text = Annotated[str, StringConstraints(max_length=200_000)]
Name = Annotated[str, StringConstraints(min_length=1, max_length=255)]


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FilePages(Body):
    file: Name
    pages: Annotated[list[Text], Field(max_length=1000)]


class PagesRequest(Body):
    files: Annotated[list[FilePages], Field(min_length=1)]


class TargetHints(Body):
    target: Name
    hints: list[Annotated[str, StringConstraints(max_length=2000)]]


class HintsRequest(Body):
    items: list[TargetHints]


class FailRequest(Body):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class SolutionSave(Body):
    part_id: Name
    # The subject's steps: MathSteps, PhysicsSteps, or GeneralSteps, checked against the lesson's subject.
    steps: dict
    # True when this answers the disagreement the last save returned.
    after_disagreement: StrictBool = False


class SimulationSave(Body):
    code: str


def _call(action: Callable[[], T]) -> T:
    try:
        return action()
    except draft.NotFound as error:
        raise HTTPException(404, str(error)) from error
    except draft.OutOfOrder as error:
        raise HTTPException(409, str(error)) from error
    except draft.Rejected as error:
        raise HTTPException(422, str(error)) from error


def agent_router(data_dir: Path) -> APIRouter:
    router = APIRouter(prefix="/agent")
    base = "/lessons/{lesson_id}"

    @router.get("/lessons")
    def waiting():
        return {"lessons": draft.waiting(data_dir)}

    @router.post(base + "/start")
    def start(lesson_id: str):
        return _call(lambda: draft.start(data_dir, lesson_id))

    @router.post(base + "/pages")
    def pages(lesson_id: str, body: PagesRequest):
        files = [(f.file, f.pages) for f in body.files]
        return _call(lambda: draft.save_pages(data_dir, lesson_id, files))

    @router.post(base + "/extraction")
    def extraction(lesson_id: str, body: ProblemsAndConcepts):
        return _call(lambda: draft.save_extraction(data_dir, lesson_id, body))

    @router.post(base + "/plan")
    def plan(lesson_id: str, body: Plan):
        return _call(lambda: draft.save_plan(data_dir, lesson_id, body))

    @router.post(base + "/sections/{number}")
    def section(lesson_id: str, number: int, body: SectionDraft):
        return _call(lambda: draft.save_section(data_dir, lesson_id, number, body))

    @router.post(base + "/sections/{number}/hints")
    def hints(lesson_id: str, number: int, body: HintsRequest):
        items = [(i.target, i.hints) for i in body.items]
        return _call(lambda: draft.save_hints(data_dir, lesson_id, number, items))

    @router.get(base + "/sections/{number}/questions")
    def questions(lesson_id: str, number: int):
        return _call(lambda: draft.questions(data_dir, lesson_id, number))

    @router.post(base + "/sections/{number}/verification")
    def verification(lesson_id: str, number: int, body: Solutions):
        return _call(lambda: draft.save_verification(data_dir, lesson_id, number, body))

    @router.post(base + "/finish")
    def finish(lesson_id: str):
        return _call(lambda: draft.finish(data_dir, lesson_id))

    @router.post(base + "/fail")
    def fail(lesson_id: str, body: FailRequest):
        return _call(lambda: draft.fail(data_dir, lesson_id, body.reason))

    @router.get(base + "/blocks/{block_id}/solution-request")
    def solution_request(lesson_id: str, block_id: str, part_id: str):
        return _call(lambda: requests.solution_request(data_dir, lesson_id, block_id, part_id))

    @router.post(base + "/blocks/{block_id}/solution")
    def solution(lesson_id: str, block_id: str, body: SolutionSave):
        return _call(
            lambda: requests.save_solution(
                data_dir, lesson_id, block_id, body.part_id, body.steps, body.after_disagreement
            )
        )

    @router.get(base + "/blocks/{block_id}/simulation-request")
    def simulation_request(lesson_id: str, block_id: str):
        return _call(lambda: requests.simulation_request(data_dir, lesson_id, block_id))

    @router.post(base + "/blocks/{block_id}/simulation")
    def simulation(lesson_id: str, block_id: str, body: SimulationSave):
        return _call(lambda: requests.save_simulation(data_dir, lesson_id, block_id, body.code))

    return router
