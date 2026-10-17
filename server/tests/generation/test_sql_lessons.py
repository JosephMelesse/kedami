"""SQL lessons end to end: uploading a course database, generation with query answers and bank practice, and
running and checking queries. See architecture/sql-lessons.md."""

import json
import sqlite3

import pytest

from kedami_server import progress
from kedami_server.db import connect
from kedami_server.generation import pipeline, prompts
from kedami_server.generation.schemas import (
    HintDraft,
    HintJudgements,
    HintReplacements,
    Plan,
    ProblemsAndConcepts,
    SectionDraft,
    Solutions,
)
from kedami_server.lesson import Lesson, QueryAnswer
from kedami_server.queries import features

from .conftest import AUTH, upload
from .factories import extraction
from .test_pipeline import FakeModel, all_fine, hints_for, lesson_status

PROBLEMS = b"PS2\n1. (a) List the names of students in year 3.\n2. (b) For each course, how many are enrolled?\n"
COURSE = b"""
CREATE TABLE student (id INTEGER PRIMARY KEY, name TEXT, year INTEGER);
CREATE TABLE enrolled (student_id INTEGER, course TEXT);
INSERT INTO student VALUES (1, 'Ada', 2), (2, 'Grace', 3), (3, 'Linus', 3);
INSERT INTO enrolled VALUES (1, 'CS101'), (2, 'CS101'), (2, 'DB200');
"""
YEAR_3 = "SELECT name FROM student WHERE year = 3"
PER_COURSE = "SELECT course, count(*) FROM enrolled GROUP BY course ORDER BY course"


def import_bank(data_dir, exercises):
    """A small bank in the import's shape: one database, and exercises given as (question, query)."""
    folder = data_dir / "sql" / "databases"
    folder.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(folder / "music.sqlite")
    conn.executescript("CREATE TABLE singer (name TEXT, age INTEGER, country TEXT);"
                       "INSERT INTO singer VALUES ('Ana', 30, 'PT'), ('Bo', 45, 'SE'), ('Cy', 45, 'PT');")
    conn.close()
    with (data_dir / "sql" / "exercises.jsonl").open("w") as out:
        for n, (question, query) in enumerate(exercises):
            out.write(json.dumps({"id": f"music-{n:010d}", "database": "music", "question": question, "query": query,
                                  "ordered": False, "features": sorted(features(query))}) + "\n")


BANK = [
    ("List every singer's name.", "SELECT name FROM singer"),
    ("Which singers are from PT?", "SELECT name FROM singer WHERE country = 'PT'"),
    ("How many singers are there?", "SELECT count(*) FROM singer"),
    ("How many singers per country?", "SELECT country, count(*) FROM singer GROUP BY country"),
    ("Countries with more than one singer?", "SELECT country FROM singer GROUP BY country HAVING count(*) > 1"),
]


def sql_extraction():
    return extraction(
        concepts=("selecting", "grouping"),
        problems=[
            {"source_ref": "PS2 #1", "prompt": "", "parts": [{"label": "(a)", "prompt": "List the names of students in year 3."}],
             "concepts": ["selecting"]},
            {"source_ref": "PS2 #2", "prompt": "", "parts": [{"label": "(b)", "prompt": "For each course, how many are enrolled?"}],
             "concepts": ["grouping"]},
        ],
    )


def sql_plan():
    return Plan.model_validate({"title": "Queries", "sections": [
        {"title": "Selecting", "goal": "Read rows.", "concepts": ["selecting"], "sql_features": ["selecting", "filtering"]},
        {"title": "Grouping", "goal": "Count by group.", "concepts": ["grouping"], "sql_features": ["aggregates", "grouping"]},
    ]})


def query(reference):
    return {"kind": "query", "reference": reference}


def section(source_ref, label, reference, body="```sql\nSELECT name FROM student;\n```"):
    return {"blocks": [
        {"type": "explanation", "body": body},
        {"type": "problem", "source_ref": source_ref, "parts": [{"label": label, "answer": query(reference)}]},
    ]}


def solved_queries(**queries):
    return {"solutions": [{"target": t, "value": None, "expression": None, "correct": None, "query": q}
                          for t, q in queries.items()]}


def sql_script(overrides=None):
    script = {
        ProblemsAndConcepts: [sql_extraction()],
        Plan: [sql_plan()],
        SectionDraft: [section("PS2 #1", "(a)", YEAR_3), section("PS2 #2", "(b)", PER_COURSE)],
        HintDraft: [hints_for("ps2-1/a"), hints_for("ps2-2/b")],
        HintJudgements: [all_fine, all_fine],
        HintReplacements: [],
        Solutions: [
            solved_queries(**{"ps2-1/a": "SELECT name FROM student WHERE year >= 3"}),
            solved_queries(**{"ps2-2/b": "SELECT course, count(student_id) FROM enrolled GROUP BY 1 ORDER BY 1"}),
        ],
    }
    script.update(overrides or {})
    return script


def create(client, database=("course.sql", COURSE)):
    files = [("problems.md", PROBLEMS, "problem_set", False)]
    if database:
        files.append((database[0], database[1], "database", False))
    return upload(client, files, subject="computer_science", domain="sql")


def generate(data_dir, lesson_id, fake, start_stage=1):
    pipeline.run(data_dir, lesson_id, "computer_science", start_stage, call=fake)


@pytest.fixture
def sql_lesson(started, data_dir):
    client, _, _ = started
    import_bank(data_dir, BANK)
    response = create(client)
    assert response.status_code == 201, response.text
    return client, response.json()["id"]


@pytest.fixture
def ready(sql_lesson, data_dir):
    client, lesson_id = sql_lesson
    fake = FakeModel(sql_script())
    generate(data_dir, lesson_id, fake)
    status = lesson_status(client, lesson_id)
    assert (status["status"], status["error"]) == ("ready", None)
    return client, lesson_id, Lesson.model_validate(status["lesson"]), fake


# Uploading


def test_a_course_database_is_kept_with_the_materials_but_not_read_as_material(sql_lesson, data_dir):
    client, lesson_id = sql_lesson
    kept = data_dir / "materials" / lesson_id / "databases" / "course.sqlite"
    assert kept.is_file()
    names = [m["filename"] for m in lesson_status(client, lesson_id)["materials"]]
    assert names == ["problems.md"]


@pytest.mark.parametrize(
    "subject, domain, files, message",
    [
        ("computer_science", "dsa", [("db.sql", COURSE, "database")], "Only a SQL lesson takes a database"),
        ("math", None, [("db.sql", COURSE, "database")], "Only a SQL lesson takes a database"),
        ("computer_science", "sql", [("a.sql", COURSE, "database"), ("b.sql", COURSE, "database")], "takes one database"),
        ("computer_science", "sql", [("db.sql", b"CREATE TABLE (", "database")], "db.sql failed"),
        ("computer_science", "sql", [("db.sql", b"ATTACH 'x' AS y;", "database")], "db.sql failed"),
        ("computer_science", "sql", [("db.csv", COURSE, "database")], "isn't a SQLite file"),
    ],
)
def test_a_database_upload_is_refused_with_a_reason(started, data_dir, subject, domain, files, message):
    client, _, runs = started
    all_files = [("problems.md", PROBLEMS, "problem_set", False)] + [(n, d, r, False) for n, d, r in files]
    response = upload(client, all_files, subject=subject, domain=domain)
    assert response.status_code == 422
    assert message in response.json()["detail"]
    assert runs == []


def test_a_sql_problem_set_isnt_read_as_a_leetcode_list(started):
    client, _, _ = started
    assert create(client).status_code == 201


# Generation


def test_a_sql_lesson_end_to_end(ready, data_dir):
    _, _, lesson, fake = ready
    assert lesson.domain == "sql"

    year_3 = lesson.find_block("ps2-1").parts[0]
    assert isinstance(year_3.answer, QueryAnswer)
    assert (year_3.answer.database, year_3.answer.reference, year_3.answer.ordered, year_3.answer.exercise) == (
        "course/course", YEAR_3, False, None)
    assert year_3.verified is True and year_3.hints
    per_course = lesson.find_block("ps2-2").parts[0].answer
    assert per_course.ordered is True
    assert lesson.find_block("ps2-2").parts[0].verified is True

    # Practice from the bank ends each section, using only what is taught by then.
    first, second = lesson.sections
    first_practice = [b for b in first.blocks if b.id.startswith(f"{first.id}-practice-")]
    second_practice = [b for b in second.blocks if b.id.startswith(f"{second.id}-practice-")]
    assert [b.prompt for b in first_practice] == ["List every singer's name.", "Which singers are from PT?"]
    # HAVING isn't taught, so that exercise waits.
    assert [b.prompt for b in second_practice] == ["How many singers are there?", "How many singers per country?"]
    assert all(b.answer.database == "bank/music" and b.answer.exercise for b in first_practice + second_practice)
    assert all(not b.hints and not b.verified for b in first_practice + second_practice)
    assert first.blocks[-len(first_practice):] == first_practice


def test_the_model_sees_the_course_database_and_the_sql_rules(ready):
    _, _, _, fake = ready
    material = fake.calls[ProblemsAndConcepts][0]["prompt"][0]["text"]
    assert "<course_database>" in material and "Table student (id, name, year), 3 rows" in material
    assert prompts.SQL_PLAN_RULES in fake.calls[Plan][0]["system"]
    assert all("course database `course`" in c["system"] for c in fake.calls[SectionDraft])
    assert all("LeetCode" not in c["system"] for c in fake.calls[SectionDraft])


def test_a_disagreeing_second_solve_leaves_the_part_unverified(sql_lesson, data_dir):
    client, lesson_id = sql_lesson
    wrong = solved_queries(**{"ps2-1/a": "SELECT name FROM student"})
    script = sql_script({Solutions: [wrong, sql_script()[Solutions][1]]})
    generate(data_dir, lesson_id, FakeModel(script))
    lesson = Lesson.model_validate(lesson_status(client, lesson_id)["lesson"])
    assert lesson.find_block("ps2-1").parts[0].verified is False


@pytest.mark.parametrize(
    "bad, feedback",
    [
        ("SELECT nope FROM student", "doesn't run: no such column: nope"),
        ("SELECT name FROM student WHERE year = 9", "returns no rows"),
        ("DELETE FROM student", "doesn't run"),
    ],
)
def test_a_reference_that_doesnt_run_or_returns_nothing_is_sent_back(sql_lesson, data_dir, bad, feedback):
    client, lesson_id = sql_lesson
    script = sql_script({SectionDraft: [section("PS2 #1", "(a)", bad), section("PS2 #1", "(a)", YEAR_3),
                                        section("PS2 #2", "(b)", PER_COURSE)]})
    fake = FakeModel(script)
    generate(data_dir, lesson_id, fake)
    assert lesson_status(client, lesson_id)["status"] == "ready"
    assert feedback in fake.calls[SectionDraft][1]["prompt"][-1]["text"]


def test_without_a_course_database_a_query_answer_is_sent_back_as_a_self_check(started, data_dir):
    client, _, _ = started
    lesson_id = create(client, database=None).json()["id"]
    self_check = {"kind": "self_check", "rubric": "Selects name where year is 3."}
    fixed = {"blocks": [{"type": "problem", "source_ref": "PS2 #1", "parts": [{"label": "(a)", "answer": self_check}]}]}
    fixed_two = {"blocks": [{"type": "problem", "source_ref": "PS2 #2", "parts": [{"label": "(b)", "answer": self_check}]}]}
    fake = FakeModel(sql_script({SectionDraft: [section("PS2 #1", "(a)", YEAR_3), fixed, fixed_two],
                                 Solutions: []}))
    generate(data_dir, lesson_id, fake)
    status = lesson_status(client, lesson_id)
    assert status["status"] == "ready", status["error"]
    assert "no course database" in fake.calls[SectionDraft][1]["prompt"][-1]["text"]
    assert "There is no course database" in fake.calls[SectionDraft][0]["system"]
    # With nothing imported in the bank either, there is no practice.
    assert not any(b.id.endswith("-practice-1") for s in Lesson.model_validate(status["lesson"]).sections for b in s.blocks)


def test_a_query_answer_outside_a_sql_lesson_is_sent_back(started, data_dir):
    client, _, _ = started
    from .test_pipeline import happy_script, run, section_two

    lesson_id = upload(client, [("ps.md", b"PS1 #1", "problem_set", False)]).json()["id"]
    sneaky = section_two()
    sneaky["blocks"][1]["parts"][0]["answer"] = query("SELECT 1")
    fake = FakeModel(happy_script({SectionDraft: [happy_script()[SectionDraft][0], sneaky, section_two()]}))
    run(data_dir, lesson_id, fake)
    assert lesson_status(client, lesson_id)["status"] == "ready"
    assert "only SQL lessons use" in fake.calls[SectionDraft][2]["prompt"][-1]["text"]


# Running and checking queries


def post(client, lesson_id, path, body):
    return client.post(f"/lessons/{lesson_id}/blocks/{path}", json=body, headers=AUTH)


def test_a_parts_tables_are_shown(ready):
    client, lesson_id, _, _ = ready
    tables = client.get(f"/lessons/{lesson_id}/blocks/ps2-1/tables", params={"part_id": "a"}, headers=AUTH).json()["tables"]
    assert [t["name"] for t in tables] == ["student", "enrolled"]
    assert tables[0]["rows"][0] == [1, "Ada", 2] and tables[0]["count"] == 3


def test_run_query_returns_the_result_or_the_error_without_an_attempt(ready, data_dir):
    client, lesson_id, _, _ = ready
    ran = post(client, lesson_id, "ps2-1/run-query", {"part_id": "a", "query": "SELECT name FROM student ORDER BY id"}).json()
    assert ran == {"columns": ["name"], "rows": [["Ada"], ["Grace"], ["Linus"]], "count": 3, "truncated": False, "error": None}
    failed = post(client, lesson_id, "ps2-1/run-query", {"part_id": "a", "query": "DROP TABLE student"}).json()
    assert failed["error"] == "Only queries that read the tables can run here."
    with connect(data_dir) as conn:
        assert progress.load(conn, lesson_id, "ps2-1", "a").attempts == 0


def test_checking_a_query_records_the_attempt_and_says_why_it_is_wrong(ready):
    client, lesson_id, _, _ = ready
    wrong = post(client, lesson_id, "ps2-1/check", {"part_id": "a", "response": "SELECT name FROM student"}).json()
    assert (wrong["correct"], wrong["reason"]) == (False, "Expected 2 rows, got 3.")
    assert wrong["result"]["rows"] == [["Ada"], ["Grace"], ["Linus"]]
    assert wrong["progress"]["attempts"] == 1
    right = post(client, lesson_id, "ps2-1/check", {"part_id": "a", "response": "SELECT name FROM student WHERE year > 2"}).json()
    assert (right["correct"], right["reason"], right["progress"]["status"]) == (True, None, "correct")


def test_order_matters_only_where_the_reference_orders(ready):
    client, lesson_id, _, _ = ready
    reversed_order = "SELECT course, count(*) FROM enrolled GROUP BY course ORDER BY course DESC"
    result = post(client, lesson_id, "ps2-2/check", {"part_id": "b", "response": reversed_order}).json()
    assert result["reason"] == "The right rows, in the wrong order."


@pytest.mark.parametrize("response", ["SELEC name FROM student", "DELETE FROM student", 42])
def test_a_query_that_cant_run_is_refused_and_isnt_an_attempt(ready, data_dir, response):
    client, lesson_id, _, _ = ready
    assert post(client, lesson_id, "ps2-1/check", {"part_id": "a", "response": response}).status_code == 422
    with connect(data_dir) as conn:
        assert progress.load(conn, lesson_id, "ps2-1", "a").attempts == 0


def test_a_practice_checkpoint_is_checked_against_its_bank_database(ready):
    client, lesson_id, lesson, _ = ready
    checkpoint = next(b for b in lesson.sections[0].blocks if b.id.endswith("-practice-2"))
    right = post(client, lesson_id, f"{checkpoint.id}/check", {"response": "SELECT name FROM singer WHERE country = 'PT'"})
    assert right.json()["correct"] is True


def test_a_missing_bank_database_says_so(ready, data_dir):
    client, lesson_id, lesson, _ = ready
    (data_dir / "sql" / "databases" / "music.sqlite").unlink()
    checkpoint = next(b for b in lesson.sections[0].blocks if b.id.endswith("-practice-1"))
    response = post(client, lesson_id, f"{checkpoint.id}/check", {"response": "SELECT 1"})
    assert response.status_code == 409 and "isn't available" in response.json()["detail"]


def test_query_routes_refuse_a_part_that_isnt_a_query(started, data_dir):
    client, _, _ = started
    from .test_pipeline import happy_script, run

    lesson_id = upload(client, [("ps.md", b"PS1 #1", "problem_set", False)]).json()["id"]
    run(data_dir, lesson_id, FakeModel(happy_script()))
    response = client.get(f"/lessons/{lesson_id}/blocks/ps1-1/tables", params={"part_id": "a"}, headers=AUTH)
    assert response.status_code == 422


def test_a_rerun_keeps_a_query_parts_state_and_query(ready, data_dir):
    client, lesson_id, _, _ = ready
    post(client, lesson_id, "ps2-1/check", {"part_id": "a", "response": "SELECT name FROM student WHERE year = 3"})
    generate(data_dir, lesson_id, FakeModel({k: v for k, v in sql_script().items() if k not in (ProblemsAndConcepts, Plan)}),
             start_stage=4)
    with connect(data_dir) as conn:
        record = progress.load(conn, lesson_id, "ps2-1", "a")
    assert (record.status, record.last_response) == ("correct", "SELECT name FROM student WHERE year = 3")
