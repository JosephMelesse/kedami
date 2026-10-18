"""SQL chapter lessons: recommending problems, creating a lesson from them with the book and its example database,
and generating it. See architecture/sql-lessons.md, Creating a SQL lesson."""

import pytest

from kedami_server.generation import pipeline
from kedami_server.generation.schemas import ConceptMap, HintDraft, HintJudgements, Plan, ProblemsAndConcepts, SectionDraft
from kedami_server.lesson import ExternalAnswer, Lesson, QueryAnswer
from kedami_server.sql_chapters import BOOK_CREDIT

from .conftest import AUTH
from .test_pipeline import FakeModel, all_fine, hints_for, lesson_status
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


def chapter_script():
    return {
        ConceptMap: [{
            "concepts": [{"id": "where", "name": "WHERE", "summary": "Keeping the rows that match."}],
            "problems": [{"number": 1, "concepts": ["where"]}, {"number": 2, "concepts": ["where"]}],
        }],
        Plan: [Plan.model_validate({"title": "Filtering", "sections": [
            {"title": "WHERE", "goal": "Keep matching rows.", "concepts": ["where"],
             "sql_features": ["selecting", "filtering"]},
        ]})],
        SectionDraft: [{"blocks": [
            {"type": "explanation", "body": "```sql\nSELECT firstname FROM person WHERE weight > 80;\n```"},
            {"type": "problem", "source_ref": "Problem 1", "parts": []},
            {"type": "problem", "source_ref": "Problem 2", "parts": []},
        ]}],
        HintDraft: [hints_for("problem-1/1", "problem-2/2")],
        HintJudgements: [all_fine],
    }


@pytest.fixture
def chapter_lesson(started, data_dir):
    client, _, runs = started
    import_bank(data_dir, BANK)
    response = create(client)
    assert response.status_code == 201, response.text
    return client, response.json()["id"], runs


@pytest.fixture
def ready(chapter_lesson, data_dir):
    client, lesson_id, _ = chapter_lesson
    fake = FakeModel(chapter_script())
    pipeline.run(data_dir, lesson_id, "computer_science", 1, call=fake)
    status = lesson_status(client, lesson_id)
    assert (status["status"], status["error"]) == ("ready", None)
    return client, lesson_id, Lesson.model_validate(status["lesson"]), fake


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


def test_a_chapter_lesson_gets_the_books_pages_and_example_database(chapter_lesson, data_dir):
    client, lesson_id, runs = chapter_lesson
    assert len(runs) == 1
    materials = {m["filename"]: m["role"] for m in lesson_status(client, lesson_id)["materials"]}
    assert materials == {"problems.md": "problem_set", "wikibooks-2.md": "reference"}
    reference = (data_dir / "materials" / lesson_id / "wikibooks-2.md").read_text(encoding="utf-8")
    assert reference.startswith(BOOK_CREDIT)
    assert "# SELECT: Fundamentals" in reference and "# Quantified Comparison" in reference
    assert (data_dir / "materials" / lesson_id / "databases" / "people.sqlite").is_file()


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


# Generating a chapter lesson


def test_a_chapter_lesson_end_to_end(ready):
    _, _, lesson, _ = ready
    assert lesson.domain == "sql"
    assert lesson.credits == [BOOK_CREDIT]

    bank = lesson.find_block("problem-1").parts[0]
    assert bank.prompt == "Which singers are from PT?"
    assert bank.answer == QueryAnswer(kind="query", database="bank/music",
                                      reference="SELECT name FROM singer WHERE country = 'PT'", exercise=PT)
    assert bank.verified is False and bank.hints
    page = lesson.find_block("problem-2").parts[0]
    assert isinstance(page.answer, ExternalAnswer) and page.answer.platform == "pgexercises"
    assert page.answer.url == "https://pgexercises.com/questions/joins/self.html"

    # Practice never repeats a problem from the problem set.
    practice = [b for b in lesson.sections[0].blocks if "-practice-" in b.id]
    assert [b.answer.exercise for b in practice] == ["music-0000000000"]


def test_the_model_sees_the_book_both_databases_and_the_chapter_rules(ready):
    _, _, _, fake = ready
    assert ProblemsAndConcepts not in fake.calls
    material = fake.calls[ConceptMap][0]["prompt"][0]["text"]
    assert "<reference_material>" in material and "# SELECT: Fundamentals" in material
    assert "<course_database>\nDatabase `people` (SQLite):" in material
    assert "Table person (id, firstname, lastname, date_of_birth, place_of_birth, ssn, weight), 10 rows" in material
    assert "<problem_databases>\nDatabase `music` (SQLite):" in material
    request = fake.calls[ConceptMap][0]["prompt"][-1]["text"]
    assert '"database": "music"' in request and '"solved_on": "pgexercises"' in request
    section_system = fake.calls[SectionDraft][0]["system"]
    assert "course database `people`" in section_system
    assert "ROLLUP and CUBE" in section_system and "`parts` as an empty list" in section_system


def test_a_rerun_from_planning_keeps_the_chapter(ready, data_dir):
    client, lesson_id, _, _ = ready
    script = chapter_script()
    del script[ConceptMap]
    fake = FakeModel(script)
    pipeline.run(data_dir, lesson_id, "computer_science", 3, call=fake)
    status = lesson_status(client, lesson_id)
    assert status["status"] == "ready"
    lesson = Lesson.model_validate(status["lesson"])
    assert lesson.credits == [BOOK_CREDIT]
    assert lesson.find_block("problem-1").parts[0].answer.exercise == PT


def test_a_problem_whose_exercise_is_gone_fails_the_lesson_with_a_reason(chapter_lesson, data_dir):
    client, lesson_id, _ = chapter_lesson
    bank = data_dir / "sql" / "exercises.jsonl"
    bank.write_text(bank.read_text().splitlines(keepends=True)[0])
    pipeline.run(data_dir, lesson_id, "computer_science", 1, call=FakeModel(chapter_script()))
    status = lesson_status(client, lesson_id)
    assert status["status"] == "failed"
    assert f"doesn't have: '{PT}'" in status["error"]
