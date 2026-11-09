"""The word check: formatting may add structure, but no word may change. See architecture/pipeline.md."""

import pytest

from kedami_server.generation.wordcheck import same_words

PAGE = "Lecture 4\nThe focal length of a thin\nlens is out-\ngoing.\n12"


@pytest.mark.parametrize(
    "markdown",
    [
        "Lecture 4\nThe focal length of a thin lens is out-going.\n12",
        "# Lecture 4\n\nThe focal length of a thin lens is outgoing.\n\n12",
        "**Lecture 4**\n\n- The *focal length* of a `thin` lens is outgoing.\n\n> 12",
        "| Lecture 4 |\n|---|\n| The focal length of a thin lens is outgoing. |\n\n12",
    ],
)
def test_structure_spacing_and_punctuation_are_ignored(markdown):
    assert same_words(PAGE, markdown, [])


@pytest.mark.parametrize(
    "markdown",
    [
        "Lecture 4\nThe focal length of a thin lens is outgoing.\n13",  # A changed number.
        "Lecture 4\nThe focal length of a thick lens is outgoing.\n12",  # A changed word.
        "Lecture 4\nThe focal length of a lens is outgoing.\n12",  # A missing word.
        "Lecture 4\nThe focal length of a very thin lens is outgoing.\n12",  # An added word.
        "The focal length of a thin lens is outgoing.\nLecture 4\n12",  # Reordered.
        "lecture 4\nThe focal length of a thin lens is outgoing.\n12",  # A changed case.
        "",
    ],
)
def test_any_change_to_the_words_fails(markdown):
    assert not same_words(PAGE, markdown, [])


def test_a_dropped_line_is_taken_out_of_the_page_first():
    markdown = "The focal length of a thin lens is outgoing."
    assert same_words(PAGE, markdown, ["Lecture 4", "12"])


def test_a_dropped_line_can_differ_in_spacing_and_punctuation():
    assert same_words("Lecture  4 -\nBody text.", "Body text.", ["Lecture 4"])


def test_a_dropped_line_must_match_a_whole_line():
    # "Lecture" is only part of a line.
    assert not same_words(PAGE, "4\nThe focal length of a thin lens is outgoing.\n12", ["Lecture"])


def test_a_dropped_line_not_on_the_page_fails():
    assert not same_words("Body text.", "Body text.", ["Page 3"])


def test_a_dropped_line_still_in_the_reply_fails():
    assert not same_words("Page 3\nBody text.", "Page 3\nBody text.", ["Page 3"])


def test_a_dropped_line_listed_twice_needs_two_on_the_page():
    assert not same_words("Page 3\nBody text.", "Body text.", ["Page 3", "Page 3"])
    assert same_words("Page 3\nBody text.\nPage 3", "Body text.", ["Page 3", "Page 3"])


@pytest.mark.parametrize(
    "page, markdown",
    [
        ("12\nRow one\nRow two\n12", "12\nRow one\nRow two"),  # The footer goes and the same line in the body stays.
        ("12\nRow one\nRow two\n12", "Row one\nRow two\n12"),  # The header goes and the same line at the end stays.
        ("A\n12\nB\n12\nC\n12", "A\nB\n12\nC\n12"),  # The first of three.
        ("A\n12\nB\n12\nC\n12", "A\n12\nB\n12\nC"),  # The last of three.
    ],
)
def test_a_dropped_line_that_appears_more_than_once_can_be_any_of_them(page, markdown):
    assert same_words(page, markdown, ["12"])


def test_a_repeated_dropped_line_doesnt_hide_a_change():
    assert not same_words("12\nRow one\n12", "Row two\n12", ["12"])


@pytest.mark.parametrize(
    "page, markdown",
    [
        ("efficient ﬁeld", "efficient field"),  # A ligature.
        ("x² + y²", "x2 + y2"),  # A superscript counts as its digit.
        ("café", "café"),  # The same letter, written two ways.
        (" Therefore", "⇒ Therefore"),  # A private-use symbol isn't a letter.
        ("θ = 30° and π", "θ = 30° and π"),  # Greek letters count.
    ],
)
def test_the_same_characters_written_differently_match(page, markdown):
    assert same_words(page, markdown, [])


def test_greek_letters_are_compared():
    assert not same_words("θ = 30", "φ = 30", [])


def test_turning_a_symbol_into_latex_fails():
    assert not same_words("θ = 30", "$\\theta = 30$", [])


def test_a_code_fence_language_is_markdown_syntax():
    assert same_words("x = 1\ny = 2", "```python\nx = 1\ny = 2\n```", [])
    assert same_words("x = 1", "~~~ python\nx = 1\n~~~", [])


def test_a_fence_doesnt_hide_a_changed_line_of_code():
    assert not same_words("x = 1", "```python\nx = 2\n```", [])
    assert not same_words("Body", "``` Body added", [])


def test_windows_line_ends_count_as_line_ends():
    assert same_words("Page 3\r\nBody text.\r\n", "Body text.", ["Page 3"])


def test_a_page_with_every_line_dropped_is_blank():
    assert same_words("Lecture 4\n12", "", ["Lecture 4", "12"])


def test_a_dropped_line_of_only_punctuation_is_harmless():
    assert same_words("---\nBody text.", "Body text.", ["---"])
    assert same_words("Body text.", "Body text.", [""])


def test_many_repeats_stay_quick():
    page = "\n".join(["12", "Row"] * 200)
    assert same_words(page, "Row" * 200, ["12"] * 200)
    assert not same_words(page, "Row" * 199, ["12"] * 200)
