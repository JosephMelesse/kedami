import base64
import io
import json

import pytest
from PIL import Image

from kedami_server.generation.ingest import Material, ingest
from kedami_server.generation.retry import GenerationError
from kedami_server.generation.schemas import TextChecks, Transcription
from kedami_server.generation.sources import MAX_IMAGE_EDGE, SourceError, kind_of, page_count, safe_filename

from .files import LONG, png, text_pdf
from .test_pipeline import FakeModel


def transcribed(prompt):
    """Echo which page was sent, so results don't depend on thread order."""
    image, text = prompt
    assert image["type"] == "image" and image["source"]["media_type"] == "image/png"
    return {"markdown": f"TRANSCRIBED {text['text']}"}


def checks(**verdicts):
    """Text check replies: page number -> clean, for pages in the request."""
    def reply(prompt):
        pages = json.loads(prompt[0]["text"].split("\n\n", 1)[1])
        return {"pages": [{"page": p["page"], "clean": verdicts[str(p["page"])]} for p in pages if str(p["page"]) in verdicts]}
    return reply


@pytest.fixture
def folder(tmp_path):
    def write(name, data):
        (tmp_path / name).write_bytes(data if isinstance(data, bytes) else data.encode())
    write("notes.md", "# Notes\n\n$v = v_0 + at$")
    write("photo.png", png())
    write("ps.pdf", text_pdf(LONG, "", LONG + " Clean?"))
    return tmp_path, write


def routes(pages):
    return [(p.file, p.page, p.route, p.reason) for p in pages]


def test_every_route(folder):
    path, _ = folder
    fake = FakeModel({TextChecks: [checks(**{"1": True, "3": False})], Transcription: [transcribed] * 3})
    materials = [
        Material("ps.pdf", "problem_set", False),
        Material("photo.png", "problem_set", False),
        Material("notes.md", "reference", False),
    ]
    normalized, pages = ingest(path, materials, fake)
    assert routes(pages) == [
        ("ps.pdf", 1, "keep", "text layer judged clean"),
        ("ps.pdf", 2, "transcribe", "no usable text layer"),
        ("ps.pdf", 3, "transcribe", "text layer judged unclean"),
        ("photo.png", 1, "transcribe", "image file"),
        ("notes.md", 1, "keep", "text file"),
    ]
    assert pages[0].markdown == LONG
    assert pages[1].markdown == "TRANSCRIBED Transcribe page 2 of ps.pdf."
    assert normalized.problem_set.startswith(f"[ps.pdf, page 1]\n\n{LONG}\n\n[ps.pdf, page 2]")
    assert "[photo.png, page 1]\n\nTRANSCRIBED Transcribe page 1 of photo.png." in normalized.problem_set
    assert normalized.reference == "[notes.md, page 1]\n\n# Notes\n\n$v = v_0 + at$"
    assert [c["role"] for c in fake.calls[TextChecks]] == ["small_check"]
    assert {c["role"] for c in fake.calls[Transcription]} == {"transcribe"}


def test_only_text_layer_pages_go_to_the_text_check(folder):
    path, _ = folder
    fake = FakeModel({TextChecks: [checks(**{"1": True, "3": True})], Transcription: [transcribed]})
    ingest(path, [Material("ps.pdf", "problem_set", False)], fake)
    sent = json.loads(fake.calls[TextChecks][0]["prompt"][0]["text"].split("\n\n", 1)[1])
    assert [p["page"] for p in sent] == [1, 3]


def test_force_transcription_skips_the_text_check(folder):
    path, _ = folder
    fake = FakeModel({Transcription: [transcribed] * 3})
    _, pages = ingest(path, [Material("ps.pdf", "problem_set", True)], fake)
    assert {(p.route, p.reason) for p in pages} == {("transcribe", "force transcription is on")}
    assert TextChecks not in fake.calls


def test_page_without_a_verdict_is_transcribed(folder):
    path, _ = folder
    fake = FakeModel({TextChecks: [checks(**{"1": True})], Transcription: [transcribed] * 2})
    _, pages = ingest(path, [Material("ps.pdf", "problem_set", False)], fake)
    assert routes(pages)[2] == ("ps.pdf", 3, "transcribe", "the text check gave no verdict")


def test_short_text_layer_counts_as_none(folder):
    path, write = folder
    write("short.pdf", text_pdf("Page 7"))
    fake = FakeModel({Transcription: [transcribed]})
    _, pages = ingest(path, [Material("short.pdf", "problem_set", False)], fake)
    assert routes(pages) == [("short.pdf", 1, "transcribe", "no usable text layer")]


def test_text_files_ignore_force_transcription(folder):
    path, _ = folder
    _, pages = ingest(path, [Material("notes.md", "problem_set", True)], FakeModel({}))
    assert routes(pages) == [("notes.md", 1, "keep", "text file")]


def test_images_sent_to_the_model_are_scaled_down(folder):
    path, write = folder
    write("big.png", png(4000, 3000))
    fake = FakeModel({Transcription: [transcribed]})
    ingest(path, [Material("big.png", "problem_set", False)], fake)
    data = fake.calls[Transcription][0]["prompt"][0]["source"]["data"]
    assert max(Image.open(io.BytesIO(base64.b64decode(data))).size) == MAX_IMAGE_EDGE


def test_transcription_that_keeps_failing_fails_the_stage(folder):
    path, _ = folder
    bad = {"markdown": None}
    fake = FakeModel({Transcription: [bad] * 3})
    with pytest.raises(GenerationError, match="Transcription of photo.png page 1 failed after 3 attempts"):
        ingest(path, [Material("photo.png", "problem_set", False)], fake)


def test_same_files_route_the_same_way_every_run(folder):
    path, _ = folder
    def run():
        fake = FakeModel({TextChecks: [checks(**{"1": True, "3": False})], Transcription: [transcribed] * 2})
        return routes(ingest(path, [Material("ps.pdf", "problem_set", False)], fake)[1])
    assert run() == run()


# Files


@pytest.mark.parametrize(
    "name, kind", [("a.PDF", "pdf"), ("b.md", "text"), ("c.txt", "text"), ("d.jpeg", "image"), ("e.WebP", "image")]
)
def test_kinds(name, kind):
    assert kind_of(name) == kind


@pytest.mark.parametrize("name", ["a.docx", "b.heic", "c", "d.pdf.exe"])
def test_unsupported_kinds(name):
    with pytest.raises(SourceError, match="only PDF"):
        kind_of(name)


def test_page_counts():
    assert page_count("a.pdf", text_pdf(LONG, LONG, "")) == 3
    assert page_count("a.png", png()) == 1
    assert page_count("a.md", b"# hi") == 1


@pytest.mark.parametrize(
    "name, data, message",
    [
        ("a.pdf", b"not a pdf", "could not be read as a PDF"),
        ("a.png", b"not an image", "could not be read as an image"),
        ("a.txt", b"\xff\xfe\x00bad", "not UTF-8"),
        ("a.pdf", b"x" * (30 * 1024 * 1024 + 1), "larger than 30 MB"),
    ],
)
def test_unreadable_files(name, data, message):
    with pytest.raises(SourceError, match=message):
        page_count(name, data)


def test_safe_filenames():
    used: set[str] = set()
    assert safe_filename("PS 3 (week 2).PDF", used) == "PS-3-week-2.pdf"
    assert safe_filename("PS 3 (week 2).pdf", used) == "PS-3-week-2-2.pdf"
    assert safe_filename("../../etc/passwd", used) == "passwd"
    assert safe_filename("..\\..\\win.txt", used) == "win.txt"
    assert safe_filename(".hidden", used) == "hidden"
    assert safe_filename("???.md", used) == "file.md"


def test_blank_pages_add_nothing(folder):
    path, write = folder
    write("blank.png", png())
    fake = FakeModel({Transcription: [{"markdown": "  "}]})
    normalized, pages = ingest(path, [Material("blank.png", "problem_set", False), Material("notes.md", "problem_set", False)], fake)
    assert normalized.problem_set == "[notes.md, page 1]\n\n# Notes\n\n$v = v_0 + at$"
    assert len(pages) == 2
