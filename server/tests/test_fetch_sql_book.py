"""The maintainer tool that fetches the SQL book. See architecture/sql-lessons.md, The book."""

import io
import urllib.error
import urllib.parse

import pytest

from kedami_server.sql_chapters import BOOK, CHAPTERS
from tools import fetch_sql_book
from tools.fetch_sql_book import EXAMPLE_PAGES, book_titles, fetch_pages


def reply(titles, missing=()):
    pages = []
    for title in titles:
        full = f"{BOOK}/{title}"
        if title in missing:
            pages.append({"title": full, "missing": True})
        else:
            pages.append({"title": full, "revisions": [{"revid": 7, "slots": {"main": {"content": f"text of {title}"}}}]})
    return {"query": {"pages": pages}}


def asked_for(url: str) -> list[str]:
    names = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["titles"][0].split("|")
    return [name.removeprefix(f"{BOOK}/") for name in names]


def too_many_requests():
    return urllib.error.HTTPError("https://en.wikibooks.org", 429, "Too Many Requests", {}, io.BytesIO())


class TestTitles:
    def test_every_chapter_page_once_then_the_example_database(self):
        titles = book_titles()
        assert len(titles) == len(set(titles))
        assert titles[-2:] == list(EXAMPLE_PAGES)
        assert {t for c in CHAPTERS for t in c.book} == set(titles[:-2])


class TestFetch:
    def test_pages_by_title_with_their_revisions(self):
        urls = []

        def fetch(url):
            urls.append(url)
            return reply(asked_for(url))

        pages = fetch_pages(["with clause", "Recursions"], fetch)
        assert pages == {"with clause": (7, "text of with clause"), "Recursions": (7, "text of Recursions")}
        assert len(urls) == 1
        assert urls[0].startswith("https://en.wikibooks.org/w/api.php?")

    def test_asks_for_at_most_fifty_pages_at_a_time(self):
        asked = []

        def fetch(url):
            asked.append(asked_for(url))
            return reply(asked[-1])

        titles = [f"Page {n}" for n in range(120)]
        assert list(fetch_pages(titles, fetch)) == titles
        assert [len(a) for a in asked] == [50, 50, 20]

    def test_waits_and_retries_when_asked_to_slow_down(self):
        answers = [too_many_requests(), too_many_requests()]
        waits = []

        def fetch(url):
            if answers:
                raise answers.pop()
            return reply(asked_for(url))

        assert fetch_pages(["with clause"], fetch, waits.append) == {"with clause": (7, "text of with clause")}
        assert waits == [30, 60]

    def test_gives_up_after_the_last_wait(self):
        waits = []

        def fetch(url):
            raise too_many_requests()

        with pytest.raises(urllib.error.HTTPError):
            fetch_pages(["with clause"], fetch, waits.append)
        assert waits == list(fetch_sql_book.WAITS_S)

    def test_other_errors_are_not_retried(self):
        waits = []

        def fetch(url):
            raise urllib.error.HTTPError(url, 500, "Server Error", {}, io.BytesIO())

        with pytest.raises(urllib.error.HTTPError):
            fetch_pages(["with clause"], fetch, waits.append)
        assert waits == []

    def test_a_missing_page_stops_the_tool(self):
        with pytest.raises(SystemExit, match="no page"):
            fetch_pages(["with clause", "Gone"], lambda url: reply(asked_for(url), missing={"Gone"}))

    def test_a_page_not_returned_stops_the_tool(self):
        with pytest.raises(SystemExit, match="Recursions"):
            fetch_pages(["with clause", "Recursions"], lambda url: reply(["with clause"]))
