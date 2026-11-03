"""Checking and saving the files a new lesson is made from."""

from dataclasses import dataclass
from pathlib import Path

from .generation.sources import MAX_PAGES, SourceError, kind_of, page_count, safe_filename

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
