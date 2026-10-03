"""Small builders for generation test data."""

from kedami_server.generation.schemas import Extraction, Plan


def extraction(problems=None, concepts=("vectors", "gravity", "range")) -> Extraction:
    return Extraction.model_validate(
        {
            "concepts": [{"id": c, "name": c.title(), "summary": f"About {c}."} for c in concepts],
            "problems": problems
            if problems is not None
            else [
                {
                    "source_ref": "PS1 #1",
                    "prompt": "A ball is thrown at $10$ m/s.",
                    "parts": [{"label": "(a)", "prompt": "Find $v_x$."}, {"label": "(b)", "prompt": "Find $v_y$."}],
                    "concepts": ["vectors"],
                },
                {
                    "source_ref": "PS1 #2",
                    "prompt": "",
                    "parts": [{"label": "2", "prompt": "How far does it go?"}],
                    "concepts": ["vectors", "gravity", "range"],
                },
            ],
        }
    )


def plan(*sections, title="Projectiles") -> Plan:
    return Plan.model_validate(
        {
            "title": title,
            "sections": [
                {"title": name, "goal": f"Learn {name}.", "concepts": list(concepts)} for name, concepts in sections
            ],
        }
    )
