"""HTTP API. Every route requires the session token."""

import hmac

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings
from .lesson import PlotBlock
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

    def get_lesson(lesson_id: str):
        lesson = load_lesson(settings.data_dir, lesson_id)
        if lesson is None:
            raise HTTPException(404, "lesson not found")
        return lesson

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/lessons/{lesson_id}")
    def lesson(lesson_id: str):
        # Generation status arrives with the pipeline (step 3); a lesson on disk is ready.
        return {"lesson": get_lesson(lesson_id).model_dump(mode="json"), "status": "ready", "current_stage": None}

    @app.get("/lessons/{lesson_id}/blocks/{block_id}/points")
    def points(lesson_id: str, block_id: str):
        block = get_lesson(lesson_id).find_block(block_id)
        if not isinstance(block, PlotBlock):
            raise HTTPException(404, "plot block not found")
        return {"functions": sample_points(block)}

    return app
