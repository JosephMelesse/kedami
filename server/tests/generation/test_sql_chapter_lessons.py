"""SQL chapter lessons: recommending problems, checking a picked database, and refusing a bad chapter lesson.
See architecture/sql-lessons.md, Creating a SQL lesson."""

import pytest

from .conftest import AUTH
from .test_pipeline import lesson_status
from .test_sql_lessons import BANK, COURSE, import_bank

# BANK's second exercise filters; chapter 2 recommends it.
PT = "music-0000000001"
PROBLEMS = f"1. spider:{PT} Which singers are from PT?\n2. pgexercises:joins/self.html Recommenders\n".encode()


def create(client, chapter=2, files=None, domain="sql"):
    files = files if files is not None else [("problems.md", PROBLEMS, "problem_set")]
    return client.post(
        "/lessons",
        data={"subject": "computer_science", "domain": domain, "chapter": str(chapter),
              "roles": [f[2] for f in files], "force": ["false" for _ in files]},
        files=[("files", (f[0], f[1], "application/octet-stream")) for f in files],
        headers=AUTH,
    )


# Recommending


def test_chapters_list_each_with_how_many_problems_it_can_recommend(started, data_dir):
    client, _, _ = started
    import_bank(data_dir, BANK)
    reply = client.get("/sql/chapters", headers=AUTH).json()
    assert reply["imported"] is True
    chapters = {c["number"]: c for c in reply["chapters"]}
    assert len(chapters) == 15
    assert chapters[1] == {"number": 1, "name": "Selecting", "source": "spider", "available": 1}
    assert chapters[2]["available"] == 1
    assert chapters[10] == {"number": 10, "name": "Outer and self joins", "source": "pgexercises", "available": 2}


def test_with_nothing_imported_spider_chapters_have_nothing(started):
    client, _, _ = started
    reply = client.get("/sql/chapters", headers=AUTH).json()
    assert reply["imported"] is False
    assert {c["available"] for c in reply["chapters"] if c["source"] == "spider"} == {0}
    assert all(c["available"] > 0 for c in reply["chapters"] if c["source"] == "pgexercises")


def test_recommend_returns_problems_and_how_many_the_chapter_has(started, data_dir):
    client, _, _ = started
    import_bank(data_dir, BANK)
    reply = client.post("/sql/recommend", json={"chapter": 2}, headers=AUTH).json()
    assert reply == {"available": 1, "problems": [
        {"source": "spider", "id": PT, "text": "Which singers are from PT?", "database": "music"},
    ]}
    pages = client.post("/sql/recommend", json={"chapter": 10, "count": 1, "round": 3}, headers=AUTH).json()
    assert pages["problems"] == [{"source": "pgexercises", "id": "joins/self.html", "database": None,
                                  "text": "Produce a list of all members who have recommended another member"}]


@pytest.mark.parametrize("body", [
    {"chapter": 16}, {"chapter": 0}, {"chapter": 2, "count": 0}, {"chapter": 2, "count": 11},
    {"chapter": 2, "round": -1}, {"chapter": "2"}, {"chapter": 2, "extra": 1},
])
def test_recommend_refuses_a_bad_request(started, body):
    client, _, _ = started
    assert client.post("/sql/recommend", json=body, headers=AUTH).status_code == 422


# Checking a course database when it is picked


def test_a_picked_database_is_checked_and_not_kept(started, data_dir):
    client, _, _ = started
    reply = client.post("/sql/database", files={"file": ("My Course.sql", COURSE)}, headers=AUTH)
    assert reply.status_code == 200
    assert reply.json() == {"name": "My_Course", "tables": [{"name": "student", "count": 3},
                                                             {"name": "enrolled", "count": 3}]}
    assert not (data_dir / "materials").exists()


@pytest.mark.parametrize("name, data, message", [
    ("db.sql", b"CREATE TABLE (", "db.sql failed"),
    ("db.sql", b"ATTACH 'x' AS y;", "db.sql failed"),
    ("db.csv", COURSE, "isn't a SQLite file"),
    ("db.sqlite", b"not a database", "db.sqlite"),
])
def test_a_picked_database_that_fails_says_why(started, name, data, message):
    client, _, _ = started
    reply = client.post("/sql/database", files={"file": (name, data)}, headers=AUTH)
    assert reply.status_code == 422
    assert message in reply.json()["detail"]


# Creating a chapter lesson


@pytest.mark.parametrize("chapter, files, domain, message", [
    (2, None, "dsa", "Only a SQL lesson is made from a chapter"),
    (16, None, "sql", "There is no SQL chapter 16"),
    (2, [("problems.md", PROBLEMS, "problem_set"), ("notes.md", b"Notes", "reference")], "sql", "only its recommended"),
    (2, [("problems.pdf", PROBLEMS, "problem_set")], "sql", "only its recommended"),
    (2, [("problems.md", PROBLEMS, "problem_set"), ("db.sql", COURSE, "database")], "sql", "takes no database"),
    (2, [("problems.md", b"1. spider:music-9 Gone", "problem_set")], "sql", "doesn't have: 'music-9'"),
    (2, [("problems.md", b"\xff\xfe", "problem_set")], "sql", "not UTF-8"),
])
def test_a_bad_chapter_lesson_is_refused_before_anything_is_saved(started, data_dir, chapter, files, domain, message):
    client, _, runs = started
    import_bank(data_dir, BANK)
    response = create(client, chapter, files, domain)
    assert response.status_code == 422
    assert message in response.json()["detail"]
    assert runs == []
    assert not (data_dir / "materials").exists()


def test_a_sql_lesson_with_its_own_problem_set_has_no_chapter(started, data_dir):
    client, _, _ = started
    response = client.post(
        "/lessons",
        data={"subject": "computer_science", "domain": "sql", "roles": ["problem_set"], "force": ["false"]},
        files=[("files", ("ps.md", b"1. List the students.", "text/markdown"))],
        headers=AUTH,
    )
    assert response.status_code == 201
    names = [m["filename"] for m in lesson_status(client, response.json()["id"])["materials"]]
    assert names == ["ps.md"]
