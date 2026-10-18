"""The maintainer tool that fetches the SQL book. See architecture/sql-lessons.md, The book."""

import io
import re
import urllib.error
import urllib.parse
from pathlib import Path

import pytest

from kedami_server.databases import from_upload, tables
from kedami_server.sql_chapters import BOOK, BOOK_DIR, CHAPTERS, book_file
from tools import fetch_sql_book
from tools.fetch_sql_book import EXAMPLE_PAGES, book_titles, fetch_pages, people_script, write

FIXTURES = Path(__file__).parent / "fixtures" / "sql_book"
REVISIONS = {
    "SELECT: Join Operation": 4660736,
    "with clause": 4660904,
    "Example Database Structure": 3698876,
    "Example Database Data": 4069437,
}


def wikitext(title: str) -> str:
    return (FIXTURES / (title.replace(":", "").replace(" ", "_") + ".wiki")).read_text(encoding="utf-8")


def example_pages() -> tuple[str, str]:
    return wikitext("Example Database Structure"), wikitext("Example Database Data")


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


class TestPeople:
    def test_builds_the_four_tables_with_the_book_rows(self):
        built = {t["name"]: t for t in tables(from_upload("people.sql", people_script(*example_pages()).encode()))}
        assert list(built) == ["person", "contact", "hobby", "person_hobby"]
        assert [len(built[name]["rows"]) for name in built] == [10, 9, 9, 9]

    def test_dates_are_text_and_bare_commits_are_dropped(self):
        script = people_script(*example_pages())
        assert "DATE'" not in script and "DATE '" not in script
        assert "'1970-11-20'" in script
        assert not re.search(r"(?m)^\s*COMMIT\s*;", script)

    def test_leaves_out_the_sqlite_example_and_the_grow_up_block(self):
        script = people_script(*example_pages())
        assert "-- SQLite syntax" not in script
        assert "INSERT INTO person SELECT" not in script.replace("\n", " ")

    def test_a_changed_structure_page_stops_the_tool(self):
        structure, data = example_pages()
        with pytest.raises(SystemExit, match="Structure"):
            people_script(structure.replace("CREATE TABLE hobby", "CREATE VIEW hobby"), data)

    def test_a_changed_data_page_stops_the_tool(self):
        structure, data = example_pages()
        with pytest.raises(SystemExit, match="Data"):
            people_script(structure, data.replace("INSERT INTO hobby", "INSERT INTO hobbies"))

    def test_the_bundled_database_matches_the_tool(self):
        header, _, script = (BOOK_DIR / "people.sql").read_text(encoding="utf-8").partition("\n\n")
        assert script == people_script(*example_pages())
        assert "Example Database Structure revision 3698876" in header


class TestWrite:
    @pytest.fixture
    def written(self, tmp_path):
        pages = {title: (revision, wikitext(title)) for title, revision in REVISIONS.items()}
        return tmp_path, write(pages, tmp_path)

    def test_writes_each_page_the_database_and_the_sources(self, written):
        folder, names = written
        assert names == [book_file("SELECT: Join Operation"), book_file("with clause"), "people.sql", "SOURCES.md"]
        assert sorted(p.name for p in folder.iterdir()) == sorted(names)
        assert (folder / "with-clause.md").read_text(encoding="utf-8").startswith("# with clause\n\n")

    def test_sources_credit_the_book_and_link_each_revision(self, written):
        sources = (written[0] / "SOURCES.md").read_text(encoding="utf-8")
        assert "Creative Commons Attribution-ShareAlike 4.0" in sources
        assert "| [with clause](https://en.wikibooks.org/wiki/Structured_Query_Language/with_clause) | " \
            "with-clause.md | [4660904](https://en.wikibooks.org/wiki/Structured_Query_Language/with_clause" \
            "?oldid=4660904) |" in sources
        assert "SELECT%3A_Join_Operation?oldid=4660736" in sources
        assert sources.count("| people.sql |") == 2

    def test_the_database_header_names_the_revisions_and_license(self, written):
        header = (written[0] / "people.sql").read_text(encoding="utf-8").split("\n\n")[0]
        assert "Example Database Data revision 4069437" in header
        assert "CC BY-SA 4.0" in header
