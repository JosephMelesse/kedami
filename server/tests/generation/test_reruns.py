import json

import pytest

from kedami_server import db, library
from kedami_server.generation import pipeline
from kedami_server.generation.schemas import (
    Extraction,
    HintDraft,
    HintJudgements,
    Plan,
    SectionDraft,
    Solutions,
    TextChecks,
    Transcription,
)
from kedami_server.lesson import Lesson
from kedami_server.progress import Record, load_all, save
from kedami_server.storage import seed_sample

from .files import LONG, png, text_pdf
from .conftest import AUTH, upload
from .factories import plan
from .test_pipeline import FakeModel, happy_script, lesson_status, run, section_one, solved


@pytest.fixture
def generated(started, data_dir):
    """A lesson generated once from the default files."""
    client, create, runs = started
    lesson_id = create().json()["id"]
    run(data_dir, lesson_id, FakeModel(happy_script()))
    runs.clear()
    return client, lesson_id, runs


def rerun(client, lesson_id, stage, force=None):
    return client.post(f"/lessons/{lesson_id}/rerun", json={"stage": stage, "force": force or {}}, headers=AUTH)


def revision(data_dir, lesson_id):
    with db.connect(data_dir) as conn:
        return library.get_lesson_row(conn, lesson_id).revision


# Uploads


@pytest.mark.parametrize(
    "files, message",
    [
        ([], "Field required"),
        ([("notes.md", b"x", "reference", False)], "at least one file as a problem set"),
        ([("ps.docx", b"x", "problem_set", False)], "only PDF"),
        ([("ps.pdf", b"not a pdf", "problem_set", False)], "could not be read as a PDF"),
        ([("ps.md", b"x", "homework", False)], "role must be"),
        ([("ps.pdf", text_pdf(*[LONG] * 101), "problem_set", False)], "101 pages"),
        ([("ps.md", b"x", "problem_set", False)] * 21, "at most 20 files"),
    ],
)
def test_uploads_are_checked_before_anything_is_saved(started, data_dir, files, message):
    client, _, runs = started
    response = upload(client, files)
    assert response.status_code == 422
    assert message in json.dumps(response.json())
    assert runs == [] and not (data_dir / "materials").exists()


def test_upload_needs_matching_roles_and_force_settings(started):
    client, _, _ = started
    response = client.post(
        "/lessons", data={"subject": "math", "roles": ["problem_set"], "force": ["false", "false"]},
        files=[("files", ("a.md", b"x", "text/markdown"))], headers=AUTH,
    )
    assert response.status_code == 422


def test_upload_names_are_made_safe_and_text_files_never_force(started, data_dir):
    client, _, _ = started
    files = [
        ("../PS 3.pdf", text_pdf(LONG), "problem_set", True),
        ("PS 3.pdf", text_pdf(LONG), "problem_set", False),
        ("scan.png", png(), "reference", True),
        ("notes.md", b"# n", "reference", True),
    ]
    lesson_id = upload(client, files).json()["id"]
    materials = [(m["filename"], m["role"], m["force_transcription"]) for m in lesson_status(client, lesson_id)["materials"]]
    assert materials == [
        ("PS-3.pdf", "problem_set", True),
        ("PS-3-2.pdf", "problem_set", False),
        ("scan.png", "reference", True),
        ("notes.md", "reference", False),
    ]
    assert sorted(p.name for p in (data_dir / "materials" / lesson_id).iterdir()) == sorted(m[0] for m in materials)


def test_stage_one_routes_uploaded_pdfs_and_images(started, data_dir):
    client, _, _ = started
    files = [("ps.pdf", text_pdf(LONG, ""), "problem_set", False), ("notes.png", png(), "reference", False)]
    lesson_id = upload(client, files).json()["id"]
    fake = FakeModel(happy_script({
        TextChecks: [{"pages": [{"page": 1, "clean": True}]}],
        Transcription: [{"markdown": "TRANSCRIBED"}, {"markdown": "TRANSCRIBED"}],
    }))
    run(data_dir, lesson_id, fake)
    assert lesson_status(client, lesson_id)["status"] == "ready"
    pages = json.loads((data_dir / "work" / lesson_id / "pages.json").read_text())
    assert [(p["file"], p["page"], p["route"]) for p in pages] == [
        ("ps.pdf", 1, "keep"), ("ps.pdf", 2, "transcribe"), ("notes.png", 1, "transcribe"),
    ]
    assert LONG in fake.calls[Extraction][0]["prompt"][0]["text"]


def test_problem_set_with_no_readable_text_fails(started, data_dir):
    client, _, _ = started
    lesson_id = upload(client, [("blank.png", png(), "problem_set", False)]).json()["id"]
    run(data_dir, lesson_id, FakeModel({Transcription: [{"markdown": ""}]}))
    assert lesson_status(client, lesson_id)["error"] == "No text could be read from the problem set."


# The rerun route


def test_rerun_stages_follow_the_saved_outputs(generated):
    client, lesson_id, _ = generated
    assert lesson_status(client, lesson_id)["rerun_stages"] == [1, 2, 3, 4]


def test_rerun_starts_generation_from_the_stage(generated, data_dir):
    client, lesson_id, runs = generated
    assert rerun(client, lesson_id, 3).status_code == 200
    assert runs == [(data_dir, lesson_id, "physics", 3)]
    status = lesson_status(client, lesson_id)
    assert (status["status"], status["lesson"]) == ("generating", None)


def test_rerun_while_generating_is_refused(generated):
    client, lesson_id, _ = generated
    rerun(client, lesson_id, 4)
    assert rerun(client, lesson_id, 4).status_code == 409


def test_rerun_needs_the_earlier_outputs(generated, data_dir):
    client, lesson_id, runs = generated
    (data_dir / "work" / lesson_id / "plan.json").unlink()
    assert lesson_status(client, lesson_id)["rerun_stages"] == [1, 2, 3]
    assert rerun(client, lesson_id, 4).status_code == 409
    assert runs == []


def test_lesson_without_source_files_cannot_be_rerun(started, data_dir):
    client, _, _ = started
    seed_sample(data_dir)
    assert lesson_status(client, "sample")["rerun_stages"] == []
    assert rerun(client, "sample", 1).status_code == 409


def test_changing_force_transcription_needs_stage_one(generated, data_dir):
    client, lesson_id, runs = generated
    material = str(lesson_status(client, lesson_id)["materials"][0]["id"])
    assert rerun(client, lesson_id, 2, {material: True}).status_code == 422
    assert rerun(client, lesson_id, 2, {material: False}).status_code == 200  # unchanged is fine
    with db.connect(data_dir) as conn:
        library.set_ready(conn, lesson_id)
    assert rerun(client, lesson_id, 1, {material: True}).status_code == 200
    assert lesson_status(client, lesson_id)["materials"][0]["force_transcription"] is True


@pytest.mark.parametrize("body", [{"stage": 0}, {"stage": 5}, {"stage": "1"}, {"stage": 1, "force": {"999": True}}, {"stage": 1, "extra": 1}])
def test_bad_rerun_requests(generated, body):
    client, lesson_id, _ = generated
    assert client.post(f"/lessons/{lesson_id}/rerun", json=body, headers=AUTH).status_code == 422


# Running a rerun


def test_rerun_from_stage_four_reuses_earlier_outputs(generated, data_dir):
    client, lesson_id, _ = generated
    extraction = (data_dir / "work" / lesson_id / "extraction.json").read_text()
    fake = FakeModel(happy_script())
    run(data_dir, lesson_id, fake, start_stage=4)
    assert Extraction not in fake.calls and Plan not in fake.calls
    assert len(fake.calls[SectionDraft]) == 2
    assert (data_dir / "work" / lesson_id / "extraction.json").read_text() == extraction
    status = lesson_status(client, lesson_id)
    assert (status["status"], status["error"]) == ("ready", None)
    assert revision(data_dir, lesson_id) == 2


def test_rerun_from_stage_two_redoes_everything_after_it(generated, data_dir):
    client, lesson_id, _ = generated
    fake = FakeModel(happy_script())
    run(data_dir, lesson_id, fake, start_stage=2)
    assert len(fake.calls[Extraction]) == 1 and len(fake.calls[Plan]) == 1
    assert revision(data_dir, lesson_id) == 2


def test_rerun_with_fewer_sections_leaves_no_stale_outputs(generated, data_dir):
    _, lesson_id, _ = generated
    one_section = {"blocks": section_one()["blocks"] + [
        {"type": "problem", "source_ref": "PS1 #2", "parts": [{"label": "2", "answer": {"kind": "numeric", "value": 9.2}}]}]}
    fake = FakeModel(happy_script({
        Plan: [plan(("Everything", ["vectors", "gravity", "range"]))],
        SectionDraft: [one_section],
        Solutions: [solved(**{"everything-block-2": 10.0})],
    }))
    fake.script[HintDraft] = [{"items": []}]
    fake.script[HintJudgements] = []
    run(data_dir, lesson_id, fake, start_stage=3)
    work = data_dir / "work" / lesson_id
    assert sorted(p.name for p in work.glob("section-*.json")) == ["section-1.json"]
    assert sorted(p.name for p in work.glob("verification-*.json")) == ["verification-1.json"]


def test_rerun_carries_progress_over(generated, data_dir):
    client, lesson_id, _ = generated
    with db.connect(data_dir) as conn:
        save(conn, lesson_id, Record(block_id="ps1-1", part_id="a", status="correct", last_response="8.66", attempts=1))
        save(conn, lesson_id, Record(block_id="ps1-1", part_id="b", status="marked_done"))
        save(conn, lesson_id, Record(block_id="vectors-block-2", part_id=None, status="correct", last_response="10"))
    changed = section_one()
    changed["blocks"][2]["parts"][0]["answer"]["value"] = 7.5
    run(data_dir, lesson_id, FakeModel(happy_script({SectionDraft: [changed, happy_script()[SectionDraft][1]]})), start_stage=4)
    with db.connect(data_dir) as conn:
        records = {(r.block_id, r.part_id): r.status for r in load_all(conn, lesson_id)}
    assert records == {("ps1-1", "a"): "in_progress", ("ps1-1", "b"): "marked_done"}
    lesson = Lesson.model_validate(lesson_status(client, lesson_id)["lesson"])
    assert lesson.find_block("ps1-1").parts[0].answer.value == 7.5


def test_failed_rerun_keeps_the_previous_lesson(generated, data_dir):
    client, lesson_id, _ = generated
    before = (data_dir / "lessons" / f"{lesson_id}.json").read_text()
    with db.connect(data_dir) as conn:
        save(conn, lesson_id, Record(block_id="ps1-1", part_id="a", status="correct", last_response="8.66"))
    bad = {"blocks": [{"type": "explanation", "body": "No problems."}]}
    run(data_dir, lesson_id, FakeModel(happy_script({SectionDraft: [bad, bad, bad]})), start_stage=4)
    status = lesson_status(client, lesson_id)
    assert status["status"] == "ready"
    assert status["error"].startswith("The last rerun failed. Section 1")
    assert (data_dir / "lessons" / f"{lesson_id}.json").read_text() == before
    assert revision(data_dir, lesson_id) == 1
    with db.connect(data_dir) as conn:
        assert [r.status for r in load_all(conn, lesson_id)] == ["correct"]


def test_successful_rerun_clears_an_earlier_rerun_error(generated, data_dir):
    client, lesson_id, _ = generated
    with db.connect(data_dir) as conn:
        library.set_rerun_failed(conn, lesson_id, "Overloaded")
    run(data_dir, lesson_id, FakeModel(happy_script()), start_stage=4)
    assert lesson_status(client, lesson_id)["error"] is None


def test_interrupted_rerun_keeps_the_previous_lesson(generated, data_dir):
    client, lesson_id, _ = generated
    rerun(client, lesson_id, 4)
    with db.connect(data_dir) as conn:
        library.fail_interrupted(conn, lambda i: pipeline.lesson_path(data_dir, i).exists())
    status = lesson_status(client, lesson_id)
    assert status["status"] == "ready" and "interrupted" in status["error"]
    assert status["lesson"] is not None
