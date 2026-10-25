"""Stage 1: the uploaded files as normalized Markdown with LaTeX, page by page.

Claude Code reads every file itself and sends each page's Markdown; see architecture/agent-mode.md.
The pages are joined into one document per role, which the later stages work from.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RoutedPage:
    file: str
    role: str
    page: int
    # How the page was read, saved in pages.json. Agent mode reads every page the same way.
    route: str
    reason: str
    markdown: str


@dataclass(frozen=True)
class Normalized:
    problem_set: str
    reference: str


def join_pages(pages: list[RoutedPage], role: str) -> str:
    """One document per role, each page marked with where it came from. Blank pages are left out."""
    return "\n\n".join(
        f"[{p.file}, page {p.page}]\n\n{p.markdown.strip()}" for p in pages if p.role == role and p.markdown.strip()
    )
