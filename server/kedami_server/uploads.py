"""Checking and saving the files a new lesson is made from."""

from dataclasses import dataclass
from pathlib import Path

from . import databases
from .generation.leetcode import find_in_dataset, parse_problem_list
from .generation.recommended import parse_recommended
from .generation.sources import MAX_PAGES, SourceError, kind_of, page_count, safe_filename
from .practice import load_bank
from .sql_chapters import BOOK_DIR, book_reference

ROLES = ("problem_set", "reference")
MAX_FILES = 20


@dataclass(frozen=True)
class Upload:
    name: str
    data: bytes
    role: str
    force_transcription: bool


@dataclass(frozen=True)
class SavedFile:
    filename: str
    role: str
    force_transcription: bool


def check_uploads(uploads: list[Upload]) -> None:
    """Raise SourceError, with a message fit to show the student, if the set can't make a lesson."""
    if not uploads:
        raise SourceError("Add at least one file.")
    if len(uploads) > MAX_FILES:
        raise SourceError(f"Upload at most {MAX_FILES} files.")
    for upload in uploads:
        if upload.role not in ROLES:
            raise SourceError(f"{upload.name}: role must be problem set or reference.")
    if not any(u.role == "problem_set" for u in uploads):
        raise SourceError("Tag at least one file as a problem set.")
    pages = sum(page_count(u.name, u.data) for u in uploads)
    if pages > MAX_PAGES:
        raise SourceError(f"These files have {pages} pages; a lesson can use at most {MAX_PAGES}.")


def check_problem_lists(uploads: list[Upload], data_dir: Path) -> None:
    """Read a computer science lesson's problem lists now when they are text, so a bad line, or a title that
    names a different problem than its number, fails at once. Lists in PDFs or images are read after stage 1
    transcribes them."""
    for upload in uploads:
        if upload.role == "problem_set" and kind_of(upload.name) == "text":
            find_in_dataset(data_dir, parse_problem_list(upload.data.decode("utf-8")))


def check_recommended(uploads: list[Upload], data_dir: Path) -> None:
    """A SQL chapter lesson takes one text file, its recommended problems, which must all be ones the server has.
    Raises SourceError or ProblemListError with a message fit to show the student."""
    if len(uploads) != 1 or uploads[0].role != "problem_set" or kind_of(uploads[0].name) != "text":
        raise SourceError("A chapter lesson takes only its recommended problems, as one text file.")
    try:
        text = uploads[0].data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SourceError(f"{uploads[0].name} is not UTF-8 text.") from error
    parse_recommended(text, load_bank(data_dir))


def chapter_material(chapter: int) -> tuple[Upload, tuple[str, bytes]]:
    """What a chapter lesson gets beside its problems: the chapter's pages of the book as one reference file, and
    the book's example database as its course database, as (file name, bytes)."""
    reference = Upload(f"wikibooks-{chapter}.md", book_reference(chapter).encode("utf-8"), "reference", False)
    people = databases.from_upload("people.sql", (BOOK_DIR / "people.sql").read_bytes())
    return reference, ("people.sql", people)


def save_uploads(folder: Path, uploads: list[Upload]) -> list[SavedFile]:
    """Write checked uploads to the materials folder under safe, unique names."""
    folder.mkdir(parents=True)
    used: set[str] = set()
    saved = []
    for upload in uploads:
        filename = safe_filename(upload.name, used)
        (folder / filename).write_bytes(upload.data)
        # Force transcription only applies to pages that have an image to read.
        force = upload.force_transcription and kind_of(filename) != "text"
        saved.append(SavedFile(filename, upload.role, force))
    return saved
