"""The draft lesson an agent builds across many tool calls. See architecture/agent-mode.md, Building a lesson."""

import json

import pytest

from kedami_server import db, library
from kedami_server.lesson import Lesson

from ..generation.factories import section_one, section_two
from .conftest import PAGES, extraction_body, number


def work(agent, lesson_id):
    return agent.data_dir / "work" / lesson_id


# Uploading


def test_an_agent_lesson_waits_for_claude_code(agent):
    lesson_id = agent.new_lesson()
    status = agent.lesson(lesson_id)
    assert (status["status"], status["current_stage"], status["lesson"]) == ("generating", None, None)
    assert agent.runs == []
    assert [w["id"] for w in agent.get("/agent/lessons").json()["lessons"]] == [lesson_id]


def test_pipeline_lessons_still_start_generation(agent):
    response = agent.upload(builder=None)
    assert response.status_code == 201
    assert len(agent.runs) == 1
    assert agent.get("/agent/lessons").json()["lessons"] == []


def test_computer_science_lessons_cant_use_the_agent(agent):
    response = agent.upload(subject="computer_science")
    assert response.status_code == 422
    assert "computer science" in response.json()["detail"].lower()


def test_unknown_builder_is_refused(agent):
    assert agent.upload(builder="codex").status_code == 422


# Starting


def test_start_returns_the_materials_and_claims_the_lesson(agent):
    lesson_id = agent.new_lesson()
    body = agent.start(lesson_id).json()
    assert body["subject"] == "physics"
    paths = {m["filename"]: m for m in body["materials"]}
    assert paths["problem-set.md"]["role"] == "problem_set"
    assert paths["problem-set.md"]["path"] == str(agent.data_dir / "materials" / lesson_id / "problem-set.md")
    assert agent.lesson(lesson_id)["current_stage"] == 1
    assert agent.get("/agent/lessons").json()["lessons"] == []


def test_start_again_resumes_with_the_steps_already_done(agent):
    lesson_id = agent.through_plan()
    body = agent.start(lesson_id).json()
    assert body["done"] == {"pages": True, "extraction": True, "plan": True, "sections": [], "verified": []}
    assert agent.lesson(lesson_id)["current_stage"] == 4


def test_tools_refuse_a_pipeline_lesson(agent):
    lesson_id = agent.upload(builder=None).json()["id"]
    assert agent.start(lesson_id).status_code == 409


def test_tools_refuse_an_unknown_lesson(agent):
    assert agent.start("no-such-lesson").status_code == 404


# Order


def test_steps_before_start_are_refused(agent):
    lesson_id = agent.new_lesson()
    assert agent.pages(lesson_id).status_code == 409


@pytest.mark.parametrize(
    "step",
    [
        lambda a, i: a.extraction(i),
        lambda a, i: a.plan(i),
        lambda a, i: a.section(i, 1, section_one()),
        lambda a, i: a.questions(i, 1),
        lambda a, i: a.verification(i, 1, []),
        lambda a, i: a.finish(i),
    ],
)
def test_each_step_needs_the_one_before(agent, step):
    lesson_id = agent.new_lesson()
    agent.start(lesson_id)
    response = step(agent, lesson_id)
    assert response.status_code == 409, response.text


def test_plan_needs_the_extraction(agent):
    lesson_id = agent.new_lesson()
    agent.start(lesson_id)
    agent.pages(lesson_id)
    assert agent.plan(lesson_id).status_code == 409


def test_finish_needs_every_section(agent):
    lesson_id = agent.through_plan()
    agent.section(lesson_id, 1, section_one())
    response = agent.finish(lesson_id)
    assert response.status_code == 409
    assert "2" in response.json()["detail"]


def test_a_section_outside_the_plan_is_not_found(agent):
    lesson_id = agent.through_plan()
    assert agent.section(lesson_id, 3, section_one()).status_code == 404


# Stages and files


def test_pages_are_saved_like_the_pipelines(agent):
    lesson_id = agent.new_lesson()
    agent.start(lesson_id)
    assert agent.pages(lesson_id).status_code == 200
    folder = work(agent, lesson_id)
    problem_set = (folder / "normalized" / "problem-set.md").read_text()
    assert "[problem-set.md, page 2]" in problem_set and "How far?" in problem_set
    pages = json.loads((folder / "pages.json").read_text())
    assert [(p["file"], p["page"], p["route"]) for p in pages] == [
        ("problem-set.md", 1, "agent"),
        ("problem-set.md", 2, "agent"),
        ("reference.md", 1, "agent"),
    ]
    assert agent.lesson(lesson_id)["current_stage"] == 2


@pytest.mark.parametrize(
    "files, message",
    [
        ([{"file": "problem-set.md", "pages": ["x"]}], "reference.md"),
        (PAGES["files"] + [{"file": "other.md", "pages": ["x"]}], "other.md"),
        (PAGES["files"] + [PAGES["files"][0]], "more than once"),
        ([{"file": "problem-set.md", "pages": ["  "]}, PAGES["files"][1]], "problem set"),
    ],
)
def test_pages_must_cover_each_file_once_with_a_readable_problem_set(agent, files, message):
    lesson_id = agent.new_lesson()
    agent.start(lesson_id)
    response = agent.pages(lesson_id, {"files": files})
    assert response.status_code == 422
    assert message in response.json()["detail"]
    assert not (work(agent, lesson_id) / "pages.json").exists()


def test_plan_places_the_problems_and_sets_the_title(agent):
    lesson_id = agent.new_lesson()
    agent.start(lesson_id)
    agent.pages(lesson_id)
    agent.extraction(lesson_id)
    body = agent.plan(lesson_id).json()
    sections = body["sections"]
    assert [(s["number"], s["id"]) for s in sections] == [(1, "vectors"), (2, "flight")]
    assert [p["source_ref"] for p in sections[0]["problems"]] == ["PS1 #1"]
    assert [p["source_ref"] for p in sections[1]["problems"]] == ["PS1 #2"]
    assert agent.lesson(lesson_id)["current_stage"] == 4
    assert agent.get("/lessons").json()["lessons"][0]["title"] == "Projectiles"


def test_a_plan_breaking_the_sequencing_rules_is_rejected_with_the_reason(agent):
    lesson_id = agent.new_lesson()
    agent.start(lesson_id)
    agent.pages(lesson_id)
    agent.extraction(lesson_id)
    bad = {"title": "P", "sections": [{"title": "Vectors", "goal": "g", "concepts": ["vectors"]}]}
    response = agent.plan(lesson_id, bad)
    assert response.status_code == 422
    assert "never introduced" in response.json()["detail"]
    assert not (work(agent, lesson_id) / "plan.json").exists()


def test_a_rejected_section_returns_every_reason_and_saves_nothing(agent):
    lesson_id = agent.through_plan()
    draft = section_one()
    draft["blocks"] = draft["blocks"][:2]
    response = agent.section(lesson_id, 1, draft)
    assert response.status_code == 422
    assert "missing from the section: PS1 #1" in response.json()["detail"]
    assert not (work(agent, lesson_id) / "section-1.json").exists()


def test_problem_text_comes_from_the_extraction(agent):
    lesson_id = agent.through_plan()
    body = agent.section(lesson_id, 1, section_one()).json()
    assert body["id"] == "vectors"
    assert {t["key"] for t in body["targets"]} == {"vectors-block-2", "ps1-1/a", "ps1-1/b"}
    saved = json.loads((work(agent, lesson_id) / "section-1.json").read_text())
    problem = next(b for b in saved["blocks"] if b["type"] == "problem")
    assert problem["prompt"] == "A ball is thrown at $10$ m/s."


def test_query_answers_are_refused(agent):
    lesson_id = agent.through_plan()
    draft = section_one()
    draft["blocks"][1]["answer"] = {"kind": "query", "reference": "SELECT 1"}
    response = agent.section(lesson_id, 1, draft)
    assert response.status_code == 422
    assert "query" in response.json()["detail"]


# Hints


def test_hints_that_contain_the_answer_are_dropped_and_the_rest_kept(agent):
    lesson_id = agent.through_sections()
    response = agent.hints(lesson_id, 1, [
        {"target": "ps1-1/a", "hints": ["Split the velocity.", "It comes to 8.66 m/s.", "Use cosine.", "A fourth."]},
        {"target": "vectors-block-2", "hints": ["Use the angle."]},
    ])
    assert response.status_code == 200
    body = response.json()
    assert [d["hint"] for d in body["dropped"]] == ["It comes to 8.66 m/s."]
    saved = json.loads((work(agent, lesson_id) / "section-1.json").read_text())
    problem = next(b for b in saved["blocks"] if b["type"] == "problem")
    # At most 3 hints are taken, before the check.
    assert problem["parts"][0]["hints"] == ["Split the velocity.", "Use cosine."]
    checkpoint = next(b for b in saved["blocks"] if b["type"] == "checkpoint")
    assert checkpoint["hints"] == ["Use the angle."]


def test_hints_for_a_target_replace_its_earlier_hints_only(agent):
    lesson_id = agent.through_sections()
    agent.hints(lesson_id, 1, [{"target": "ps1-1/a", "hints": ["First."]}, {"target": "ps1-1/b", "hints": ["Keep."]}])
    agent.hints(lesson_id, 1, [{"target": "ps1-1/a", "hints": ["Second."]}])
    saved = json.loads((work(agent, lesson_id) / "section-1.json").read_text())
    parts = next(b for b in saved["blocks"] if b["type"] == "problem")["parts"]
    assert [p["hints"] for p in parts] == [["Second."], ["Keep."]]


def test_hints_for_an_unknown_target_are_refused(agent):
    lesson_id = agent.through_sections()
    response = agent.hints(lesson_id, 1, [{"target": "ps1-9/a", "hints": ["x"]}])
    assert response.status_code == 422
    assert "ps1-9/a" in response.json()["detail"]


# Verification


def test_questions_never_include_the_stored_answer(agent):
    lesson_id = agent.through_sections()
    items = agent.questions(lesson_id, 1).json()["questions"]
    assert {i["target"] for i in items} == {"vectors-block-2", "ps1-1/a", "ps1-1/b"}
    assert all(i["answer"] == {"format": "number", "unit": "m/s"} for i in items)
    assert "8.66" not in json.dumps(items)


def test_the_server_sets_verified_by_comparing_answers(agent):
    lesson_id = agent.through_sections()
    response = agent.verification(lesson_id, 1, [number("vectors-block-2", 10.0), number("ps1-1/a", 9.5)])
    assert response.status_code == 200
    assert response.json() == {"verified": ["vectors-block-2"], "unverified": ["ps1-1/a", "ps1-1/b"]}
    results = json.loads((work(agent, lesson_id) / "verification-1.json").read_text())
    assert [r["verified"] for r in results] == [True, False, False]


def test_a_solution_for_an_unknown_target_is_refused(agent):
    lesson_id = agent.through_sections()
    response = agent.verification(lesson_id, 1, [number("ps1-2/2", 9.2)])
    assert response.status_code == 422
    assert "ps1-2/2" in response.json()["detail"]


# Resubmitting


def test_a_resubmitted_section_replaces_it_and_clears_its_verification(agent):
    lesson_id = agent.through_sections()
    agent.verification(lesson_id, 1, [number("vectors-block-2", 10.0)])
    agent.verification(lesson_id, 2, [number("ps1-2/2", 9.2)])
    changed = section_one()
    changed["blocks"][0]["body"] = "Components, again."
    assert agent.section(lesson_id, 1, changed).status_code == 200
    folder = work(agent, lesson_id)
    saved = json.loads((folder / "section-1.json").read_text())
    assert saved["blocks"][0]["body"] == "Components, again."
    assert not any(b.get("verified") for b in saved["blocks"])
    assert not (folder / "verification-1.json").exists()
    assert (folder / "verification-2.json").exists()
    assert agent.start(lesson_id).json()["done"]["verified"] == [2]


def test_a_new_extraction_deletes_the_plan_and_sections(agent):
    lesson_id = agent.through_sections()
    agent.verification(lesson_id, 1, [number("vectors-block-2", 10.0)])
    assert agent.extraction(lesson_id, extraction_body()).status_code == 200
    folder = work(agent, lesson_id)
    assert sorted(p.name for p in folder.iterdir()) == ["extraction.json", "normalized", "pages.json"]
    assert agent.lesson(lesson_id)["current_stage"] == 3
    assert agent.section(lesson_id, 1, section_one()).status_code == 409


def test_new_pages_delete_every_later_step(agent):
    lesson_id = agent.through_sections()
    assert agent.pages(lesson_id).status_code == 200
    assert sorted(p.name for p in work(agent, lesson_id).iterdir()) == ["normalized", "pages.json"]


# Finishing


def test_the_draft_is_never_served_before_finish(agent):
    lesson_id = agent.through_sections()
    status = agent.lesson(lesson_id)
    assert (status["status"], status["lesson"]) == ("generating", None)
    assert agent.get(f"/lessons/{lesson_id}/progress").status_code == 404
    assert not (agent.data_dir / "lessons" / f"{lesson_id}.json").exists()


def test_finish_writes_a_ready_lesson(agent):
    lesson_id = agent.through_sections()
    agent.hints(lesson_id, 1, [{"target": "ps1-1/a", "hints": ["Split the velocity."]}])
    agent.verification(lesson_id, 1, [number("vectors-block-2", 10.0), number("ps1-1/a", 8.66)])
    assert agent.finish(lesson_id).status_code == 200
    status = agent.lesson(lesson_id)
    assert (status["status"], status["current_stage"], status["error"]) == ("ready", None, None)
    lesson = Lesson.model_validate(status["lesson"])
    assert lesson.title == "Projectiles" and lesson.source_files == ["problem-set.md", "reference.md"]
    part = lesson.find_block("ps1-1").parts[0]
    assert (part.hints, part.verified) == (["Split the velocity."], True)
    assert lesson.find_block("ps1-2").parts[0].verified is False
    assert status["rerun_stages"] == []


def test_a_finished_lesson_takes_no_more_tool_calls(agent):
    lesson_id = agent.through_sections()
    agent.finish(lesson_id)
    assert agent.section(lesson_id, 1, section_one()).status_code == 409
    assert agent.finish(lesson_id).status_code == 409


def test_agent_lessons_cant_be_rerun(agent):
    lesson_id = agent.through_sections()
    agent.finish(lesson_id)
    response = agent.post(f"/lessons/{lesson_id}/rerun", {"stage": 1})
    assert response.status_code == 409


# Ending a build


def test_fail_ends_the_build_with_the_reason(agent):
    lesson_id = agent.through_plan()
    assert agent.fail(lesson_id, "The scan is unreadable.").status_code == 200
    status = agent.lesson(lesson_id)
    assert (status["status"], status["error"]) == ("failed", "The scan is unreadable.")
    assert agent.section(lesson_id, 1, section_one()).status_code == 409
    assert agent.start(lesson_id).status_code == 409


def test_cancel_from_the_window_fails_a_waiting_or_started_build(agent):
    waiting, started = agent.new_lesson(), agent.through_plan()
    for lesson_id in (waiting, started):
        assert agent.post(f"/lessons/{lesson_id}/cancel").status_code == 200
        status = agent.lesson(lesson_id)
        assert (status["status"], status["error"]) == ("failed", "Canceled.")
    # A failed lesson can be deleted, like any other.
    assert agent.client.delete(f"/lessons/{waiting}", headers={"Authorization": "Bearer t"}).status_code == 200


def test_pipeline_lessons_cant_be_canceled(agent):
    lesson_id = agent.upload(builder=None).json()["id"]
    assert agent.post(f"/lessons/{lesson_id}/cancel").status_code == 409


def test_a_restart_fails_a_build_in_progress(agent):
    lesson_id = agent.through_plan()
    with db.connect(agent.data_dir) as conn:
        library.fail_interrupted(conn, lambda _: False)
    assert agent.lesson(lesson_id)["status"] == "failed"
    assert agent.section(lesson_id, 1, section_one()).status_code == 409
