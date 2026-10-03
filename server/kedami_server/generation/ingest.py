"""Stage 1: turn uploaded files into normalized Markdown with LaTeX, page by page.

Page routing (architecture/pipeline.md):
- text or Markdown file: keep
- image file: transcribe
- any page of a file with force transcription on: transcribe
- PDF page with no or negligible text layer: transcribe
- PDF page with a text layer: keep it if a small check judges it clean, otherwise transcribe
When the small check gives no verdict for a page, the page takes the safer route and is transcribed.
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from . import prompts
from .retry import retrying
from .schemas import TextChecks, Transcription
from .sources import Page, page_png, read_pages

MIN_TEXT_CHARS = 40
TRANSCRIBE_WORKERS = 4

KEEP = "keep"
TRANSCRIBE = "transcribe"


@dataclass(frozen=True)
class Material:
    filename: str
    role: str
    force_transcription: bool


@dataclass(frozen=True)
class RoutedPage:
    file: str
    role: str
    page: int
    route: str
    reason: str
    markdown: str


@dataclass(frozen=True)
class Normalized:
    problem_set: str
    reference: str


def route_pages(material: Material, pages: list[Page], call: Callable) -> list[tuple[Page, str, str]]:
    """Decide each page's route and the reason, before any transcription."""
    decided: dict[int, tuple[str, str]] = {}
    to_check = []
    for page in pages:
        if page.kind == "text":
            decided[page.number] = (KEEP, "text file")
        elif page.kind == "image":
            decided[page.number] = (TRANSCRIBE, "image file")
        elif material.force_transcription:
            decided[page.number] = (TRANSCRIBE, "force transcription is on")
        elif len("".join((page.text or "").split())) < MIN_TEXT_CHARS:
            decided[page.number] = (TRANSCRIBE, "no usable text layer")
        else:
            to_check.append(page)

    if to_check:
        checks = retrying(
            f"Text check for {material.filename}",
            lambda _feedback: call(
                "small_check",
                system=prompts.TEXT_CHECK_SYSTEM,
                prompt=[prompts.text_check_request(material.filename, [(p.number, p.text) for p in to_check])],
                output=TextChecks,
            ),
        )
        verdicts = {c.page: c.clean for c in checks.pages}
        for page in to_check:
            if page.number not in verdicts:
                decided[page.number] = (TRANSCRIBE, "the text check gave no verdict")
            elif verdicts[page.number]:
                decided[page.number] = (KEEP, "text layer judged clean")
            else:
                decided[page.number] = (TRANSCRIBE, "text layer judged unclean")

    return [(page, *decided[page.number]) for page in pages]


def ingest(source_dir: Path, materials: list[Material], call: Callable) -> tuple[Normalized, list[RoutedPage]]:
    routed: list[tuple[Material, Page, str, str]] = []
    for material in materials:
        pages = read_pages(source_dir / material.filename)
        routed += [(material, page, route, reason) for page, route, reason in route_pages(material, pages, call)]

    # PDFium is not thread-safe, so pages are rendered here, one at a time, and only the model calls run in parallel.
    images = {
        (material.filename, page.number): page_png(source_dir / material.filename, page)
        for material, page, route, _ in routed
        if route == TRANSCRIBE
    }

    def transcribe(key: tuple[str, int]) -> str:
        file, number = key
        reply = retrying(
            f"Transcription of {file} page {number}",
            lambda _feedback: call(
                "transcribe",
                system=prompts.TRANSCRIBE_SYSTEM,
                prompt=prompts.transcribe_request(file, number, images[key]),
                output=Transcription,
            ),
        )
        return reply.markdown

    with ThreadPoolExecutor(max_workers=TRANSCRIBE_WORKERS) as pool:
        transcribed = dict(zip(images, pool.map(transcribe, images)))

    pages = [
        RoutedPage(
            file=material.filename,
            role=material.role,
            page=page.number,
            route=route,
            reason=reason,
            markdown=transcribed[(material.filename, page.number)] if route == TRANSCRIBE else (page.text or ""),
        )
        for material, page, route, reason in routed
    ]
    return Normalized(_join(pages, "problem_set"), _join(pages, "reference")), pages


def _join(pages: list[RoutedPage], role: str) -> str:
    """One document per role, each page marked with where it came from. Blank pages are left out."""
    return "\n\n".join(
        f"[{p.file}, page {p.page}]\n\n{p.markdown.strip()}" for p in pages if p.role == role and p.markdown.strip()
    )
