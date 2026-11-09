"""Formatting a reference's kept PDF pages: what is sent, and what becomes of each reply."""

import json

import pytest

from kedami_server.generation import pipeline
from kedami_server.generation.formatting import (
    CALL_FAILED,
    FAILED_WORD_CHECK,
    FORMATTED,
    LEFT_OUT,
    MAX_PAGES_PER_CALL,
)
from kedami_server.generation.ingest import Material, ingest
from kedami_server.generation.schemas import FormattedPages, TextChecks, Transcription
from kedami_server.generation.sources import read_pages
from kedami_server.model import ModelError

from .conftest import upload
from .files import LONG, png, text_pdf
from .test_ingest import checks, transcribed
from .test_pipeline import FakeModel, happy_script, run


def sent(prompt):
    """The pages in a format request."""
    return json.loads(prompt[0]["text"].split("\n\n", 1)[1])


def as_markdown(prompt):
    """A reply that keeps every word and adds a heading mark."""
    return {"pages": [{"page": p["page"], "markdown": f"# {p['text']}", "dropped_lines": []} for p in sent(prompt)]}


def all_clean(count):
    return checks(**{str(n): True for n in range(1, count + 1)})


@pytest.fixture
def pdf(tmp_path):
    def write(*pages, name="notes.pdf"):
        (tmp_path / name).write_bytes(text_pdf(*pages))
        return tmp_path
    return write


def reference(name="notes.pdf", force=False):
    return Material(name, "reference", force)


def test_a_kept_page_comes_back_formatted(pdf):
    folder = pdf(LONG)
    fake = FakeModel({TextChecks: [all_clean(1)], FormattedPages: [as_markdown]})
    normalized, [page] = ingest(folder, [reference()], fake)
    assert (page.markdown, page.format) == (f"# {LONG}", FORMATTED)
    assert normalized.reference == f"[notes.pdf, page 1]\n\n# {LONG}"
    assert [call["role"] for call in fake.calls[FormattedPages]] == ["format"]


def test_dropped_lines_are_saved_with_the_page(pdf):
    folder = pdf(LONG)
    # The text layer is one line, so test the check through a page the reply fully keeps.
    reply = {"pages": [{"page": 1, "markdown": LONG, "dropped_lines": [""]}]}
    _, [page] = ingest(folder, [reference()], FakeModel({TextChecks: [all_clean(1)], FormattedPages: [reply]}))
    assert (page.format, page.dropped_lines) == (FORMATTED, [""])


def test_a_page_that_fails_the_check_keeps_its_raw_text(pdf):
    folder = pdf(LONG)
    reply = {"pages": [{"page": 1, "markdown": LONG.replace("45", "46"), "dropped_lines": []}]}
    normalized, [page] = ingest(folder, [reference()], FakeModel({TextChecks: [all_clean(1)], FormattedPages: [reply]}))
    assert (page.markdown, page.format) == (LONG, FAILED_WORD_CHECK)
    assert LONG in normalized.reference and "46" not in normalized.reference


def test_a_page_the_reply_leaves_out_keeps_its_raw_text(pdf):
    folder = pdf(LONG, LONG + " Two?")
    reply = {"pages": [{"page": 1, "markdown": LONG, "dropped_lines": []}]}
    _, pages = ingest(folder, [reference()], FakeModel({TextChecks: [all_clean(2)], FormattedPages: [reply]}))
    assert [(p.format, p.markdown) for p in pages] == [(FORMATTED, LONG), (LEFT_OUT, LONG + " Two?")]


def test_one_bad_page_doesnt_touch_the_others_in_its_call(pdf):
    folder = pdf(LONG, LONG + " Two?")
    reply = {"pages": [
        {"page": 1, "markdown": "Something else.", "dropped_lines": []},
        {"page": 2, "markdown": f"## {LONG} Two?", "dropped_lines": []},
    ]}
    _, pages = ingest(folder, [reference()], FakeModel({TextChecks: [all_clean(2)], FormattedPages: [reply]}))
    assert [p.format for p in pages] == [FAILED_WORD_CHECK, FORMATTED]


def test_a_page_the_request_didnt_ask_for_is_ignored(pdf):
    folder = pdf(LONG)
    reply = {"pages": [{"page": 1, "markdown": LONG, "dropped_lines": []}, {"page": 9, "markdown": "x", "dropped_lines": []}]}
    _, pages = ingest(folder, [reference()], FakeModel({TextChecks: [all_clean(1)], FormattedPages: [reply]}))
    assert [(p.page, p.format) for p in pages] == [(1, FORMATTED)]


@pytest.mark.parametrize(
    "failure, calls",
    [
        (ModelError("The model's reply was cut off at the token limit."), 1),
        (None, 3),  # A reply that keeps failing validation is tried three times.
    ],
)
def test_a_failed_call_leaves_its_pages_raw_and_doesnt_fail_the_lesson(pdf, failure, calls):
    folder = pdf(LONG)
    replies = [failure] if failure else [{"pages": [{"page": "one"}]}] * calls
    fake = FakeModel({TextChecks: [all_clean(1)], FormattedPages: replies})
    normalized, [page] = ingest(folder, [reference()], fake)
    assert (page.markdown, page.format) == (LONG, CALL_FAILED)
    assert LONG in normalized.reference
    assert len(fake.calls[FormattedPages]) == calls


def test_at_most_ten_consecutive_pages_go_in_a_call(pdf):
    count = MAX_PAGES_PER_CALL + 3
    folder = pdf(*[f"{LONG} {n}" for n in range(1, count + 1)])
    fake = FakeModel({TextChecks: [all_clean(count)], FormattedPages: [as_markdown, as_markdown]})
    _, pages = ingest(folder, [reference()], fake)
    numbers = sorted([p["page"] for p in sent(call["prompt"])] for call in fake.calls[FormattedPages])
    assert numbers == [list(range(1, 11)), [11, 12, 13]]
    assert [p.page for p in pages] == list(range(1, count + 1))
    assert {p.format for p in pages} == {FORMATTED}


def test_a_transcribed_page_breaks_a_run_and_isnt_formatted(pdf):
    folder = pdf(LONG, "", LONG + " Three?")
    fake = FakeModel({
        TextChecks: [all_clean(3)],
        Transcription: [transcribed],
        FormattedPages: [as_markdown, as_markdown],
    })
    _, pages = ingest(folder, [reference()], fake)
    assert sorted([p["page"] for p in sent(call["prompt"])] for call in fake.calls[FormattedPages]) == [[1], [3]]
    assert [p.format for p in pages] == [FORMATTED, None, FORMATTED]
    assert pages[1].markdown.startswith("TRANSCRIBED")


def test_each_file_gets_its_own_calls(pdf):
    pdf(LONG, name="one.pdf")
    folder = pdf(LONG, name="two.pdf")
    fake = FakeModel({
        TextChecks: [all_clean(1), all_clean(1)],
        FormattedPages: [as_markdown, as_markdown],
    })
    _, pages = ingest(folder, [reference("one.pdf"), reference("two.pdf")], fake)
    assert len(fake.calls[FormattedPages]) == 2
    assert [(p.file, p.format) for p in pages] == [("one.pdf", FORMATTED), ("two.pdf", FORMATTED)]


def test_a_problem_set_isnt_formatted(pdf):
    folder = pdf(LONG)
    fake = FakeModel({TextChecks: [all_clean(1)]})
    _, [page] = ingest(folder, [Material("notes.pdf", "problem_set", False)], fake)
    assert (page.markdown, page.format) == (LONG, None)
    assert FormattedPages not in fake.calls


def test_a_text_file_isnt_formatted(tmp_path):
    (tmp_path / "notes.md").write_text("# Notes")
    fake = FakeModel({})
    _, [page] = ingest(tmp_path, [reference("notes.md")], fake)
    assert (page.markdown, page.format) == ("# Notes", None)


def test_an_image_or_forced_page_isnt_formatted(pdf):
    folder = pdf(LONG)
    (folder / "photo.png").write_bytes(png())
    fake = FakeModel({Transcription: [transcribed, transcribed]})
    _, pages = ingest(folder, [reference(force=True), reference("photo.png")], fake)
    assert [p.format for p in pages] == [None, None]
    assert FormattedPages not in fake.calls


def test_a_blank_formatted_page_is_left_out_of_the_document(tmp_path):
    (tmp_path / "notes.pdf").write_bytes(text_pdf(LONG, LONG + " Two?"))
    reply = {"pages": [
        {"page": 1, "markdown": "", "dropped_lines": [LONG]},
        {"page": 2, "markdown": f"{LONG} Two?", "dropped_lines": []},
    ]}
    fake = FakeModel({TextChecks: [all_clean(2)], FormattedPages: [reply]})
    normalized, _ = ingest(tmp_path, [reference()], fake)
    assert normalized.reference == f"[notes.pdf, page 2]\n\n{LONG} Two?"


def test_pdfium_s_marks_are_taken_out_of_a_text_layer(tmp_path, monkeypatch):
    """A real text layer: Windows line ends, and 0x02 where a hyphen ended a line."""
    class TextPage:
        def get_text_bounded(self):
            return "out\x02\r\ngoing\x07 rays\tand  symbols\r\n"

    class FakePage:
        def get_textpage(self):
            return TextPage()

    monkeypatch.setattr("kedami_server.generation.sources.pdfium.PdfDocument", lambda _path: [FakePage()])
    [page] = read_pages(tmp_path / "notes.pdf")
    assert page.text == "out-\ngoing rays\tand  symbols\n"


# The pipeline's saved output


def test_stage_one_saves_the_passages_and_each_page_s_format(started, data_dir):
    client, _, _ = started
    files = [("ps.md", b"PS1\n1. A ball...", "problem_set", False), ("notes.pdf", text_pdf(LONG), "reference", False)]
    lesson_id = upload(client, files).json()["id"]
    run(data_dir, lesson_id, FakeModel({**happy_script(), TextChecks: [all_clean(1)], FormattedPages: [as_markdown]}))
    work = pipeline.work_dir(data_dir, lesson_id)
    assert json.loads((work / "passages.json").read_text()) == [
        {"number": 1, "kind": "text", "file": "notes.pdf", "page": 1, "text": f"# {LONG}"}
    ]
    pages = json.loads((work / "pages.json").read_text())
    assert [(p["file"], p["format"], p["dropped_lines"]) for p in pages] == [
        ("ps.md", None, []),
        ("notes.pdf", FORMATTED, []),
    ]


def test_a_rerun_from_stage_one_replaces_the_passages(started, data_dir):
    client, _, _ = started
    files = [("ps.md", b"PS1\n1. A ball...", "problem_set", False), ("notes.md", b"First.\n\nSecond.", "reference", False)]
    lesson_id = upload(client, files).json()["id"]
    run(data_dir, lesson_id, FakeModel(happy_script()))
    passages = pipeline.work_dir(data_dir, lesson_id) / "passages.json"
    assert [p["text"] for p in json.loads(passages.read_text())] == ["First.", "Second."]
    (pipeline.materials_dir(data_dir, lesson_id) / "notes.md").write_text("Only.")
    pipeline.run(data_dir, lesson_id, "physics", 1, FakeModel(happy_script()))
    assert [p["text"] for p in json.loads(passages.read_text())] == ["Only."]


def test_a_rerun_from_a_later_stage_keeps_the_passages(started, data_dir):
    client, _, _ = started
    files = [("ps.md", b"PS1\n1. A ball...", "problem_set", False), ("notes.md", b"First.", "reference", False)]
    lesson_id = upload(client, files).json()["id"]
    run(data_dir, lesson_id, FakeModel(happy_script()))
    passages = pipeline.work_dir(data_dir, lesson_id) / "passages.json"
    saved = passages.read_text()
    pipeline.run(data_dir, lesson_id, "physics", 2, FakeModel(happy_script()))
    assert passages.read_text() == saved
