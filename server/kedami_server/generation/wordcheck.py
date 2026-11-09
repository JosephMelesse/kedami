"""The word check: did formatting a reference page change any of its words? See architecture/pipeline.md.

Only letters and digits are compared, in order, so the model may add structure and fix spacing freely.
Lines the model says it dropped are taken out of the page first, and each must match a whole line.
"""

import re
import unicodedata
from collections import Counter

# A code fence's language is Markdown syntax, not part of the page's words.
FENCE_LANGUAGE = re.compile(r"^([ \t]*(?:`{3,}|~{3,}))[ \t]*[^\s`~]*[ \t]*$", re.MULTILINE)


def letters(text: str) -> str:
    """Text reduced to its letters and digits. NFKC makes a ligature, a superscript, and an accent compare by value."""
    return "".join(ch for ch in unicodedata.normalize("NFKC", FENCE_LANGUAGE.sub(r"\1", text)) if ch.isalnum())


def same_words(page: str, markdown: str, dropped: list[str]) -> bool:
    """Whether the reply has the page's letters and digits, once the dropped lines are taken out.

    A line can appear more than once, such as a page number that is also a table cell, and the reply doesn't say
    which one it dropped. So this searches for any choice of lines to drop that makes the two the same.
    """
    lines = [key for key in (letters(line) for line in page.splitlines()) if key]
    reply = letters(markdown)
    # A dropped line of only punctuation can't affect the comparison.
    to_drop = Counter(key for key in map(letters, dropped) if key)
    slots = {key: slot for slot, key in enumerate(to_drop)}
    start = (0, 0, tuple(to_drop.values()))

    stack, seen = [start], {start}
    while stack:
        line, position, left = stack.pop()
        if line == len(lines):
            if position == len(reply) and not any(left):
                return True
            continue
        key = lines[line]
        next_states = []
        if reply.startswith(key, position):
            next_states.append((line + 1, position + len(key), left))
        slot = slots.get(key)
        if slot is not None and left[slot]:
            next_states.append((line + 1, position, (*left[:slot], left[slot] - 1, *left[slot + 1 :])))
        for state in next_states:
            if state not in seen:
                seen.add(state)
                stack.append(state)
    return False
