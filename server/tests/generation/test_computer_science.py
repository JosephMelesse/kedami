import json

import pytest
from pydantic import ValidationError

from kedami_server.generation.leetcode import ConceptMapError, ListedProblem, build_extraction
from kedami_server.generation.schemas import (
    ConceptMap,
    HintDraft,
    HintJudgements,
    Plan,
    SectionDraft,
    Solutions,
    TextChecks,
)
from kedami_server.lesson import CheckpointBlock, ExternalAnswer, Lesson

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


# The extraction built from the list


def test_extraction_lists_the_problems_with_external_answers():
    extraction = build_extraction(LISTED, GOOD_MAP)
    assert [(p.source_ref, p.prompt, [(x.label, x.prompt) for x in p.parts], p.concepts) for p in extraction.problems] == [
        ("LeetCode #1", "", [("1", "Complete LeetCode #1: Two Sum.")], ["hash-maps"]),
        ("LeetCode #15", "", [("15", "Complete LeetCode #15: 3Sum.")], ["hash-maps", "two-pointers"]),
    ]
    two_sum = extraction.externals["leetcode-1"]
    assert (two_sum.number, two_sum.title, two_sum.slug, two_sum.url) == (1, "Two Sum", "two-sum", "https://leetcode.com/problems/two-sum/")


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


def test_checkpoints_cannot_be_external():
    external = {"kind": "external", "platform": "leetcode", "number": 1, "title": "Two Sum", "slug": "two-sum"}
    with pytest.raises(ValidationError, match="answered in the lesson"):
        CheckpointBlock.model_validate({"type": "checkpoint", "id": "c", "prompt": "Q", "answer": external})


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
    assert all("LeetCode problems the student solves on LeetCode" in c["system"] for c in fake.calls[SectionDraft])
    solved = json.loads(fake.calls[Solutions][0]["prompt"][-1]["text"].split("\n\n", 1)[1])
    assert [s["target"] for s in solved] == ["hash-maps-block-2"]
    assert len(fake.calls[Solutions]) == 1  # the second section has nothing to verify


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
