"""Small builders for generation test data."""

from kedami_server.generation.passages import TEXT, Passage
from kedami_server.generation.schemas import Extraction, Plan

UNITS = ("vectors", "gravity", "range")


def passages(*texts, file="reference.md", kind=TEXT) -> list[Passage]:
    """Text passages numbered from 1, one per page of one file."""
    return [Passage(number=n, kind=kind, file=file, page=n, text=t) for n, t in enumerate(texts, start=1)]


# One passage for each default unit, in order.
PASSAGES = passages(*(f"About {u}." for u in UNITS))


def extraction(problems=None, units=UNITS, skipped=(), last=None) -> Extraction:
    """Each unit covers one passage, the first unit the first passage. `last` stretches the last unit to that
    passage, for a reference with more passages than units."""
    spans = [[n, n] for n in range(1, len(units) + 1)]
    if last is not None:
        spans[-1][1] = last
    return Extraction.model_validate(
        {
            "units": [
                {"id": u, "title": u.title(), "summary": f"About {u}.", "first": first, "last": end}
                for u, (first, end) in zip(units, spans)
            ],
            "skipped": list(skipped),
            "problems": problems
            if problems is not None
            else [
                {
                    "source_ref": "PS1 #1",
                    "prompt": "A ball is thrown at $10$ m/s.",
                    "parts": [{"label": "(a)", "prompt": "Find $v_x$."}, {"label": "(b)", "prompt": "Find $v_y$."}],
                    "units": ["vectors"],
                },
                {
                    "source_ref": "PS1 #2",
                    "prompt": "",
                    "parts": [{"label": "2", "prompt": "How far does it go?"}],
                    "units": ["vectors", "gravity", "range"],
                },
            ],
        }
    )


def plan(*sections, title="Projectiles") -> Plan:
    return Plan.model_validate(
        {
            "title": title,
            "sections": [{"title": name, "goal": f"Learn {name}.", "units": list(units)} for name, units in sections],
        }
    )
