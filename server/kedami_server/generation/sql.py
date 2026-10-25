"""Query answers belong to SQL lessons, which agent mode doesn't build."""

from ..lesson import Section
from .assemble import SectionError


def refuse_queries(section: Section) -> None:
    """Outside SQL lessons, a query answer is refused."""
    for key, answer in _answers(section.model_dump()):
        if answer["kind"] == "query":
            raise SectionError(f"{key} has a query answer, which only SQL lessons use")


def _answers(section: dict):
    """Each answer in a dumped section, with a key naming where it is."""
    for block in section["blocks"]:
        if block["type"] == "checkpoint":
            yield block["id"], block["answer"]
        elif block["type"] == "problem":
            for part in block["parts"]:
                yield f"{block['source_ref']} part {part['label']}", part["answer"]
