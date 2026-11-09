"""A lesson needs both a problem set and a reference. See Upload rules in architecture/pipeline.md."""

import pytest

from kedami_server import db
from kedami_server.generation import pipeline
from kedami_server.generation.schemas import Transcription

from .conftest import AUTH, REFERENCE_TEXT, upload
from .files import png
from .test_pipeline import FakeModel, happy_script, lesson_status, run

PROBLEM_SET = ("ps.md", b"PS1\n1. A ball...", "problem_set", False)
REFERENCE = ("notes.md", REFERENCE_TEXT, "reference", False)


def lessons_on_disk(data_dir):
    return list((data_dir / "materials").glob("*")) if (data_dir / "materials").exists() else []


@pytest.mark.parametrize(
    "files, message",
    [
        ([PROBLEM_SET], "Tag at least one file as a reference."),
        ([REFERENCE], "Tag at least one file as a problem set."),
    ],
)
def test_an_upload_missing_either_is_refused_and_saves_nothing(started, data_dir, files, message):
    client, _, runs = started
    response = upload(client, files)
    assert (response.status_code, response.json()["detail"]) == (422, message)
    assert runs == []
    assert lessons_on_disk(data_dir) == []
    assert client.get("/lessons", headers=AUTH).json()["lessons"] == []


def test_an_upload_with_both_is_accepted(started):
    client, _, runs = started
    assert upload(client, [PROBLEM_SET, REFERENCE]).status_code == 201
    assert len(runs) == 1


def test_a_placeholder_cant_be_filled_without_a_reference(started):
    client, _, runs = started
    planned = {"folder_id": None, "placeholders": [{"name": "Week 1", "due_date": None}]}
    lesson_id = client.post("/placeholders", json=planned, headers=AUTH).json()["ids"][0]
    response = client.post(
        f"/lessons/{lesson_id}/fill",
        data={"subject": "math", "roles": ["problem_set"], "force": ["false"]},
        files=[("files", ("ps.md", b"PS1", "text/markdown"))],
        headers=AUTH,
    )
    assert (response.status_code, response.json()["detail"]) == (422, "Tag at least one file as a reference.")
    assert runs == []
    assert client.get(f"/lessons/{lesson_id}", headers=AUTH).json()["status"] == "placeholder"


def test_a_reference_with_no_readable_text_fails_the_lesson(started, data_dir):
    client, _, _ = started
    lesson_id = upload(client, [PROBLEM_SET, ("blank.png", png(), "reference", False)]).json()["id"]
    run(data_dir, lesson_id, FakeModel({Transcription: [{"markdown": "  "}]}))
    status = lesson_status(client, lesson_id)
    assert (status["status"], status["error"]) == ("failed", "No text could be read from the reference.")


def test_the_failed_lesson_can_be_rerun_from_stage_one_only(started, data_dir):
    client, _, _ = started
    lesson_id = upload(client, [PROBLEM_SET, ("blank.png", png(), "reference", False)]).json()["id"]
    run(data_dir, lesson_id, FakeModel({Transcription: [{"markdown": "  "}]}))
    assert client.get(f"/lessons/{lesson_id}", headers=AUTH).json()["rerun_stages"] == [1]


def without_reference(client, data_dir):
    """A ready lesson from before a reference was required: its only material is a problem set."""
    lesson_id = upload(client, [PROBLEM_SET, REFERENCE]).json()["id"]
    run(data_dir, lesson_id, FakeModel(happy_script()))
    with db.connect(data_dir) as conn:
        conn.execute("DELETE FROM materials WHERE lesson_id = ? AND role = 'reference'", (lesson_id,))
    work = pipeline.work_dir(data_dir, lesson_id)
    (work / pipeline.NORMALIZED / pipeline.REFERENCE_FILE).write_text("")
    (work / pipeline.PASSAGES_FILE).unlink()
    return lesson_id


def test_an_older_lesson_with_no_reference_still_opens(started, data_dir):
    client, _, _ = started
    lesson_id = without_reference(client, data_dir)
    assert client.get(f"/lessons/{lesson_id}", headers=AUTH).json()["status"] == "ready"
    # Show solution and Generate simulation still get its problem set, with no empty reference section.
    [material] = pipeline.normalized_materials(data_dir, lesson_id, "physics")
    assert "<problem_set>" in material["text"] and "<reference_material>" not in material["text"]


@pytest.mark.parametrize("stage", [1, 2, 3, 4])
def test_an_older_lesson_with_no_reference_cant_be_rerun(started, data_dir, stage):
    client, _, runs = started
    lesson_id = without_reference(client, data_dir)
    assert client.get(f"/lessons/{lesson_id}", headers=AUTH).json()["rerun_stages"] == []
    response = client.post(f"/lessons/{lesson_id}/rerun", json={"stage": stage}, headers=AUTH)
    assert response.status_code == 409
    assert len(runs) == 1  # Only the upload's run.


def test_a_lesson_with_a_reference_can_still_be_rerun_from_any_stage(started, data_dir):
    client, _, _ = started
    lesson_id = upload(client, [PROBLEM_SET, REFERENCE]).json()["id"]
    run(data_dir, lesson_id, FakeModel(happy_script()))
    assert client.get(f"/lessons/{lesson_id}", headers=AUTH).json()["rerun_stages"] == [1, 2, 3, 4]


def test_the_extraction_prompt_treats_the_reference_as_always_there():
    from kedami_server.generation import prompts

    assert "when it is given" not in prompts.EXTRACT_SYSTEM
    assert "otherwise" not in prompts.EXTRACT_SYSTEM.split("The reference is split")[1]
