"""HTTP API. Every route requires the session token."""

import hmac
import uuid
from dataclasses import asdict
from typing import Annotated, Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from . import db, progress
from .checking import InvalidResponse, check
from .config import Settings
from .generation import pipeline
from .lesson import Lesson, PlotBlock
from .library import LessonRow, add_material, create_generating, get_lesson_row, list_lessons, problem_ids
from .plot import sample_points
from .storage import load_lesson
from .targets import Target, find_target


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CheckRequest(Body):
    part_id: str | None = None
    response: Any


class HintRequest(Body):
    part_id: str | None = None
    count: StrictInt


MAX_PASTE = 200_000


class NewLessonRequest(Body):
    """Step 3 takes pasted text; file upload replaces it in step 5."""

    subject: Literal["math", "physics"]
    problem_set: Annotated[str, Field(min_length=1, max_length=MAX_PASTE, pattern=r"\S")]
    reference: Annotated[str, Field(max_length=MAX_PASTE)] = ""


class MarkDoneRequest(Body):
    part_id: str
    done: StrictBool


def create_app(settings: Settings, start_generation=pipeline.start) -> FastAPI:
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
        allow_methods=["GET", "POST"],
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
            "title": row.title,
            "subject": row.subject,
            "status": row.status,
            "current_stage": row.current_stage,
            "error": row.error,
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
    def new_lesson(body: NewLessonRequest):
        lesson_id = str(uuid.uuid4())
        source = pipeline.materials_dir(settings.data_dir, lesson_id)
        source.mkdir(parents=True)
        (source / pipeline.PROBLEM_SET_FILE).write_text(body.problem_set)
        with db.connect(settings.data_dir) as conn:
            create_generating(conn, lesson_id, body.subject, schema_version=1)
            add_material(conn, lesson_id, pipeline.PROBLEM_SET_FILE, "problem_set")
            if body.reference.strip():
                (source / pipeline.REFERENCE_FILE).write_text(body.reference)
                add_material(conn, lesson_id, pipeline.REFERENCE_FILE, "reference")
        start_generation(settings.data_dir, lesson_id, body.subject)
        return {"id": lesson_id}

    @app.get("/lessons/{lesson_id}")
    def lesson(lesson_id: str):
        row = get_row(lesson_id)
        body = get_lesson(lesson_id).model_dump(mode="json") if row.status == "ready" else None
        return {"lesson": body, "status": row.status, "current_stage": row.current_stage, "error": row.error}

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

    return app
