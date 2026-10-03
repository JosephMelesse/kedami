"""HTTP API. Every route requires the session token."""

import hmac

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import db
from .config import Settings
from .lesson import Lesson, PlotBlock
from .library import LessonRow, get_lesson_row, list_lessons, problem_ids
from .plot import sample_points
from .storage import load_lesson


def create_app(settings: Settings) -> FastAPI:
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

    def summary(row: LessonRow) -> dict:
        lesson = load_lesson(settings.data_dir, row.id) if row.status == "ready" else None
        return {
            "id": row.id,
            "title": row.title,
            "subject": row.subject,
            "status": row.status,
            "current_stage": row.current_stage,
            "created": row.created,
            "problems_total": len(problem_ids(lesson)) if lesson else 0,
            "problems_done": 0,
        }

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/lessons")
    def lessons():
        with db.connect(settings.data_dir) as conn:
            rows = list_lessons(conn)
        return {"lessons": [summary(row) for row in rows]}

    @app.get("/lessons/{lesson_id}")
    def lesson(lesson_id: str):
        row = get_row(lesson_id)
        body = get_lesson(lesson_id).model_dump(mode="json") if row.status == "ready" else None
        return {"lesson": body, "status": row.status, "current_stage": row.current_stage}

    @app.get("/lessons/{lesson_id}/blocks/{block_id}/points")
    def points(lesson_id: str, block_id: str):
        block = get_lesson(lesson_id).find_block(block_id)
        if not isinstance(block, PlotBlock):
            raise HTTPException(404, "plot block not found")
        return {"functions": sample_points(block)}

    return app
