"""Fetch the SQL book's pages from Wikibooks and write them into the server as Markdown. A maintainer tool, run by
hand from server/ as `python -m tools.fetch_sql_book`; the app never fetches the book.

Writes kedami_server/sql_book/: one Markdown file per page the chapters use, SOURCES.md with each page's revision
and the license, and people.sql, the book's example database adapted for SQLite. See architecture/sql-lessons.md,
The book.
"""

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

from kedami_server.databases import from_upload, tables
from kedami_server.sql_chapters import BOOK, BOOK_DIR, CHAPTERS, book_file

from .wikitext import _CODE_BLOCK, to_markdown

API = "https://en.wikibooks.org/w/api.php"
USER_AGENT = "Kedami/0.1 (maintainer tool fetching an open book for a personal study app)"
EXAMPLE_PAGES = ("Example Database Structure", "Example Database Data")
# Wikibooks answers many requests from one client with 429; these are the waits before each retry.
WAITS_S = (30, 60, 120, 180)
BATCH = 50

Fetch = Callable[[str], dict]


def book_titles() -> list[str]:
    """Every page the chapters use, then the example database's pages, each once."""
    titles = dict.fromkeys(title for chapter in CHAPTERS for title in chapter.book)
    return [*titles, *EXAMPLE_PAGES]


def fetch_pages(titles: list[str], fetch: Fetch | None = None, sleep: Callable[[float], None] = time.sleep) -> dict:
    """Each page's revision ID and wikitext, by title, asking for up to 50 pages a request."""
    fetch = fetch or _get
    pages = {}
    for start in range(0, len(titles), BATCH):
        names = "|".join(f"{BOOK}/{title}" for title in titles[start : start + BATCH])
        url = API + "?" + urllib.parse.urlencode({
            "action": "query", "prop": "revisions", "rvprop": "content|ids", "rvslots": "main", "titles": names,
            "format": "json", "formatversion": "2", "redirects": "1",
        })
        reply = _patiently(lambda: fetch(url), sleep)
        for page in reply["query"]["pages"]:
            if "missing" in page:
                raise SystemExit(f"the book has no page {page['title']}")
            revision = page["revisions"][0]
            pages[page["title"].split("/", 1)[1]] = (revision["revid"], revision["slots"]["main"]["content"])
    missing = [t for t in titles if t not in pages]
    if missing:
        raise SystemExit(f"Wikibooks didn't return: {', '.join(missing)}")
    return pages


def _patiently(request: Callable[[], dict], sleep: Callable[[float], None]) -> dict:
    for wait in (*WAITS_S, None):
        try:
            return request()
        except urllib.error.HTTPError as error:
            if error.code != 429 or wait is None:
                raise
            print(f"Wikibooks asked to slow down; waiting {wait}s", file=sys.stderr)
            sleep(wait)
    raise AssertionError("unreachable")


def _get(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def people_script(structure: str, data: str) -> str:
    """The example database's script: the four CREATE TABLEs, then each table's INSERTs, adapted for SQLite.

    Adapted in two ways only: DATE'1970-11-20' literals become the text '1970-11-20', as SQLite keeps dates, and
    bare COMMIT statements are dropped, since SQLite refuses a COMMIT with no transaction open. The Data page's
    one-row SQLite example and its "Grow up" block, which doubles the rows, are left out. Raises SystemExit if
    either page no longer has the blocks expected, so a change to the book is noticed.
    """
    creates = [m[3].strip() for m in _CODE_BLOCK.finditer(structure)]
    inserts = [m[3].strip() for m in _CODE_BLOCK.finditer(data)]
    if len(creates) != 4 or any("CREATE TABLE" not in c for c in creates):
        raise SystemExit("the Example Database Structure page no longer has four CREATE TABLE blocks")
    wanted = [b for b in inserts if "INSERT INTO" in b and not b.startswith("-- SQLite syntax") and "SELECT" not in b]
    if [re.search(r"INSERT INTO (\w+)", b)[1] for b in wanted] != ["person", "contact", "hobby", "person_hobby"]:
        raise SystemExit("the Example Database Data page no longer has one INSERT block per table, in order")
    script = "\n\n".join(creates + wanted)
    script = re.sub(r"\bDATE\s*'(\d{4}-\d{2}-\d{2})'", r"'\1'", script)
    return re.sub(r"(?m)^[ \t]*COMMIT[ \t]*;[ \t]*$\n?", "", script)


def page_url(title: str, revision: int | None = None) -> str:
    path = urllib.parse.quote(f"{BOOK}/{title}".replace(" ", "_"))
    return f"https://en.wikibooks.org/wiki/{path}" + (f"?oldid={revision}" if revision else "")


def sources(pages: dict) -> str:
    lines = [
        "# Sources",
        "",
        f'The files here are converted from the Wikibooks book "{BOOK}", by Wikibooks contributors, under the '
        "Creative Commons Attribution-ShareAlike 4.0 license (https://creativecommons.org/licenses/by-sa/4.0/). "
        "They are adapted: converted to Markdown, with navigation and images left out. people.sql is adapted from "
        "the Example Database pages for SQLite, as its header says. They carry the same license.",
        "",
        "| Page | File | Revision |",
        "| --- | --- | --- |",
    ]
    for title, (revision, _) in pages.items():
        file = "people.sql" if title in EXAMPLE_PAGES else book_file(title)
        lines.append(f"| [{title}]({page_url(title)}) | {file} | [{revision}]({page_url(title, revision)}) |")
    return "\n".join(lines) + "\n"


def write(pages: dict, folder: Path = BOOK_DIR) -> list[str]:
    """Write the book's files, checking the example database builds. Returns the files written."""
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for title, (_, wikitext) in pages.items():
        if title in EXAMPLE_PAGES:
            continue
        (folder / book_file(title)).write_text(to_markdown(wikitext, title), encoding="utf-8")
        written.append(book_file(title))
    structure, data = (pages[t][1] for t in EXAMPLE_PAGES)
    revisions = ", ".join(f"{t} revision {pages[t][0]}" for t in EXAMPLE_PAGES)
    header = (
        f'-- The example database of the Wikibooks book "{BOOK}" ({revisions}), CC BY-SA 4.0.\n'
        "-- Adapted for SQLite: date literals as text, and bare COMMIT statements dropped.\n\n"
    )
    script = header + people_script(structure, data)
    built = tables(from_upload("people.sql", script.encode()))
    if [t["name"] for t in built] != ["person", "contact", "hobby", "person_hobby"]:
        raise SystemExit("people.sql didn't build the four example tables")
    (folder / "people.sql").write_text(script, encoding="utf-8")
    (folder / "SOURCES.md").write_text(sources(pages), encoding="utf-8")
    return [*written, "people.sql", "SOURCES.md"]


def main() -> None:
    pages = fetch_pages(book_titles())
    for name in write(pages):
        print(f"wrote {BOOK_DIR / name}")


if __name__ == "__main__":
    main()
