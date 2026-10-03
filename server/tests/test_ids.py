import pytest

from kedami_server.ids import slugify


@pytest.mark.parametrize(
    "text, expected",
    [
        ("PS3 #4", "ps3-4"),
        ("(a)", "a"),
        ("4(b)(ii)", "4-b-ii"),
        ("  Problem 12  ", "problem-12"),
        ("Part A", "part-a"),
        ("§2.1", "2-1"),
        ("ps3-4", "ps3-4"),
    ],
)
def test_slugify(text, expected):
    assert slugify(text) == expected


def test_slugify_is_stable_on_repeat():
    assert slugify(slugify("PS3 #4")) == slugify("PS3 #4")


@pytest.mark.parametrize("text", ["", "   ", "#", "()", "αβ"])
def test_slugify_rejects_text_with_no_alphanumerics(text):
    with pytest.raises(ValueError):
        slugify(text)
