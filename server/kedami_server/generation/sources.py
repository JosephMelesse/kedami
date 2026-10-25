"""Uploaded course files: what kind each is and how many pages it has, checked at upload."""

import io
import re
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, UnidentifiedImageError

TEXT_SUFFIXES = {".txt", ".md", ".markdown"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
PDF_SUFFIXES = {".pdf"}

MAX_FILE_BYTES = 30 * 1024 * 1024
MAX_PAGES = 100


class SourceError(ValueError):
    """A file that can't be used, with a message fit to show the student."""


def kind_of(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return "text"
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix in PDF_SUFFIXES:
        return "pdf"
    raise SourceError(f"{filename}: only PDF, image (PNG, JPEG, WebP, GIF), text, and Markdown files are supported")


def safe_filename(name: str, used: set[str]) -> str:
    """A plain file name for the materials folder, unique among `used`."""
    base = Path(name.replace("\\", "/")).name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(base).stem).strip(".-") or "file"
    suffix = Path(base).suffix.lower()
    candidate, n = f"{stem}{suffix}", 2
    while candidate in used:
        candidate, n = f"{stem}-{n}{suffix}", n + 1
    used.add(candidate)
    return candidate


def page_count(filename: str, data: bytes) -> int:
    """Check that the file is readable and return its page count."""
    if len(data) > MAX_FILE_BYTES:
        raise SourceError(f"{filename} is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB")
    kind = kind_of(filename)
    if kind == "text":
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise SourceError(f"{filename} is not UTF-8 text") from error
        return 1
    if kind == "image":
        _open_image(filename, data)
        return 1
    try:
        return len(pdfium.PdfDocument(data))
    except pdfium.PdfiumError as error:
        raise SourceError(f"{filename} could not be read as a PDF") from error


def _open_image(filename: str, data: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
        return image
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise SourceError(f"{filename} could not be read as an image") from error
