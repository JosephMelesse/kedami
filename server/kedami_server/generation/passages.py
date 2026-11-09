"""Splitting the normalized reference into numbered passages. See Stage 1: passages in architecture/pipeline.md.

Passages are the only way later stages refer to the reference, so a split never loses or moves a line.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from .ingest import TRANSCRIBE, RoutedPage

TEXT = "text"
NOTE = "note"

FIGURE_LINE = re.compile(r"\[Figure:.*\]")
FENCE = re.compile(r"(`{3,}|~{3,})[^`]*")
LIST_ITEM = re.compile(r"\s*(?:[-*+]|\d+[.)])\s")
MATH = "$$"


@dataclass(frozen=True)
class Passage:
    number: int
    kind: str
    file: str
    page: int
    text: str


def split_passages(pages: list[RoutedPage]) -> list[Passage]:
    """The reference's pages as numbered passages. Each page is split alone, so a page break always ends a passage."""
    parts = [
        (page, kind, text)
        for page in pages
        if page.role == "reference"
        for kind, text in _split_page(page.markdown, notes=page.route == TRANSCRIBE)
    ]
    return [
        Passage(number=number, kind=kind, file=page.file, page=page.page, text=text)
        for number, (page, kind, text) in enumerate(parts, start=1)
    ]


def _split_page(markdown: str, notes: bool) -> Iterable[tuple[str, str]]:
    current: list[str] = []
    after_blank = False
    closer: str | None = None

    for line in markdown.splitlines():
        if closer is not None:
            current.append(line)
            if _closes(line, closer):
                closer = None
        elif not line.strip():
            after_blank = bool(current)
        elif notes and FIGURE_LINE.fullmatch(line.strip()):
            if current:
                yield TEXT, "\n".join(current)
                current, after_blank = [], False
            yield NOTE, line.strip()
        else:
            if after_blank:
                if _continues(current, line):
                    current.append("")
                else:
                    yield TEXT, "\n".join(current)
                    current = []
                after_blank = False
            current.append(line)
            closer = _opens(line)
    if current:
        yield TEXT, "\n".join(current)


def _opens(line: str) -> str | None:
    """What will close the block this line opens: a code fence, or `$$` math left open on the line."""
    stripped = line.strip()
    fence = FENCE.fullmatch(stripped)
    if fence:
        return fence.group(1)
    return MATH if stripped.count(MATH) % 2 else None


def _closes(line: str, closer: str) -> bool:
    stripped = line.strip()
    if closer == MATH:
        return stripped.count(MATH) % 2 == 1
    return len(stripped) >= len(closer) and not stripped.strip(closer[0])


def _continues(current: list[str], line: str) -> bool:
    """Whether a line after a blank line still belongs to the list or table before the blank."""
    if line.lstrip().startswith("|") and current[-1].lstrip().startswith("|"):
        return True
    in_list = any(LIST_ITEM.match(earlier) for earlier in current)
    return in_list and (LIST_ITEM.match(line) is not None or line[0] in " \t")
