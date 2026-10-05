import json
from collections import defaultdict

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from kedami_server import db
from kedami_server.app import create_app
from kedami_server.config import Settings
from kedami_server.generation import pipeline
from kedami_server.generation.schemas import (
    ProblemsAndConcepts,
    HintDraft,
    HintJudgements,
    HintReplacements,
    Plan,
    SectionDraft,
    Solutions,
)
from kedami_server.lesson import Lesson
from kedami_server.model import ModelError

from .conftest import AUTH, upload
from .factories import extraction, plan

NUMERIC = {"kind": "numeric", "value": 8.66, "rel_tolerance": 0.01, "unit": "m/s"}


class FakeModel:
    """Replies from a script, per output type. A reply may be a model, a dict, or an exception."""

    def __init__(self, script: dict):
        self.script = {kind: list(replies) for kind, replies in script.items()}
        self.calls = defaultdict(list)

    def __call__(self, role, *, system, prompt, output):
        self.calls[output].append({"role": role, "system": system, "prompt": prompt})
        reply = self.script[output].pop(0)
        if isinstance(reply, Exception):
            raise reply
        if callable(reply):
            reply = reply(prompt)
        return reply if isinstance(reply, BaseModel) else output.model_validate(reply)


def section_one():
    return {"blocks": [
        {"type": "explanation", "body": "Components."},
        {"type": "checkpoint", "prompt": "A $20$ m/s throw at $60°$: find $v_x$.", "answer": {**NUMERIC, "value": 10}},
        {"type": "problem", "source_ref": "PS1 #1", "parts": [{"label": "(a)", "answer": {**NUMERIC}},
                                                             {"label": "(b)", "answer": {**NUMERIC, "value": 5}}]},
    ]}


def section_two():
    return {"blocks": [
        {"type": "explanation", "body": "Range."},
        {"type": "problem", "source_ref": "PS1 #2", "parts": [{"label": "2", "answer": {**NUMERIC, "value": 9.2}}]},
    ]}


def hints_for(*keys):
    return {"items": [{"target": k, "hints": ["Think about components.", "Use cosine."]} for k in keys]}


def all_fine(prompt):
    data = json.loads(prompt[0]["text"].split("\n\n", 1)[1])
    return {"results": [{"target": d["target"], "index": d["index"], "gives_away": False} for d in data]}


def solved(**values):
    return {"solutions": [{"target": t, "value": v, "expression": None, "correct": None} for t, v in values.items()]}


SECTION_ONE_SOLVED = solved(**{"vectors-block-2": 10.0, "ps1-1/a": 8.66, "ps1-1/b": 6.0})
SECTION_TWO_SOLVED = solved(**{"ps1-2/2": 9.2})


def happy_script(overrides=None):
    script = {
        ProblemsAndConcepts: [extraction()],
        Plan: [plan(("Vectors", ["vectors"]), ("Flight", ["gravity", "range"]))],
        SectionDraft: [section_one(), section_two()],
        HintDraft: [hints_for("vectors-block-2", "ps1-1/a", "ps1-1/b"), hints_for("ps1-2/2")],
        HintJudgements: [all_fine, all_fine],
        HintReplacements: [],
        Solutions: [SECTION_ONE_SOLVED, SECTION_TWO_SOLVED],
    }
    script.update(overrides or {})
    return script


def run(data_dir, lesson_id, fake, start_stage=1):
    pipeline.run(data_dir, lesson_id, "physics", start_stage, call=fake)


def lesson_status(client, lesson_id):
    return client.get(f"/lessons/{lesson_id}", headers=AUTH).json()


# Creating a lesson


def test_new_lesson_saves_materials_and_starts_generation(started, data_dir):
    client, create, runs = started
    response = create()
    assert response.status_code == 201
    lesson_id = response.json()["id"]
    assert runs == [(data_dir, lesson_id, "physics", 1)]
    assert (data_dir / "materials" / lesson_id / "problem-set.md").read_text() == "PS1\n1. A ball..."
    assert (data_dir / "materials" / lesson_id / "reference.md").read_text() == "Notes on projectiles."
    status = lesson_status(client, lesson_id)
    assert (status["lesson"], status["status"], status["current_stage"], status["error"]) == (None, "generating", None, None)
    assert [(m["filename"], m["role"], m["force_transcription"]) for m in status["materials"]] == [
        ("problem-set.md", "problem_set", False),
        ("reference.md", "reference", False),
    ]
    assert status["rerun_stages"] == [1]
    assert client.get("/lessons", headers=AUTH).json()["lessons"][-1]["title"] == "New lesson"


# Running the pipeline


def test_happy_path_produces_a_ready_lesson(started, data_dir):
    client, create, _ = started
    lesson_id = create().json()["id"]
    fake = FakeModel(happy_script())
    run(data_dir, lesson_id, fake)

    status = lesson_status(client, lesson_id)
    assert status["status"] == "ready" and status["error"] is None
    lesson = Lesson.model_validate(status["lesson"])
    assert lesson.title == "Projectiles"
    assert [s.id for s in lesson.sections] == ["vectors", "flight"]
    assert lesson.source_files == ["problem-set.md", "reference.md"]
    problem = lesson.find_block("ps1-1")
    assert problem.prompt == "A ball is thrown at $10$ m/s."
    assert [p.hints for p in problem.parts] == [["Think about components.", "Use cosine."]] * 2
    # The second solve agreed on (a) but not on (b).
    assert [p.verified for p in problem.parts] == [True, False]
    assert lesson.find_block("vectors-block-2").verified is True
    assert lesson.find_block("ps1-2").parts[0].verified is True
    assert lesson.find_block("vectors-block-2").hints == ["Think about components.", "Use cosine."]

    summary = client.get("/lessons", headers=AUTH).json()["lessons"][-1]
    assert (summary["title"], summary["problems_total"]) == ("Projectiles", 2)

    work = data_dir / "work" / lesson_id
    assert sorted(p.name for p in work.iterdir()) == [
        "extraction.json", "normalized", "outline.json", "pages.json", "plan.json",
        "section-1.json", "section-2.json", "verification-1.json", "verification-2.json",
    ]
    pages = json.loads((work / "pages.json").read_text())
    assert [(p["file"], p["route"], p["reason"]) for p in pages] == [
        ("problem-set.md", "keep", "text file"), ("reference.md", "keep", "text file"),
    ]
    assert (work / "normalized" / "problem-set.md").read_text() == "[problem-set.md, page 1]\n\nPS1\n1. A ball..."
    records = json.loads((work / "verification-1.json").read_text())
    assert [(r["target"], r["verified"]) for r in records] == [("vectors-block-2", True), ("ps1-1/a", True), ("ps1-1/b", False)]
    assert json.loads((work / "outline.json").read_text())["sections"][1]["problems"] == ["PS1 #2"]


def test_requests_use_the_generate_role_and_open_with_the_cached_material(started, data_dir):
    _, create, _ = started
    lesson_id = create().json()["id"]
    fake = FakeModel(happy_script())
    run(data_dir, lesson_id, fake)
    for output in (ProblemsAndConcepts, Plan, SectionDraft, HintDraft):
        for call in fake.calls[output]:
            assert call["role"] == "generate"
            first = call["prompt"][0]
            assert "PS1\n1. A ball..." in first["text"] and "Notes on projectiles." in first["text"]
            assert first["cache_control"] == {"type": "ephemeral"}
    assert all(call["role"] == "small_check" for call in fake.calls[HintJudgements])
    assert [call["role"] for call in fake.calls[Solutions]] == ["second_solve", "second_solve"]


@pytest.mark.parametrize("subject, has_rules", [("general", True), ("physics", False), ("math", False)])
def test_only_general_lessons_get_the_general_section_rules(started, data_dir, subject, has_rules):
    client, create, _ = started
    lesson_id = create(subject=subject).json()["id"]
    fake = FakeModel(happy_script())
    pipeline.run(data_dir, lesson_id, subject, 1, call=fake)
    assert lesson_status(client, lesson_id)["lesson"]["subject"] == subject
    assert all(("language of the course material" in c["system"]) == has_rules for c in fake.calls[SectionDraft])


def test_rejected_section_is_retried_alone_with_the_reason(started, data_dir):
    _, create, _ = started
    lesson_id = create().json()["id"]
    missing_problem = {"blocks": [{"type": "explanation", "body": "Components."}]}
    fake = FakeModel(happy_script({SectionDraft: [missing_problem, section_one(), section_two()]}))
    run(data_dir, lesson_id, fake)
    prompts = [c["prompt"][-1]["text"] for c in fake.calls[SectionDraft]]
    assert len(prompts) == 3
    assert "missing from the section: PS1 #1" in prompts[1]
    assert "rejected" not in prompts[2]
    assert len(fake.calls[ProblemsAndConcepts]) == 1 and len(fake.calls[Plan]) == 1


def test_plan_breaking_the_sequencing_rules_is_retried(started, data_dir):
    _, create, _ = started
    lesson_id = create().json()["id"]
    incomplete = plan(("Vectors", ["vectors"]))
    fake = FakeModel(happy_script({Plan: [incomplete, plan(("Vectors", ["vectors"]), ("Flight", ["gravity", "range"]))]}))
    run(data_dir, lesson_id, fake)
    assert "never introduced: gravity, range" in fake.calls[Plan][1]["prompt"][-1]["text"]


def test_stage_failing_every_attempt_fails_the_lesson(started, data_dir):
    client, create, _ = started
    lesson_id = create().json()["id"]
    bad = {"concepts": [], "problems": []}
    fake = FakeModel(happy_script({ProblemsAndConcepts: [bad, bad, bad]}))
    run(data_dir, lesson_id, fake)
    status = lesson_status(client, lesson_id)
    assert status["status"] == "failed"
    assert status["error"].startswith("Extraction failed after 3 attempts")
    assert status["current_stage"] == 2
    assert not (data_dir / "lessons" / f"{lesson_id}.json").exists()


def test_model_error_fails_the_lesson_without_retrying(started, data_dir):
    client, create, _ = started
    lesson_id = create().json()["id"]
    fake = FakeModel(happy_script({Plan: [ModelError("The Anthropic API key is missing or invalid.")]}))
    run(data_dir, lesson_id, fake)
    status = lesson_status(client, lesson_id)
    assert (status["status"], status["error"], status["current_stage"]) == ("failed", "The Anthropic API key is missing or invalid.", 3)
    assert len(fake.calls[Plan]) == 1


def test_unexpected_errors_still_fail_the_lesson(started, data_dir):
    client, create, _ = started
    lesson_id = create().json()["id"]
    fake = FakeModel(happy_script({ProblemsAndConcepts: [RuntimeError("boom")]}))
    run(data_dir, lesson_id, fake)
    assert lesson_status(client, lesson_id)["error"] == "Unexpected error: boom"


def test_interrupted_generation_is_marked_failed(started, data_dir):
    client, create, _ = started
    lesson_id = create().json()["id"]
    from kedami_server import library

    with db.connect(data_dir) as conn:
        library.fail_interrupted(conn, lambda _id: False)
    status = lesson_status(client, lesson_id)
    assert status["status"] == "failed" and "interrupted" in status["error"]


def test_verification_that_keeps_failing_leaves_the_section_unverified(started, data_dir):
    client, create, _ = started
    lesson_id = create().json()["id"]
    malformed = {"solutions": "not a list"}
    fake = FakeModel(happy_script({Solutions: [malformed, malformed, malformed, SECTION_TWO_SOLVED]}))
    run(data_dir, lesson_id, fake)
    status = lesson_status(client, lesson_id)
    assert status["status"] == "ready"
    lesson = Lesson.model_validate(status["lesson"])
    assert not any(p.verified for p in lesson.find_block("ps1-1").parts)
    assert lesson.find_block("ps1-2").parts[0].verified is True
    record = json.loads((data_dir / "work" / lesson_id / "verification-1.json").read_text())
    assert record["error"].startswith("Verification for section 1 failed after 3 attempts")


def test_api_error_during_verification_fails_the_lesson(started, data_dir):
    client, create, _ = started
    lesson_id = create().json()["id"]
    fake = FakeModel(happy_script({Solutions: [ModelError("The model declined this request.")]}))
    run(data_dir, lesson_id, fake)
    status = lesson_status(client, lesson_id)
    assert (status["status"], status["error"]) == ("failed", "The model declined this request.")
