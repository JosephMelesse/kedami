"""The lesson index: one row per lesson, whatever its generation status."""

import json
import sqlite3
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, fields
from datetime import UTC, datetime

from .lesson import Lesson, ProblemBlock

STATUSES = ("placeholder", "generating", "ready", "failed")


@dataclass(frozen=True)
class LessonRow:
    id: str
    title: str
    # Empty only on a placeholder.
    subject: str | None
    status: str
    current_stage: int | None
    schema_version: int
    revision: int
    created: str
    error: str | None = None
    folder_id: int | None = None
    # The student's name for the lesson. It outlasts reruns, which replace `title` with the plan's.
    custom_title: str | None = None
    # The block the student was last reading. A rerun keeps it, even if that block is gone.
    reading_block: str | None = None
    # The blocks that begin day 2 onward, as a JSON list. A rerun keeps them; see `day_starts`.
    day_starts: str | None = None
    # Whether the student is working through it, shown in the home page's Active card. A rerun keeps it.
    active: bool = False
    # As YYYY-MM-DD; see deadlines.py. A rerun or a move keeps it.
    due_date: str | None = None

    @property
    def shown_title(self) -> str:
        return self.custom_title or self.title


def add_ready_lesson(conn: sqlite3.Connection, lesson: Lesson) -> None:
    """Index a lesson that already exists on disk. Does nothing if it is already indexed."""
    conn.execute(
        "INSERT OR IGNORE INTO lessons (id, title, subject, status, current_stage, schema_version, created)"
        " VALUES (?, ?, ?, 'ready', NULL, ?, ?)",
        (lesson.id, lesson.title, lesson.subject, lesson.schema_version, _now()),
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()


def create_generating(
    conn: sqlite3.Connection,
    lesson_id: str,
    subject: str,
    schema_version: int,
    folder_id: int | None = None,
) -> None:
    """Index a lesson whose generation is starting. The title arrives with the plan."""
    conn.execute(
        "INSERT INTO lessons (id, title, subject, status, current_stage, schema_version, created, folder_id)"
        " VALUES (?, 'New lesson', ?, 'generating', NULL, ?, ?, ?)",
        (lesson_id, subject, schema_version, _now(), folder_id),
    )


def create_placeholder(
    conn: sqlite3.Connection,
    lesson_id: str,
    name: str,
    schema_version: int,
    folder_id: int | None = None,
    due_date: str | None = None,
) -> None:
    """Index a lesson planned but not generated. The name is the custom title, so generation never overwrites it."""
    conn.execute(
        "INSERT INTO lessons"
        " (id, title, custom_title, subject, status, current_stage, schema_version, created, folder_id, due_date)"
        " VALUES (?, 'New lesson', ?, NULL, 'placeholder', NULL, ?, ?, ?, ?)",
        (lesson_id, name, schema_version, _now(), folder_id, due_date),
    )


def fill_placeholder(
    conn: sqlite3.Connection, lesson_id: str, subject: str
) -> bool:
    """Start generating a placeholder under its own ID. False if it isn't a placeholder any more."""
    cursor = conn.execute(
        "UPDATE lessons SET subject = ?, status = 'generating', current_stage = NULL, error = NULL"
        " WHERE id = ? AND status = 'placeholder'",
        (subject, lesson_id),
    )
    return cursor.rowcount == 1


def set_stage(conn: sqlite3.Connection, lesson_id: str, stage: int) -> None:
    conn.execute("UPDATE lessons SET current_stage = ? WHERE id = ?", (stage, lesson_id))


def set_title(conn: sqlite3.Connection, lesson_id: str, title: str) -> None:
    conn.execute("UPDATE lessons SET title = ? WHERE id = ?", (title, lesson_id))


def start_run(conn: sqlite3.Connection, lesson_id: str) -> None:
    conn.execute(
        "UPDATE lessons SET status = 'generating', current_stage = NULL, error = NULL WHERE id = ?", (lesson_id,)
    )


def set_ready(conn: sqlite3.Connection, lesson_id: str, rerun: bool = False) -> None:
    """A rerun that replaces the lesson JSON increments its revision."""
    conn.execute(
        "UPDATE lessons SET status = 'ready', current_stage = NULL, error = NULL, revision = revision + ? WHERE id = ?",
        (1 if rerun else 0, lesson_id),
    )


def set_failed(conn: sqlite3.Connection, lesson_id: str, error: str) -> None:
    conn.execute("UPDATE lessons SET status = 'failed', error = ? WHERE id = ?", (error, lesson_id))


def set_rerun_failed(conn: sqlite3.Connection, lesson_id: str, error: str) -> None:
    """A failed rerun leaves the existing lesson in place and usable, with the reason."""
    conn.execute(
        "UPDATE lessons SET status = 'ready', current_stage = NULL, error = ? WHERE id = ?",
        (f"The last rerun failed. {error}", lesson_id),
    )


def fail_interrupted(conn: sqlite3.Connection, has_lesson: Callable[[str], bool]) -> None:
    """Generation runs inside the server process, so a restart ends any run in progress."""
    message = "Generation was interrupted when the app closed."
    for row in conn.execute("SELECT id FROM lessons WHERE status = 'generating'").fetchall():
        if has_lesson(row["id"]):
            set_rerun_failed(conn, row["id"], message)
        else:
            set_failed(conn, row["id"], message)


@dataclass(frozen=True)
class MaterialRow:
    id: int
    lesson_id: str
    filename: str
    role: str
    force_transcription: bool


def add_material(conn: sqlite3.Connection, lesson_id: str, filename: str, role: str, force: bool = False) -> None:
    conn.execute(
        "INSERT INTO materials (lesson_id, filename, role, force_transcription) VALUES (?, ?, ?, ?)",
        (lesson_id, filename, role, int(force)),
    )


def list_materials(conn: sqlite3.Connection, lesson_id: str) -> list[MaterialRow]:
    rows = conn.execute("SELECT * FROM materials WHERE lesson_id = ? ORDER BY id", (lesson_id,)).fetchall()
    return [MaterialRow(**{**dict(row), "force_transcription": bool(row["force_transcription"])}) for row in rows]


def set_force(conn: sqlite3.Connection, material_id: int, force: bool) -> None:
    conn.execute("UPDATE materials SET force_transcription = ? WHERE id = ?", (int(force), material_id))


def list_lessons(conn: sqlite3.Connection) -> list[LessonRow]:
    rows = conn.execute("SELECT * FROM lessons ORDER BY created, id").fetchall()
    return [_lesson_row(row) for row in rows]


def get_lesson_row(conn: sqlite3.Connection, lesson_id: str) -> LessonRow | None:
    row = conn.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
    return _lesson_row(row) if row else None


def _lesson_row(row: sqlite3.Row) -> LessonRow:
    """Older databases keep columns that are no longer used, so only the row's known fields are read."""
    known = {field.name for field in fields(LessonRow)}
    return LessonRow(**{key: row[key] for key in row.keys() if key in known})


def problem_ids(lesson: Lesson) -> list[str]:
    return [block.id for section in lesson.sections for block in section.blocks if isinstance(block, ProblemBlock)]


def delete_lesson(conn: sqlite3.Connection, lesson_id: str) -> None:
    """Remove the lesson's index row; its progress, materials, and simulation rows go with it."""
    conn.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))


# Folders nest to any depth. A lesson or folder with no parent is on the home page.

MAX_FOLDER_NAME = 80
MAX_FOLDER_NOTE = 20_000


class FolderExists(ValueError):
    pass


class FolderCycle(ValueError):
    pass


@dataclass(frozen=True)
class FolderRow:
    id: int
    name: str
    parent_id: int | None
    # Its lessons, counting those in its subfolders at any depth.
    lessons: int = 0
    own_lessons: int = 0
    subfolders: int = 0
    # The student's own text, which never goes to the model or into any lesson material.
    note: str = ""


@dataclass(frozen=True)
class RenamedFolder:
    id: int
    old: str
    new: str


@dataclass(frozen=True)
class DeletedFolder:
    parent_id: int | None
    renamed: list[RenamedFolder]


def create_folder(conn: sqlite3.Connection, name: str, parent_id: int | None = None) -> FolderRow:
    try:
        cursor = conn.execute(
            "INSERT INTO folders (name, parent_id, created) VALUES (?, ?, ?)", (name, parent_id, _now())
        )
    except sqlite3.IntegrityError as error:
        raise FolderExists(f"A folder named {name!r} already exists here.") from error
    return FolderRow(id=cursor.lastrowid, name=name, parent_id=parent_id)


def list_folders(conn: sqlite3.Connection) -> list[FolderRow]:
    rows = conn.execute(
        "SELECT f.id, f.name, f.parent_id, f.note, COUNT(l.id) AS own_lessons"
        " FROM folders f LEFT JOIN lessons l ON l.folder_id = f.id"
        " GROUP BY f.id ORDER BY f.name COLLATE NOCASE, f.id"
    ).fetchall()
    parents = {row["id"]: row["parent_id"] for row in rows}
    lessons: Counter[int] = Counter()
    subfolders: Counter[int] = Counter()
    for row in rows:
        if row["parent_id"] is not None:
            subfolders[row["parent_id"]] += 1
        folder = row["id"]
        while folder is not None:
            lessons[folder] += row["own_lessons"]
            folder = parents[folder]
    return [
        FolderRow(**row, lessons=lessons[row["id"]], subfolders=subfolders[row["id"]])
        for row in rows
    ]


def rename_folder(conn: sqlite3.Connection, folder_id: int, name: str) -> None:
    try:
        conn.execute("UPDATE folders SET name = ? WHERE id = ?", (name, folder_id))
    except sqlite3.IntegrityError as error:
        raise FolderExists(f"A folder named {name!r} already exists here.") from error


def set_folder_note(conn: sqlite3.Connection, folder_id: int, note: str) -> None:
    conn.execute("UPDATE folders SET note = ? WHERE id = ?", (note, folder_id))


def folder_exists(conn: sqlite3.Connection, folder_id: int) -> bool:
    return conn.execute("SELECT 1 FROM folders WHERE id = ?", (folder_id,)).fetchone() is not None


def _ancestors_and_self(conn: sqlite3.Connection, folder_id: int) -> set[int]:
    rows = conn.execute(
        "WITH RECURSIVE chain (id, parent_id) AS ("
        " SELECT id, parent_id FROM folders WHERE id = ?"
        " UNION SELECT f.id, f.parent_id FROM folders f JOIN chain c ON f.id = c.parent_id"
        ") SELECT id FROM chain",
        (folder_id,),
    ).fetchall()
    return {row["id"] for row in rows}


def move_folder(conn: sqlite3.Connection, folder_id: int, parent_id: int | None) -> None:
    """Move a folder and everything in it. Start a write transaction first, so the check and the move can't interleave."""
    if parent_id is not None and folder_id in _ancestors_and_self(conn, parent_id):
        raise FolderCycle("A folder can't move into itself or one of its own subfolders.")
    try:
        conn.execute("UPDATE folders SET parent_id = ? WHERE id = ?", (parent_id, folder_id))
    except sqlite3.IntegrityError as error:
        raise FolderExists("A folder with this name already exists there.") from error


def _name_taken(conn: sqlite3.Connection, name: str, parent_id: int | None) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM folders WHERE COALESCE(parent_id, 0) = COALESCE(?, 0) AND name = ? COLLATE NOCASE",
            (parent_id, name),
        ).fetchone()
        is not None
    )


def _free_name(conn: sqlite3.Connection, name: str, parent_id: int | None) -> str:
    """The name with the lowest free number, as in `Week 1 (2)`, cut to fit the limit."""
    number = 2
    while True:
        suffix = f" ({number})"
        numbered = name[: MAX_FOLDER_NAME - len(suffix)].rstrip() + suffix
        if not _name_taken(conn, numbered, parent_id):
            return numbered
        number += 1


def delete_folder(conn: sqlite3.Connection, folder_id: int) -> DeletedFolder:
    """Remove the folder; its lessons and subfolders move up to its parent, with numbers for any that clash.

    Start a write transaction first. The folder goes first, so its own name doesn't count as taken, and the
    reference from its subfolders is deferred until they have moved. Subfolders that can keep their names move
    before any is numbered, so a number never takes a name another subfolder already has.
    """
    parent_id = conn.execute("SELECT parent_id FROM folders WHERE id = ?", (folder_id,)).fetchone()["parent_id"]
    conn.execute("UPDATE lessons SET folder_id = ? WHERE folder_id = ?", (parent_id, folder_id))
    children = conn.execute(
        "SELECT id, name FROM folders WHERE parent_id = ? ORDER BY name COLLATE NOCASE, id", (folder_id,)
    ).fetchall()
    conn.execute("DELETE FROM folders WHERE id = ?", (folder_id,))

    clashing = []
    for child in children:
        if _name_taken(conn, child["name"], parent_id):
            clashing.append(child)
        else:
            conn.execute("UPDATE folders SET parent_id = ? WHERE id = ?", (parent_id, child["id"]))
    renamed = []
    for child in clashing:
        name = _free_name(conn, child["name"], parent_id)
        conn.execute("UPDATE folders SET parent_id = ?, name = ? WHERE id = ?", (parent_id, name, child["id"]))
        renamed.append(RenamedFolder(id=child["id"], old=child["name"], new=name))
    return DeletedFolder(parent_id=parent_id, renamed=renamed)


def rename_lesson(conn: sqlite3.Connection, lesson_id: str, title: str) -> None:
    conn.execute("UPDATE lessons SET custom_title = ? WHERE id = ?", (title, lesson_id))


def set_reading_block(conn: sqlite3.Connection, lesson_id: str, block_id: str) -> None:
    conn.execute("UPDATE lessons SET reading_block = ? WHERE id = ?", (block_id, lesson_id))


def set_day_starts(conn: sqlite3.Connection, lesson_id: str, block_ids: list[str]) -> None:
    conn.execute("UPDATE lessons SET day_starts = ? WHERE id = ?", (json.dumps(block_ids) if block_ids else None, lesson_id))


def day_starts(row: LessonRow, lesson: Lesson) -> list[str]:
    """The saved day starts still in the lesson, in lesson order, since a rerun can drop or move blocks."""
    saved = set(json.loads(row.day_starts)) if row.day_starts else set()
    block_ids = [block.id for section in lesson.sections for block in section.blocks]
    return [block_id for block_id in block_ids[1:] if block_id in saved]


def set_active(conn: sqlite3.Connection, lesson_id: str, active: bool) -> None:
    conn.execute("UPDATE lessons SET active = ? WHERE id = ?", (int(active), lesson_id))


def set_due_date(conn: sqlite3.Connection, lesson_id: str, due_date: str | None) -> None:
    conn.execute("UPDATE lessons SET due_date = ? WHERE id = ?", (due_date, lesson_id))


def move_lesson(conn: sqlite3.Connection, lesson_id: str, folder_id: int | None) -> None:
    conn.execute("UPDATE lessons SET folder_id = ? WHERE id = ?", (folder_id, lesson_id))
