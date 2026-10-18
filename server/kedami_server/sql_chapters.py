"""SQL querying in 15 chapters, in the order courses usually teach it, with what each recommends problems from.
See architecture/sql-lessons.md, Chapters.

A chapter with Spider features recommends Spider exercises that use them; one without recommends pgexercises
pages. Each pgexercises page here was checked to practice its chapter when it was added. Kedami keeps only its
path and title, never its text. Each chapter also names the pages of the bundled book its explanations draw on;
see The book in architecture/sql-lessons.md.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Page:
    path: str
    title: str


@dataclass(frozen=True)
class Chapter:
    number: int
    name: str
    features: frozenset[str] = frozenset()
    pages: tuple[Page, ...] = field(default=())
    # Titles of the book's pages, under "Structured Query Language/".
    book: tuple[str, ...] = ()


CHAPTERS = (
    Chapter(1, "Selecting", frozenset({"selecting"}), book=("SELECT: Fundamentals",)),
    Chapter(2, "Filtering", frozenset({"filtering"}), book=("SELECT: Fundamentals", "Quantified Comparison")),
    Chapter(3, "Text and patterns", frozenset({"patterns"}), book=("Like Predicate", "SELECT: Predefined Functions")),
    Chapter(
        4,
        "Nulls",
        pages=(Page("aggregates/count3.html", "Count the number of recommendations each member makes"),),
        book=("SELECT: IS NULL Predicate", "NULLs and the Three Valued Logic"),
    ),
    Chapter(
        5,
        "Sorting and limiting",
        frozenset({"sorting", "limiting", "distinct"}),
        book=("SELECT: Fundamentals", "Retrieve Top N Rows per Group", "Eliminate Duplicates"),
    ),
    Chapter(
        6,
        "Expressions and CASE",
        pages=(Page("basic/classify.html", "Classify results into buckets"),),
        book=("SELECT: Case Expression", "SELECT: Predefined Functions"),
    ),
    Chapter(7, "Aggregates", frozenset({"aggregates"}), book=("SELECT: Grouping",)),
    Chapter(8, "Grouping", frozenset({"grouping", "having"}), book=("SELECT: Grouping",)),
    Chapter(9, "Inner joins", frozenset({"joins"}), book=("SELECT: Join Operation",)),
    Chapter(
        10,
        "Outer and self joins",
        pages=(
            Page("joins/self.html", "Produce a list of all members who have recommended another member"),
            Page("joins/self2.html", "Produce a list of all members, along with their recommender"),
        ),
        book=("SELECT: Join Operation",),
    ),
    Chapter(11, "Subqueries", frozenset({"subqueries"}), book=("SELECT: Subquery", "Quantified Comparison")),
    Chapter(12, "Set operations", frozenset({"set operations"}), book=("SELECT: Set Operations",)),
    Chapter(
        13,
        "CTEs",
        pages=(
            Page("recursive/getupward.html", "Find the upward recommendation chain for member ID 27"),
            Page("recursive/getdownward.html", "Find the downward recommendation chain for member ID 1"),
            Page(
                "recursive/getupwardall.html",
                "Produce a CTE that can return the upward recommendation chain for any member",
            ),
        ),
        book=("with clause", "Recursions"),
    ),
    Chapter(
        14,
        "Window functions",
        pages=(
            Page(
                "aggregates/countmembers.html",
                "Produce a list of member names, with each row containing the total member count",
            ),
            Page("aggregates/nummembers.html", "Produce a numbered list of members"),
            Page("aggregates/rankmembers.html", "Rank members by (rounded) hours used"),
        ),
        book=("Window functions",),
    ),
    Chapter(
        15,
        "Dates and times",
        pages=(
            Page("basic/date.html", "Working with dates"),
            Page("date/timestamp.html", "Produce a timestamp for 1 a.m. on the 31st of August 2012"),
            Page("date/interval.html", "Subtract timestamps from each other"),
            Page("date/series.html", "Generate a list of all the dates in October 2012"),
            Page("date/extract.html", "Get the day of the month from a timestamp"),
            Page("date/interval2.html", "Work out the number of seconds between timestamps"),
            Page("date/daysinmonth.html", "Work out the number of days in each month of 2012"),
            Page("date/daysremaining.html", "Work out the number of days remaining in the month"),
            Page("date/endtimes.html", "Work out the end time of bookings"),
            Page("date/bookingspermonth.html", "Return a count of bookings for each month"),
            Page("date/utilisationpermonth.html", "Work out the utilisation percentage for each facility by month"),
        ),
        book=("SELECT: Predefined Functions",),
    ),
)

PGEXERCISES = "https://pgexercises.com/questions/"
# A page is one section folder and one page name. The renderer and main both check this before opening one.
PAGE_PATH = re.compile(r"^[a-z]+/[a-z0-9]+\.html$")


def chapter(number: int) -> Chapter:
    for c in CHAPTERS:
        if c.number == number:
            return c
    raise KeyError(f"no SQL chapter {number}")


def known_features(number: int) -> frozenset[str]:
    """The Spider features a chapter's problems may use: its own and every earlier chapter's, and selecting."""
    return frozenset({"selecting"}).union(*(c.features for c in CHAPTERS if c.number <= number))


BOOK = "Structured Query Language"
BOOK_DIR = Path(__file__).parent / "sql_book"
BOOK_CREDIT = (
    "Explanations draw on Structured Query Language, Wikibooks (CC BY-SA): "
    "en.wikibooks.org/wiki/Structured_Query_Language"
)


def book_file(title: str) -> str:
    """A book page's file name in sql_book/: "SELECT: Fundamentals" is "select-fundamentals.md"."""
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") + ".md"


def book_reference(number: int) -> str:
    """A chapter's pages of the book, as one reference document, credited at the top."""
    pages = [(BOOK_DIR / book_file(title)).read_text(encoding="utf-8") for title in chapter(number).book]
    return f"{BOOK_CREDIT}\n\n" + "\n\n".join(pages)


def page(path: str) -> Page | None:
    return next((p for c in CHAPTERS for p in c.pages if p.path == path), None)
