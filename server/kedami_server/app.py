"""HTTP API. Every route requires the session token."""

import hmac
import uuid
from dataclasses import asdict
from typing import Annotated, Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StringConstraints

from . import databases, db, progress, queries, simulation_state, solution_state, test_flags, usage
from .checking import InvalidResponse, check
from .config import Settings
from .model import ModelError, call_model
from .generation import pipeline
from .generation.retry import GenerationError
from .generation.simulations import new_code
from .generation.solutions import has_solution, write_solution
from .leetcode_search import entries as leetcode_entries
from .leetcode_search import search as search_leetcode
from .lesson import CodeAnswer, Domain, Lesson, PlotBlock, ProblemBlock, QueryAnswer, SimulationBlock, Subject
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


class ActiveRequest(Body):
    active: StrictBool


class ReadingPositionRequest(Body):
    block_id: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class DaysRequest(Body):
    # Day 1 starts at the first block, so 30 days have 29 starts.
    block_ids: Annotated[list[Annotated[str, StringConstraints(min_length=1, max_length=200)]], Field(max_length=29)]


class MarkDoneRequest(Body):
    part_id: str
    done: StrictBool


# Longest code a code part saves, in characters.
MAX_CODE = 100_000


class CodeRequest(Body):
    part_id: str
    code: Annotated[str, StringConstraints(max_length=MAX_CODE)]


class SubmitRequest(CodeRequest):
    # Whether every unflagged test passed, as the sandboxed runner reported. The server can't run the code.
    passed: StrictBool


class QueryRequest(Body):
    # Null for a checkpoint.
    part_id: str | None = None
    query: Annotated[str, StringConstraints(max_length=queries.MAX_QUERY_LENGTH)]


# Rows of a query's result sent back for showing.
SHOWN_ROWS = 100
SHOWN_TEXT = 1000


def shown(result: queries.Result) -> dict:
    """A query's result as the workspace shows it: at most SHOWN_ROWS rows, long text cut, blobs as hex."""

    def value(v):
        if isinstance(v, bytes):
            return f"x'{v[:SHOWN_TEXT // 2].hex()}'"
        if isinstance(v, str) and len(v) > SHOWN_TEXT:
            return v[: SHOWN_TEXT - 3] + "..."
        return v

    return {
        "columns": result.columns,
        "rows": [[value(v) for v in row] for row in result.rows[:SHOWN_ROWS]],
        "count": len(result.rows),
        "truncated": result.truncated,
    }


class FlaggedTest(Body):
    args: str
    expected: str


class FlagRequest(Body):
    part_id: str
    action: Literal["flag", "unflag", "clear"]
    # The test to flag or unflag; clear removes every flag on the part.
    test: FlaggedTest | None = None


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
            "domain": row.domain or ("dsa" if row.subject == "computer_science" else None),
            "status": row.status,
            "current_stage": row.current_stage,
            "error": row.error,
            "folder_id": row.folder_id,
            "created": row.created,
            "problems_total": len(problem_ids(lesson)) if lesson else 0,
            "problems_done": done,
            "active": bool(row.active),
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
        domain: Annotated[Domain | None, Form()] = None,
    ):
        if (subject == "computer_science") != (domain is not None):
            raise HTTPException(422, "A computer science lesson needs a domain, and only it has one.")
        if not len(files) == len(roles) == len(force):
            raise HTTPException(422, "Each file needs a role and a force transcription setting.")
        uploads = [Upload(f.filename or "file", f.file.read(), r, x) for f, r, x in zip(files, roles, force)]
        # A SQL lesson's course database is checked and kept apart from the material that is read.
        database_uploads = [u for u in uploads if u.role == "database"]
        if database_uploads and domain != "sql":
            raise HTTPException(422, "Only a SQL lesson takes a database.")
        if len(database_uploads) > 1:
            raise HTTPException(422, "A SQL lesson takes one database.")
        uploads = [u for u in uploads if u.role != "database"]
        if folder is not None:
            with db.connect(settings.data_dir) as conn:
                if not library.folder_exists(conn, folder):
                    raise HTTPException(422, "That folder no longer exists.")
        try:
            check_uploads(uploads)
            if subject == "computer_science" and domain == "dsa":
                check_problem_lists(uploads, settings.data_dir)
            course = [(u.name, databases.from_upload(u.name, u.data)) for u in database_uploads]
        except (SourceError, ProblemListError, databases.DatabaseFileError) as error:
            raise HTTPException(422, str(error)) from error

        lesson_id = str(uuid.uuid4())
        saved = save_uploads(pipeline.materials_dir(settings.data_dir, lesson_id), uploads)
        for name, image in course:
            databases.save_course(pipeline.materials_dir(settings.data_dir, lesson_id), name, image)
        with db.connect(settings.data_dir) as conn:
            create_generating(conn, lesson_id, subject, schema_version=1, folder_id=folder, domain=domain)
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
        loaded = get_lesson(lesson_id) if row.status == "ready" else None
        body = loaded.model_dump(mode="json") if loaded else None
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
            "day_starts": library.day_starts(row, loaded) if loaded else [],
        }

    @app.post("/lessons/{lesson_id}/reading-position")
    def reading_position(lesson_id: str, body: ReadingPositionRequest):
        if get_lesson(lesson_id).find_block(body.block_id) is None:
            raise HTTPException(404, "block not found")
        with db.connect(settings.data_dir) as conn:
            library.set_reading_block(conn, lesson_id, body.block_id)
        return {"block_id": body.block_id}

    @app.post("/lessons/{lesson_id}/days")
    def days(lesson_id: str, body: DaysRequest):
        block_ids = [block.id for section in get_lesson(lesson_id).sections for block in section.blocks]
        if any(block_id not in block_ids for block_id in body.block_ids):
            raise HTTPException(404, "block not found")
        positions = [block_ids.index(block_id) for block_id in body.block_ids]
        if positions and positions[0] == 0:
            raise HTTPException(422, "The first block already starts day 1.")
        if any(a >= b for a, b in zip(positions, positions[1:])):
            raise HTTPException(422, "Day starts must be in lesson order, with no repeats.")
        with db.connect(settings.data_dir) as conn:
            library.set_day_starts(conn, lesson_id, body.block_ids)
        return {"block_ids": body.block_ids}

    @app.get("/lessons/{lesson_id}/blocks/{block_id}/points")
    def points(lesson_id: str, block_id: str):
        block = get_lesson(lesson_id).find_block(block_id)
        if not isinstance(block, PlotBlock):
            raise HTTPException(404, "plot block not found")
        return {"functions": sample_points(block)}

    @app.get("/leetcode/search")
    def leetcode_search(q: Annotated[str, Query(max_length=200)] = ""):
        found = search_leetcode(settings.data_dir, q)
        # Whether anything is imported, so the picker can say so instead of finding nothing.
        imported = len(leetcode_entries(settings.data_dir)) > 0
        return {"problems": [asdict(entry) for entry in found], "imported": imported}

    @app.get("/lessons/{lesson_id}/progress")
    def lesson_progress(lesson_id: str):
        get_lesson(lesson_id)
        with db.connect(settings.data_dir) as conn:
            records = progress.load_all(conn, lesson_id)
            flags = test_flags.load_all(conn, lesson_id)
        return {"progress": [asdict(record) for record in records], "flags": flags}

    def query_database(lesson_id: str, answer: QueryAnswer) -> bytes:
        try:
            return databases.image_for(settings.data_dir, pipeline.materials_dir(settings.data_dir, lesson_id), answer.database)
        except databases.DatabaseMissing as error:
            raise HTTPException(409, str(error)) from error

    def query_target(lesson_id: str, block_id: str, part_id: str | None) -> tuple[Target, QueryAnswer, bytes]:
        target = get_target(get_lesson(lesson_id), block_id, part_id)
        if not isinstance(target.answer, QueryAnswer):
            raise HTTPException(422, "This part isn't a query.")
        return target, target.answer, query_database(lesson_id, target.answer)

    @app.get("/lessons/{lesson_id}/blocks/{block_id}/tables")
    def query_tables(lesson_id: str, block_id: str, part_id: str | None = None):
        _, _, image = query_target(lesson_id, block_id, part_id)
        return {"tables": databases.tables(image)}

    @app.post("/lessons/{lesson_id}/blocks/{block_id}/run-query")
    def run_query(lesson_id: str, block_id: str, body: QueryRequest):
        _, _, image = query_target(lesson_id, block_id, body.part_id)
        try:
            return shown(queries.run(image, body.query)) | {"error": None}
        except queries.QueryError as error:
            return {"columns": [], "rows": [], "count": 0, "truncated": False, "error": str(error)}

    def check_query(lesson_id: str, target: Target, answer: QueryAnswer, response) -> dict:
        if not isinstance(response, str):
            raise HTTPException(422, "Write a query.")
        try:
            reason, got = queries.check(query_database(lesson_id, answer), answer.reference, answer.ordered, response)
        except queries.QueryError as error:
            raise HTTPException(422, str(error)) from error
        except queries.BrokenReference as error:
            raise HTTPException(409, f"This exercise's reference query doesn't run: {error}") from error
        record = update(lesson_id, target, lambda r: progress.after_check(r, reason is None, response))
        return {"correct": reason is None, "progress": asdict(record), "reason": reason, "result": shown(got)}

    @app.post("/lessons/{lesson_id}/blocks/{block_id}/check")
    def check_response(lesson_id: str, block_id: str, body: CheckRequest):
        target = get_target(get_lesson(lesson_id), block_id, body.part_id)
        if isinstance(target.answer, QueryAnswer):
            return check_query(lesson_id, target, target.answer, body.response)
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

    def get_code_target(lesson_id: str, block_id: str, part_id: str) -> tuple[Target, CodeAnswer]:
        target = get_target(get_lesson(lesson_id), block_id, part_id)
        if not isinstance(target.answer, CodeAnswer):
            raise HTTPException(422, "This part isn't a code problem.")
        return target, target.answer

    @app.post("/lessons/{lesson_id}/blocks/{block_id}/code")
    def save_code(lesson_id: str, block_id: str, body: CodeRequest):
        target, answer = get_code_target(lesson_id, block_id, body.part_id)
        record = update(lesson_id, target, lambda r: progress.after_code_saved(r, body.code, answer.starter_code))
        return {"progress": asdict(record)}

    @app.post("/lessons/{lesson_id}/blocks/{block_id}/submit")
    def submit_code(lesson_id: str, block_id: str, body: SubmitRequest):
        target, _ = get_code_target(lesson_id, block_id, body.part_id)
        record = update(lesson_id, target, lambda r: progress.after_check(r, body.passed, body.code))
        return {"progress": asdict(record)}

    @app.post("/lessons/{lesson_id}/blocks/{block_id}/flags")
    def flag_test(lesson_id: str, block_id: str, body: FlagRequest):
        _, answer = get_code_target(lesson_id, block_id, body.part_id)
        with db.connect(settings.data_dir) as conn:
            if body.action == "clear":
                test_flags.clear(conn, lesson_id, block_id, body.part_id)
            else:
                test = body.test
                if test is None or not any(t.args == test.args and t.expected == test.expected for t in answer.tests):
                    raise HTTPException(422, "No such test in this problem.")
                flagged = body.action == "flag"
                test_flags.set_flag(conn, lesson_id, block_id, body.part_id, test.args, test.expected, flagged)
            flags = test_flags.load_all(conn, lesson_id)
        return {"flags": [f for f in flags if (f["block_id"], f["part_id"]) == (block_id, body.part_id)]}

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
            with usage.recording(settings.data_dir, lesson_id, "simulation"):
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
            with usage.recording(settings.data_dir, lesson_id, "solution"):
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

    @app.post("/lessons/{lesson_id}/active")
    def set_active(lesson_id: str, body: ActiveRequest):
        get_lesson(lesson_id)
        with db.connect(settings.data_dir) as conn:
            library.set_active(conn, lesson_id, body.active)
        return {"id": lesson_id, "active": body.active}

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
