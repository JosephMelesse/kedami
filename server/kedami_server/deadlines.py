"""Due dates: reading them strictly, and the overdue rule. See Deadlines in architecture/ui.md."""

import re
from collections.abc import Iterable
from datetime import date
from typing import Annotated

from pydantic import AfterValidator, StrictStr

_FORMAT = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", re.ASCII)


def parse_due_date(text: str) -> str:
    """The date if it is a real calendar date written as YYYY-MM-DD. `date.fromisoformat` alone also takes 20261101."""
    if not _FORMAT.fullmatch(text):
        raise ValueError("A due date is written YYYY-MM-DD.")
    date.fromisoformat(text)
    return text


DueDate = Annotated[StrictStr, AfterValidator(parse_due_date)]


def today() -> str:
    """The date on this machine, which is the student's own."""
    return date.today().isoformat()


def is_overdue(due_date: str | None, done: bool, on: str) -> bool:
    """Whether the date has passed on the given day. YYYY-MM-DD strings sort as dates do."""
    return due_date is not None and not done and due_date < on


def soonest_by_folder(parents: dict[int, int | None], due: Iterable[tuple[int, str]]) -> dict[int, str]:
    """The soonest date in each folder, counting subfolders at any depth, from unfinished lessons' folders and dates."""
    soonest: dict[int, str] = {}
    for folder_id, due_date in due:
        folder: int | None = folder_id
        while folder is not None:
            if folder not in soonest or due_date < soonest[folder]:
                soonest[folder] = due_date
            folder = parents[folder]
    return soonest
