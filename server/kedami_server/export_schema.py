"""Write the lesson JSON Schema that the renderer's TypeScript types are generated from.

Uses serialization mode, so fields with defaults are required: the server always sends them.
"""

import json
from pathlib import Path

from .lesson import Lesson

OUTPUT = Path(__file__).resolve().parents[1] / "schema" / "lesson.schema.json"


def main() -> None:
    schema = Lesson.model_json_schema(mode="serialization")
    OUTPUT.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
