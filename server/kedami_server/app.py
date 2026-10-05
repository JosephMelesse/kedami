"""HTTP API. Every route requires the session token."""

import hmac
import uuid
from dataclasses import asdict
from typing import Annotated, Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StringConstraints

from . import db, progress, simulation_state, solution_state
from .checking import InvalidResponse, check
from .config import Settings
from .model import ModelError, call_model
from .generation import pipeline
from .generation.retry import GenerationError
from .generation.simulations import new_code
from .generation.solutions import has_solution, write_solution
from .lesson import Lesson, PlotBlock, ProblemBlock, SimulationBlock, Subject
from .generation.sources import SourceError
from . import library
from .library import (
    LessonRow,
    add_material,
    create_generating,
    get_lesson_row,
    list_lessons,
    list_materials,
    problem_ids,
    set_force,
    start_run,
)
from .plot import sample_points
from .storage import delete_lesson_files, load_lesson
from .targets import Target, find_target
from .generation.leetcode import ProblemListError
from .uploads import Upload, check_problem_lists, check_uploads, save_uploads


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CheckRequest(Body):
    part_id: str | None = None
    response: Any


class HintRequest(Body):
    part_id: str | None = None
    count: StrictInt


class RerunRequest(Body):
    stage: Annotated[StrictInt, Field(ge=1, le=4)]
    # Force transcription per material, keyed by material ID.
    force: dict[str, StrictBool] = {}


class SimulationStatusRequest(Body):
    ok: StrictBool
    error: Annotated[str, Field(max_length=2000)] | None = None


class SolutionRequest(Body):
    part_id: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class FolderRequest(Body):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class RenameRequest(Body):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class MoveRequest(Body):
    # None moves the lesson to the home page.
    folder_id: StrictInt | None


class ReadingPositionRequest(Body):
    block_id: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class MarkDoneRequest(Body):
    part_id: str
    done: StrictBool


def create_app(settings: Settings, start_generation=pipeline.start, call=call_model) -> FastAPI:
    app = FastAPI(title="Kedami", docs_url=None, redoc_url=None, openapi_url=None)
    expected = f"Bearer {settings.token}".encode()

    @app.middleware("http")
    async def require_token(request: Request, call_next):
        supplied = request.headers.get("authorization", "").encode()
        if not hmac.compare_digest(supplied, expected):
            return JSONResponse({"detail": "missing or invalid session token"}, status_code=401)
        return await call_next(request)

    # Added last so it wraps the token check: preflight requests carry no token.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    def get_row(lesson_id: str) -> LessonRow:
        with db.connect(settings.data_dir) as conn:
            row = get_lesson_row(conn, lesson_id)
        if row is None:
            raise HTTPException(404, "lesson not found")
        return row

    def get_lesson(lesson_id: str) -> Lesson:
        lesson = load_lesson(settings.data_dir, lesson_id) if get_row(lesson_id).status == "ready" else None
        if lesson is None:
            raise HTTPException(404, "lesson not found")
        return lesson

    def get_target(lesson: Lesson, block_id: str, part_id: str | None) -> Target:
        target = find_target(lesson, block_id, part_id)
        if target is None:
            raise HTTPException(404, "no such part or checkpoint")
        return target

    def update(lesson_id: str, target: Target, transition) -> progress.Record:
        """Load the record, apply a transition, and save it in one transaction."""
        with db.connect(settings.data_dir) as conn:
            conn.execute("BEGIN IMMEDIATE")  # Take the write lock before reading, so updates can't interleave.
            record = progress.load(conn, lesson_id, target.block_id, target.part_id)
            try:
                return progress.save(conn, lesson_id, transition(record))
            except progress.Conflict as error:
                raise HTTPException(409, str(error)) from error

    def summary(row: LessonRow) -> dict:
        lesson = load_lesson(settings.data_dir, row.id) if row.status == "ready" else None
        done = 0
        if lesson:
            with db.connect(settings.data_dir) as conn:
                done = progress.problems_done(lesson, progress.load_all(conn, row.id))
        return {
            "id": row.id,
            "title": row.shown_title,
            "subject": row.subject,
            "status": row.status,
            "current_stage": row.current_stage,
            "error": row.error,
            "folder_id": row.folder_id,
            "created": row.created,
            "problems_total": len(problem_ids(lesson)) if lesson else 0,
            "problems_done": done,
        }

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/lessons")
    def lessons():
        with db.connect(settings.data_dir) as conn:
            rows = list_lessons(conn)
        return {"lessons": [summary(row) for row in rows]}

    @app.post("/lessons", status_code=201)
    def new_lesson(
        subject: Annotated[Subject, Form()],
        files: Annotated[list[UploadFile], File()],
        roles: Annotated[list[str], Form()],
        force: Annotated[list[bool], Form()],
        folder: Annotated[int | None, Form()] = None,
    ):
        if not len(files) == len(roles) == len(force):
            raise HTTPException(422, "Each file needs a role and a force transcription setting.")
        uploads = [Upload(f.filename or "file", f.file.read(), r, x) for f, r, x in zip(files, roles, force)]
        if folder is not None:
            with db.connect(settings.data_dir) as conn:
                if not library.folder_exists(conn, folder):
                    raise HTTPException(422, "That folder no longer exists.")
        try:
            check_uploads(uploads)
            if subject == "computer_science":
                check_problem_lists(uploads)
        except (SourceError, ProblemListError) as error:
            raise HTTPException(422, str(error)) from error

        lesson_id = str(uuid.uuid4())
        saved = save_uploads(pipeline.materials_dir(settings.data_dir, lesson_id), uploads)
        with db.connect(settings.data_dir) as conn:
            create_generating(conn, lesson_id, subject, schema_version=1, folder_id=folder)
            for file in saved:
                add_material(conn, lesson_id, file.filename, file.role, file.force_transcription)
        start_generation(settings.data_dir, lesson_id, subject, 1)
        return {"id": lesson_id}

    @app.post("/lessons/{lesson_id}/rerun")
    def rerun(lesson_id: str, body: RerunRequest):
        row = get_row(lesson_id)
        if row.status == "generating":
            raise HTTPException(409, "This lesson is already generating.")
        with db.connect(settings.data_dir) as conn:
            materials = {str(m.id): m for m in list_materials(conn, lesson_id)}
        unknown = sorted(body.force.keys() - materials.keys())
        if unknown:
            raise HTTPException(422, f"Unknown files: {', '.join(unknown)}")
        changed = {key: value for key, value in body.force.items() if materials[key].force_transcription != value}
        if changed and body.stage != 1:
            raise HTTPException(422, "Changing force transcription needs a rerun from stage 1.")
        if body.stage not in pipeline.available_stages(settings.data_dir, lesson_id, bool(materials)):
            raise HTTPException(409, f"This lesson can't be rerun from stage {body.stage}.")
        with db.connect(settings.data_dir) as conn:
            for key, value in changed.items():
                set_force(conn, int(key), value)
            start_run(conn, lesson_id)
        start_generation(settings.data_dir, lesson_id, row.subject, body.stage)
        return {"id": lesson_id}

    @app.get("/lessons/{lesson_id}")
    def lesson(lesson_id: str):
        row = get_row(lesson_id)
        body = get_lesson(lesson_id).model_dump(mode="json") if row.status == "ready" else None
        if body and row.custom_title:
            # A renamed lesson is served under its new name; the JSON on disk keeps the plan's.
            body["title"] = row.custom_title
        with db.connect(settings.data_dir) as conn:
            materials = list_materials(conn, lesson_id)
        return {
            "lesson": body,
            "status": row.status,
            "current_stage": row.current_stage,
            "error": row.error,
            "materials": [
                {"id": m.id, "filename": m.filename, "role": m.role, "force_transcription": m.force_transcription}
                for m in materials
            ],
            "rerun_stages": pipeline.available_stages(settings.data_dir, lesson_id, bool(materials)),
            "reading_block": row.reading_block,
        }

    @app.post("/lessons/{lesson_id}/reading-position")
    def reading_position(lesson_id: str, body: ReadingPositionRequest):
        if get_lesson(lesson_id).find_block(body.block_id) is None:
            raise HTTPException(404, "block not found")
        with db.connect(settings.data_dir) as conn:
            library.set_reading_block(conn, lesson_id, body.block_id)
        return {"block_id": body.block_id}

    @app.get("/lessons/{lesson_id}/blocks/{block_id}/points")
    def points(lesson_id: str, block_id: str):
        block = get_lesson(lesson_id).find_block(block_id)
        if not isinstance(block, PlotBlock):
            raise HTTPException(404, "plot block not found")
        return {"functions": sample_points(block)}

    @app.get("/lessons/{lesson_id}/progress")
    def lesson_progress(lesson_id: str):
        get_lesson(lesson_id)
        with db.connect(settings.data_dir) as conn:
            records = progress.load_all(conn, lesson_id)
        return {"progress": [asdict(record) for record in records]}

    @app.post("/lessons/{lesson_id}/blocks/{block_id}/check")
    def check_response(lesson_id: str, block_id: str, body: CheckRequest):
        target = get_target(get_lesson(lesson_id), block_id, body.part_id)
        try:
            correct = check(target.answer, body.response)
        except InvalidResponse as error:
            raise HTTPException(422, str(error)) from error
        record = update(lesson_id, target, lambda r: progress.after_check(r, correct, body.response))
        return {"correct": correct, "progress": asdict(record)}

    @app.post("/lessons/{lesson_id}/blocks/{block_id}/hint")
    def reveal_hint(lesson_id: str, block_id: str, body: HintRequest):
        target = get_target(get_lesson(lesson_id), block_id, body.part_id)
        record = update(lesson_id, target, lambda r: progress.after_hints(r, body.count, len(target.hints)))
        return {"progress": asdict(record)}

    @app.post("/lessons/{lesson_id}/blocks/{block_id}/mark-done")
    def mark_done(lesson_id: str, block_id: str, body: MarkDoneRequest):
        target = get_target(get_lesson(lesson_id), block_id, body.part_id)
        record = update(lesson_id, target, lambda r: progress.after_mark_done(r, body.done))
        return {"progress": asdict(record)}

    def get_simulation(lesson: Lesson, block_id: str) -> SimulationBlock:
        block = lesson.find_block(block_id)
        if not isinstance(block, SimulationBlock):
            raise HTTPException(404, "simulation block not found")
        return block

    @app.get("/lessons/{lesson_id}/blocks/{block_id}/simulation")
    def simulation(lesson_id: str, block_id: str):
        block = get_simulation(get_lesson(lesson_id), block_id)
        with db.connect(settings.data_dir) as conn:
            state = simulation_state.load(conn, lesson_id, block_id)
        return {"code": state.code or block.code, "flagged": state.flagged, "error": state.error}

    @app.post("/lessons/{lesson_id}/blocks/{block_id}/simulation-status")
    def simulation_status(lesson_id: str, block_id: str, body: SimulationStatusRequest):
        get_simulation(get_lesson(lesson_id), block_id)
        with db.connect(settings.data_dir) as conn:
            simulation_state.set_status(conn, lesson_id, block_id, body.ok, body.error)
        return {"flagged": not body.ok}

    @app.post("/lessons/{lesson_id}/blocks/{block_id}/regenerate")
    def regenerate(lesson_id: str, block_id: str):
        lesson = get_lesson(lesson_id)
        block = get_simulation(lesson, block_id)
        section = next(s for s in lesson.sections if any(b.id == block_id for b in s.blocks))
        with db.connect(settings.data_dir) as conn:
            state = simulation_state.load(conn, lesson_id, block_id)
        materials = pipeline.normalized_materials(settings.data_dir, lesson_id, lesson.subject)
        failure = state.error if state.flagged else None
        try:
            code = new_code(section, block, block.brief, materials, call, failure)
        except (ModelError, GenerationError) as error:
            raise HTTPException(502, str(error)) from error
        with db.connect(settings.data_dir) as conn:
            simulation_state.save_code(conn, lesson_id, block_id, code)
        return {"code": code, "flagged": False, "error": None}

    @app.post("/lessons/{lesson_id}/blocks/{block_id}/solution")
    def solution(lesson_id: str, block_id: str, body: SolutionRequest):
        lesson = get_lesson(lesson_id)
        block = lesson.find_block(block_id)
        part = next((p for p in block.parts if p.id == body.part_id), None) if isinstance(block, ProblemBlock) else None
        if part is None or not has_solution(lesson.subject, part):
            raise HTTPException(404, "This part has no solution.")
        with db.connect(settings.data_dir) as conn:
            stored = solution_state.load(conn, lesson_id, block_id, part.id)
        if stored:
            return stored
        materials = pipeline.normalized_materials(settings.data_dir, lesson_id, lesson.subject)
        try:
            written = write_solution(lesson.subject, block, part, materials, call)
        except (ModelError, GenerationError) as error:
            raise HTTPException(502, str(error)) from error
        solution = {"format": lesson.subject, **written.steps.model_dump()}
        with db.connect(settings.data_dir) as conn:
            solution_state.save(conn, lesson_id, block_id, part.id, solution, written.matches)
        return {"solution": solution, "matches": written.matches}

    @app.delete("/lessons/{lesson_id}")
    def delete_lesson(lesson_id: str):
        row = get_row(lesson_id)
        if row.status == "generating":
            raise HTTPException(409, "This lesson is still generating; delete it once it finishes.")
        with db.connect(settings.data_dir) as conn:
            library.delete_lesson(conn, lesson_id)
        delete_lesson_files(settings.data_dir, lesson_id)
        return {"deleted": lesson_id}

    @app.post("/lessons/{lesson_id}/rename")
    def rename_lesson(lesson_id: str, body: RenameRequest):
        get_row(lesson_id)
        with db.connect(settings.data_dir) as conn:
            library.rename_lesson(conn, lesson_id, body.title)
        return {"id": lesson_id, "title": body.title}

    @app.post("/lessons/{lesson_id}/move")
    def move_lesson(lesson_id: str, body: MoveRequest):
        get_row(lesson_id)
        with db.connect(settings.data_dir) as conn:
            if body.folder_id is not None and not library.folder_exists(conn, body.folder_id):
                raise HTTPException(404, "folder not found")
            library.move_lesson(conn, lesson_id, body.folder_id)
        return {"id": lesson_id, "folder_id": body.folder_id}

    @app.get("/folders")
    def folders():
        with db.connect(settings.data_dir) as conn:
            return {"folders": [asdict(f) for f in library.list_folders(conn)]}

    @app.post("/folders", status_code=201)
    def create_folder(body: FolderRequest):
        with db.connect(settings.data_dir) as conn:
            try:
                return asdict(library.create_folder(conn, body.name))
            except library.FolderExists as error:
                raise HTTPException(409, str(error)) from error

    @app.post("/folders/{folder_id}/rename")
    def rename_folder(folder_id: int, body: FolderRequest):
        with db.connect(settings.data_dir) as conn:
            if not library.folder_exists(conn, folder_id):
                raise HTTPException(404, "folder not found")
            try:
                library.rename_folder(conn, folder_id, body.name)
            except library.FolderExists as error:
                raise HTTPException(409, str(error)) from error
        return {"id": folder_id, "name": body.name}

    @app.delete("/folders/{folder_id}")
    def delete_folder(folder_id: int):
        with db.connect(settings.data_dir) as conn:
            if not library.folder_exists(conn, folder_id):
                raise HTTPException(404, "folder not found")
            library.delete_folder(conn, folder_id)
        return {"deleted": folder_id}

    return app
