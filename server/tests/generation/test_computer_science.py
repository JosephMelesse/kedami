import json

import pytest
from pydantic import ValidationError

from kedami_server import progress
from kedami_server.db import connect
from kedami_server.generation.leetcode import (
    ConceptMapError,
    ListedProblem,
    ProblemListError,
    build_extraction,
    find_in_dataset,
)
from kedami_server.generation.schemas import (
    ConceptMap,
    Extraction,
    HintDraft,
    HintJudgements,
    Plan,
    SectionDraft,
    Solutions,
    TextChecks,
)
from kedami_server.lesson import CheckpointBlock, CodeAnswer, ExternalAnswer, Lesson

from .conftest import AUTH, upload
from .files import text_pdf
from .test_pipeline import FakeModel, lesson_status, run

LIST = b"# Week 3: hashing and pointers\n\n1. Two Sum\n15. 3Sum\n"
LISTED = [ListedProblem(1, "Two Sum"), ListedProblem(15, "3Sum")]


def concept_map(*problems, concepts=("hash-maps", "two-pointers")):
    return ConceptMap.model_validate({
        "concepts": [{"id": c, "name": c, "summary": f"About {c}."} for c in concepts],
        "problems": [{"number": n, "concepts": list(cs)} for n, cs in problems],
    })


GOOD_MAP = concept_map((1, ["hash-maps"]), (15, ["hash-maps", "two-pointers"]))

TWO_SUM_DESCRIPTION = "Given an array of integers nums and an integer target, return indices...\n\nExample 1:"


def dataset_entry(number=1, slug="two-sum", **overrides) -> dict:
    """A problem as the import writes it to leetcode.jsonl: number first, then the rest."""
    return {
        "number": number,
        "slug": slug,
        "difficulty": "Easy",
        "description": TWO_SUM_DESCRIPTION,
        "starter_code": "class Solution:\n    def twoSum(self, nums: List[int], target: int) -> List[int]:\n        ",
        "method": "twoSum",
        "tests": [{"args": "nums = [3, 3], target = 6", "expected": "[0, 1]", "compare": "equal"}],
    } | overrides


def import_dataset(data_dir, *entries) -> None:
    (data_dir / "leetcode.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entries))


# The extraction built from the list


def test_without_the_dataset_every_problem_is_solved_on_leetcode():
    extraction = build_extraction(LISTED, GOOD_MAP)
    assert [(p.source_ref, p.prompt, [(x.label, x.prompt) for x in p.parts], p.concepts) for p in extraction.problems] == [
        ("LeetCode #1", "", [("1", "Complete LeetCode #1: Two Sum.")], ["hash-maps"]),
        ("LeetCode #15", "", [("15", "Complete LeetCode #15: 3Sum.")], ["hash-maps", "two-pointers"]),
    ]
    two_sum = extraction.answers["leetcode-1"]
    assert isinstance(two_sum, ExternalAnswer)
    assert (two_sum.number, two_sum.title, two_sum.slug, two_sum.url) == (1, "Two Sum", "two-sum", "https://leetcode.com/problems/two-sum/")


# Problems found in the imported dataset


def test_a_problem_in_the_dataset_becomes_a_code_answer(data_dir):
    import_dataset(data_dir, dataset_entry(), dataset_entry(number=2, slug="add-two-numbers"))
    found = find_in_dataset(data_dir, LISTED)
    assert list(found) == [1]
    answer = found[1].answer
    assert (answer.kind, answer.number, answer.title, answer.slug, answer.difficulty, answer.method) == (
        "code", 1, "Two Sum", "two-sum", "Easy", "twoSum"
    )
    assert [t.model_dump() for t in answer.tests] == [{"args": "nums = [3, 3], target = 6", "expected": "[0, 1]", "compare": "equal"}]
    assert found[1].description == TWO_SUM_DESCRIPTION


def test_code_problems_take_their_description_and_the_rest_stay_on_leetcode(data_dir):
    import_dataset(data_dir, dataset_entry())
    extraction = build_extraction(LISTED, GOOD_MAP, find_in_dataset(data_dir, LISTED))
    assert [p.parts[0].prompt for p in extraction.problems] == [TWO_SUM_DESCRIPTION, "Complete LeetCode #15: 3Sum."]
    assert isinstance(extraction.answers["leetcode-1"], CodeAnswer)
    assert isinstance(extraction.answers["leetcode-15"], ExternalAnswer)


def test_a_title_that_names_a_different_problem_is_refused(data_dir):
    import_dataset(data_dir, dataset_entry(), dataset_entry(number=15, slug="3sum"))
    listed = [ListedProblem(1, "Add Two Numbers"), ListedProblem(15, "3Sum")]
    with pytest.raises(ProblemListError, match="#1 is 'two-sum', not 'Add Two Numbers'"):
        find_in_dataset(data_dir, listed)


@pytest.mark.parametrize(
    "damage",
    [
        {"difficulty": "Impossible"},
        {"method": "two sum"},
        {"tests": []},
        {"tests": [{"args": "x = 1"}]},
        {"starter_code": ""},
        {"description": "  "},
        {"description": None},
    ],
)
def test_a_damaged_dataset_entry_leaves_the_problem_on_leetcode(data_dir, damage):
    import_dataset(data_dir, dataset_entry(**damage))
    assert find_in_dataset(data_dir, LISTED) == {}


def test_a_dataset_entry_missing_a_field_leaves_the_problem_on_leetcode(data_dir):
    entry = dataset_entry()
    del entry["tests"]
    import_dataset(data_dir, entry)
    assert find_in_dataset(data_dir, LISTED) == {}


def test_extraction_saved_before_the_rename_still_loads():
    external = {"kind": "external", "platform": "leetcode", "number": 1, "title": "Two Sum", "slug": "two-sum"}
    saved = build_extraction(LISTED[:1], concept_map((1, ["hash-maps"]))).model_dump()
    saved["externals"] = {"leetcode-1": external}
    del saved["answers"]
    assert isinstance(Extraction.model_validate(saved).answers["leetcode-1"], ExternalAnswer)


@pytest.mark.parametrize(
    "mapped, message",
    [
        ([(1, ["hash-maps"])], "missing: 15"),
        ([(1, []), (15, []), (2, [])], "aren't in the list: 2"),
        ([(1, []), (1, []), (15, [])], "more than once: 1"),
    ],
)
def test_concept_map_must_cover_every_listed_problem_once(mapped, message):
    with pytest.raises(ConceptMapError, match=message):
        build_extraction(LISTED, concept_map(*mapped))


def test_concept_map_rejects_unknown_concepts():
    with pytest.raises(ValidationError, match="unknown concepts: graphs"):
        concept_map((1, ["graphs"]))


@pytest.mark.parametrize(
    "answer",
    [
        {"kind": "external", "platform": "leetcode", "number": 1, "title": "Two Sum", "slug": "two-sum"},
        {"kind": "code", "platform": "leetcode", "number": 1, "title": "Two Sum", "slug": "two-sum", "difficulty": "Easy",
         "method": "twoSum", "starter_code": "class Solution: ...",
         "tests": [{"args": "", "expected": "1", "compare": "equal"}]},
    ],
)
def test_checkpoints_cannot_be_leetcode_problems(answer):
    with pytest.raises(ValidationError, match="homework only"):
        CheckpointBlock.model_validate({"type": "checkpoint", "id": "c", "prompt": "Q", "answer": answer})


# A whole computer science lesson


def cs_script(overrides=None):
    plan = Plan.model_validate({"title": "Hashing", "sections": [
        {"title": "Hash maps", "goal": "Look things up in O(1).", "concepts": ["hash-maps"], "simulation": None},
        {"title": "Two pointers", "goal": "Scan from both ends.", "concepts": ["two-pointers"], "simulation": None},
    ]})
    null = {k: None for k in ("body", "prompt", "steps", "functions", "parameters", "x_domain", "y_domain", "svg",
                              "caption", "answer", "source_ref", "parts")}
    complexity = {**null, "type": "checkpoint", "prompt": "Lookup time in a dict?", "answer": {
        "kind": "choice", "options": ["O(1)", "O(n)"], "correct": [0], "value": None, "rel_tolerance": None,
        "unit": None, "expression": None, "rubric": None}}
    section_one = {"blocks": [
        {**null, "type": "explanation", "body": "```python\nseen = {}\n```"},
        complexity,
        {**null, "type": "problem", "source_ref": "LeetCode #1", "parts": []},
    ]}
    section_two = {"blocks": [{**null, "type": "problem", "source_ref": "LeetCode #15", "parts": []}]}

    def hints(prompt):
        targets = json.loads(prompt[-1]["text"].split("\n\n", 1)[1])
        return {"items": [{"target": t["target"], "hints": ["Think about what you've seen so far."]} for t in targets]}

    def fine(prompt):
        data = json.loads(prompt[0]["text"].split("\n\n", 1)[1])
        return {"results": [{"target": d["target"], "index": d["index"], "gives_away": False} for d in data]}

    script = {
        ConceptMap: [GOOD_MAP],
        Plan: [plan],
        SectionDraft: [section_one, section_two],
        HintDraft: [hints, hints],
        HintJudgements: [fine, fine],
        Solutions: [{"solutions": [{"target": "hash-maps-block-2", "value": None, "expression": None, "correct": [0]}]}],
    }
    script.update(overrides or {})
    return script


@pytest.fixture
def cs_lesson(started, data_dir):
    client, _, _ = started
    lesson_id = upload(client, [("problems.md", LIST, "problem_set", False)], subject="computer_science").json()["id"]
    return client, lesson_id


def test_cs_lesson_end_to_end(cs_lesson, data_dir):
    client, lesson_id = cs_lesson
    fake = FakeModel(cs_script())
    pipeline_run(data_dir, lesson_id, fake)
    status = lesson_status(client, lesson_id)
    assert (status["status"], status["error"]) == ("ready", None)
    lesson = Lesson.model_validate(status["lesson"])
    assert lesson.subject == "computer_science"

    two_sum = lesson.find_block("leetcode-1").parts[0]
    assert two_sum.prompt == "Complete LeetCode #1: Two Sum."
    assert isinstance(two_sum.answer, ExternalAnswer) and two_sum.answer.slug == "two-sum"
    assert two_sum.hints == ["Think about what you've seen so far."] and two_sum.verified is False
    assert lesson.find_block("leetcode-15").parts[0].answer.slug == "3sum"
    assert lesson.find_block("hash-maps-block-2").verified is True

    sent_problems = json.loads(fake.calls[ConceptMap][0]["prompt"][-1]["text"].split("\n\n", 1)[1])
    assert sent_problems == [{"number": 1, "title": "Two Sum"}, {"number": 15, "title": "3Sum"}]
    assert all("solves in a code editor or on LeetCode" in c["system"] for c in fake.calls[SectionDraft])
    solved = json.loads(fake.calls[Solutions][0]["prompt"][-1]["text"].split("\n\n", 1)[1])
    assert [s["target"] for s in solved] == ["hash-maps-block-2"]
    assert len(fake.calls[Solutions]) == 1  # the second section has nothing to verify


def test_cs_lesson_with_the_dataset_end_to_end(started, data_dir):
    client, _, _ = started
    import_dataset(data_dir, dataset_entry())
    lesson_id = upload(client, [("problems.md", LIST, "problem_set", False)], subject="computer_science").json()["id"]
    fake = FakeModel(cs_script())
    pipeline_run(data_dir, lesson_id, fake)
    status = lesson_status(client, lesson_id)
    assert (status["status"], status["error"]) == ("ready", None)
    lesson = Lesson.model_validate(status["lesson"])

    two_sum = lesson.find_block("leetcode-1").parts[0]
    assert two_sum.prompt == TWO_SUM_DESCRIPTION
    assert isinstance(two_sum.answer, CodeAnswer) and two_sum.answer.tests[0].expected == "[0, 1]"
    assert two_sum.hints == ["Think about what you've seen so far."] and two_sum.verified is False
    assert isinstance(lesson.find_block("leetcode-15").parts[0].answer, ExternalAnswer)

    # The concept map sees the description; hints see it too, but never the tests or starter code.
    sent = json.loads(fake.calls[ConceptMap][0]["prompt"][-1]["text"].split("\n\n", 1)[1])
    assert sent == [{"number": 1, "title": "Two Sum", "description": TWO_SUM_DESCRIPTION}, {"number": 15, "title": "3Sum"}]
    hinted = json.loads(fake.calls[HintDraft][0]["prompt"][-1]["text"].split("\n\n", 1)[1])
    code_target = next(h for h in hinted if h["target"] == "leetcode-1/1")
    assert TWO_SUM_DESCRIPTION in code_target["question"]
    assert set(code_target["answer"]) == {"kind", "platform", "number", "title", "slug", "difficulty", "method"}

    check = client.post(f"/lessons/{lesson_id}/blocks/leetcode-1/check", json={"part_id": "1", "response": "x"}, headers=AUTH)
    assert check.status_code == 422 and "workspace" in check.json()["detail"]


def test_a_wrong_title_is_refused_at_upload_once_the_dataset_is_imported(started, data_dir):
    client, _, runs = started
    import_dataset(data_dir, dataset_entry())
    response = upload(client, [("problems.md", b"1. Add Two Numbers\n", "problem_set", False)], subject="computer_science")
    assert response.status_code == 422
    assert "#1 is 'two-sum', not 'Add Two Numbers'" in response.json()["detail"]
    assert runs == []


def test_a_rerun_keeps_a_code_parts_state_and_code(started, data_dir):
    client, _, _ = started
    import_dataset(data_dir, dataset_entry())
    lesson_id = upload(client, [("problems.md", LIST, "problem_set", False)], subject="computer_science").json()["id"]
    pipeline_run(data_dir, lesson_id, FakeModel(cs_script()))
    code = "class Solution:\n    def twoSum(self, nums, target):\n        return [0, 1]\n"
    with connect(data_dir) as conn:
        progress.save(conn, lesson_id, progress.Record(
            block_id="leetcode-1", part_id="1", status=progress.CORRECT, last_response=code, attempts=2))
    rerun = FakeModel({k: v for k, v in cs_script().items() if k is not ConceptMap})
    from kedami_server.generation import pipeline

    pipeline.run(data_dir, lesson_id, "computer_science", start_stage=3, call=rerun)
    assert lesson_status(client, lesson_id)["status"] == "ready"
    with connect(data_dir) as conn:
        record = progress.load(conn, lesson_id, "leetcode-1", "1")
    assert (record.status, record.last_response, record.attempts) == (progress.CORRECT, code, 2)


def test_concept_map_missing_a_problem_is_retried(cs_lesson, data_dir):
    client, lesson_id = cs_lesson
    fake = FakeModel(cs_script({ConceptMap: [concept_map((1, ["hash-maps"])), GOOD_MAP]}))
    pipeline_run(data_dir, lesson_id, fake)
    assert lesson_status(client, lesson_id)["status"] == "ready"
    assert "problems missing: 15" in fake.calls[ConceptMap][1]["prompt"][-1]["text"]


def test_external_parts_can_only_be_marked_done(cs_lesson, data_dir):
    client, lesson_id = cs_lesson
    pipeline_run(data_dir, lesson_id, FakeModel(cs_script()))
    base = f"/lessons/{lesson_id}/blocks/leetcode-1"
    check = client.post(f"{base}/check", json={"part_id": "1", "response": "done"}, headers=AUTH)
    assert check.status_code == 422 and "Mark it done" in check.json()["detail"]
    marked = client.post(f"{base}/mark-done", json={"part_id": "1", "done": True}, headers=AUTH).json()
    assert marked["progress"]["status"] == "marked_done"


def test_bad_text_list_is_refused_at_upload(started, data_dir):
    client, _, runs = started
    response = upload(client, [("problems.md", b"1. Two Sum\nsolve by Friday\n", "problem_set", False)],
                      subject="computer_science")
    assert response.status_code == 422
    assert "line 2 isn't a problem number and title" in response.json()["detail"]
    assert runs == [] and not (data_dir / "materials").exists()


def test_math_lessons_skip_the_list_check(started):
    client, _, _ = started
    files = [("ps.md", b"Find x such that 2x = 4.", "problem_set", False)]
    assert upload(client, files, subject="math").status_code == 201


def test_list_in_a_pdf_is_read_after_stage_one(started, data_dir):
    client, _, _ = started
    pdf = text_pdf("1. Two Sum and some more words so the text layer counts", "Please finish these before the Friday lecture, thanks")
    lesson_id = upload(client, [("problems.pdf", pdf, "problem_set", False)], subject="computer_science").json()["id"]
    fake = FakeModel({TextChecks: [{"pages": [{"page": 1, "clean": True}, {"page": 2, "clean": True}]}]})
    pipeline_run(data_dir, lesson_id, fake)
    status = lesson_status(client, lesson_id)
    assert status["status"] == "failed"
    assert "isn't a problem number and title" in status["error"]


def pipeline_run(data_dir, lesson_id, fake):
    from kedami_server.generation import pipeline

    pipeline.run(data_dir, lesson_id, "computer_science", call=fake)


# Domains


def test_a_computer_science_lesson_saved_without_a_domain_reads_as_dsa(cs_lesson, data_dir):
    lesson = Lesson.model_validate({"schema_version": 1, "id": "old", "title": "T", "subject": "computer_science",
                                    "source_files": [], "sections": [{"id": "s", "title": "S", "goal": "G", "blocks": []}]})
    assert lesson.domain == "dsa"


@pytest.mark.parametrize("subject, domain", [("math", "dsa"), ("computer_science", "sql")])
def test_only_computer_science_has_a_domain_and_only_known_ones(subject, domain):
    with pytest.raises(ValidationError):
        Lesson.model_validate({"schema_version": 1, "id": "x", "title": "T", "subject": subject, "domain": domain,
                               "source_files": [], "sections": [{"id": "s", "title": "S", "goal": "G", "blocks": []}]})


@pytest.mark.parametrize(
    "subject, domain",
    [("computer_science", None), ("math", "dsa"), ("computer_science", "sql")],
)
def test_an_upload_needs_a_domain_exactly_for_computer_science(started, subject, domain):
    client, _, runs = started
    data = {"subject": subject, "roles": ["problem_set"], "force": ["false"]} | ({"domain": domain} if domain else {})
    response = client.post("/lessons", data=data, files=[("files", ("problems.md", LIST, "text/markdown"))], headers=AUTH)
    assert response.status_code == 422
    assert runs == []


def test_a_dsa_lesson_keeps_its_domain_in_the_lesson_and_the_library(cs_lesson, data_dir):
    client, lesson_id = cs_lesson
    assert next(s for s in client.get("/lessons", headers=AUTH).json()["lessons"] if s["id"] == lesson_id)["domain"] == "dsa"
    pipeline_run(data_dir, lesson_id, FakeModel(cs_script()))
    assert lesson_status(client, lesson_id)["lesson"]["domain"] == "dsa"


def test_a_lesson_indexed_before_domains_existed_is_listed_as_dsa(cs_lesson, data_dir):
    client, lesson_id = cs_lesson
    with connect(data_dir) as conn:
        conn.execute("UPDATE lessons SET domain = NULL WHERE id = ?", (lesson_id,))
    assert next(s for s in client.get("/lessons", headers=AUTH).json()["lessons"] if s["id"] == lesson_id)["domain"] == "dsa"
