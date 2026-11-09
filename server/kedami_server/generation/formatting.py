"""Formatting a reference's kept PDF pages as Markdown. See Stage 1: formatting in architecture/pipeline.md.

The model only adds structure. The word check decides whether its reply is used, and a page it rejects, like a page
the model left out or a call that failed, keeps its raw text, so formatting never fails a lesson.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING

from ..model import ModelError
from . import prompts
from .retry import GenerationError, retrying
from .schemas import FormattedPage, FormattedPages
from .wordcheck import same_words

if TYPE_CHECKING:
    from .ingest import RoutedPage

log = logging.getLogger(__name__)

MAX_PAGES_PER_CALL = 10

FORMATTED = "formatted"
FAILED_WORD_CHECK = "failed the word check"
LEFT_OUT = "left out of the reply"
CALL_FAILED = "the format call failed"


def runs_of_pages(pages: list[RoutedPage]) -> list[list[RoutedPage]]:
    """Consecutive pages of one file, at most a call's worth in each run, so the model can see what repeats."""
    runs: list[list[RoutedPage]] = []
    for page in pages:
        last = runs[-1][-1] if runs else None
        if last and last.file == page.file and last.page + 1 == page.page and len(runs[-1]) < MAX_PAGES_PER_CALL:
            runs[-1].append(page)
        else:
            runs.append([page])
    return runs


def format_run(pages: list[RoutedPage], call: Callable) -> list[RoutedPage]:
    """One call for a run of pages. Each page comes back formatted, or with its raw text and the reason."""
    file = pages[0].file
    try:
        reply = retrying(
            f"Formatting of {file}",
            lambda _feedback: call(
                "format",
                system=prompts.FORMAT_SYSTEM,
                prompt=[prompts.format_request(file, [(p.page, p.markdown) for p in pages])],
                output=FormattedPages,
            ),
        )
    except (GenerationError, ModelError) as failure:
        log.warning("formatting %s pages %d to %d failed: %s", file, pages[0].page, pages[-1].page, failure)
        return [replace(page, format=CALL_FAILED) for page in pages]
    replies = {formatted.page: formatted for formatted in reply.pages}
    return [_checked(page, replies.get(page.page)) for page in pages]


def _checked(page: RoutedPage, reply: FormattedPage | None) -> RoutedPage:
    if reply is None:
        return replace(page, format=LEFT_OUT)
    if not same_words(page.markdown, reply.markdown, reply.dropped_lines):
        return replace(page, format=FAILED_WORD_CHECK)
    return replace(page, markdown=reply.markdown, format=FORMATTED, dropped_lines=reply.dropped_lines)
