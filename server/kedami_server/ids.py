"""Stable IDs derived from source references and part labels."""

import re

ID_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Lowercase, collapse every run of non-alphanumerics to one hyphen, trim hyphens.

    "PS3 #4" -> "ps3-4", "(a)" -> "a", "4(b)(ii)" -> "4-b-ii".
    """
    slug = _NON_ALNUM.sub("-", text.lower()).strip("-")
    if not slug:
        raise ValueError(f"cannot derive an id from {text!r}")
    return slug
