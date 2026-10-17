"""Search the imported LeetCode problems by number or words, for the DSA problem picker.

The number, slug, title, and difficulty of every imported problem are kept in memory, read from
`leetcode.jsonl` on the first search and again whenever the file changes. See
architecture/code-problems.md, Picking problems.
"""

import re
import threading
from dataclasses import dataclass
from pathlib import Path

from .import_leetcode import OUTPUT

MAX_RESULTS = 8

# Each line the import writes starts with these fields, so the index is read without parsing whole lines.
_ENTRY = re.compile(r'^\{"number": (\d+), "slug": "([a-z0-9-]+)", "difficulty": "(Easy|Medium|Hard)"')
_ROMAN = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}
_TOKEN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Entry:
    number: int
    slug: str
    title: str
    difficulty: str

    @property
    def words(self) -> list[str]:
        return self.slug.split("-")


def title_from_slug(slug: str) -> str:
    """The dataset has slugs, not titles: "two-sum-ii-input-array-is-sorted" is "Two Sum II Input Array Is
    Sorted". LeetCode's punctuation is lost, but the title derives back to the slug."""
    return " ".join(word.upper() if word in _ROMAN else word[:1].upper() + word[1:] for word in slug.split("-"))


_cache: dict[Path, tuple[tuple[int, int], list[Entry]]] = {}
_lock = threading.Lock()


def entries(data_dir: Path) -> list[Entry]:
    """Every imported problem, by number. Empty if nothing has been imported."""
    path = data_dir / OUTPUT
    try:
        stat = path.stat()
    except FileNotFoundError:
        return []
    stamp = (stat.st_mtime_ns, stat.st_size)
    with _lock:
        cached = _cache.get(path)
        if cached is None or cached[0] != stamp:
            cached = (stamp, _read(path))
            _cache[path] = cached
        return cached[1]


def _read(path: Path) -> list[Entry]:
    found = []
    with path.open(encoding="utf-8") as lines:
        for line in lines:
            match = _ENTRY.match(line)
            if match:
                number, slug, difficulty = int(match[1]), match[2], match[3]
                found.append(Entry(number, slug, title_from_slug(slug), difficulty))
    return found


def search(data_dir: Path, query: str) -> list[Entry]:
    """Up to MAX_RESULTS problems matching a number or words, closest first.

    A number matches problems whose number starts with it, the exact number first. Words match problems
    where every word typed starts a word of the slug, in any order; a number among them may instead be the
    problem's number. The slug that is exactly the words comes first, then slugs starting with them, then
    the rest; within each, slugs with fewer words come first, as the closer match.
    """
    text = query.strip().lower()
    if text.isdigit():
        hits = [e for e in entries(data_dir) if str(e.number).startswith(text)]
        return sorted(hits, key=lambda e: (str(e.number) != text, e.number))[:MAX_RESULTS]
    tokens = _TOKEN.findall(text)
    if not tokens:
        return []
    hits = [e for e in entries(data_dir) if all(_matches(token, e) for token in tokens)]
    words = "-".join(tokens)
    return sorted(
        hits, key=lambda e: (e.slug != words, not e.slug.startswith(words), len(e.words), e.number)
    )[:MAX_RESULTS]


def _matches(token: str, entry: Entry) -> bool:
    return any(word.startswith(token) for word in entry.words) or (token.isdigit() and str(entry.number) == token)
