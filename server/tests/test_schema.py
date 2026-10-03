import json

from kedami_server.export_schema import OUTPUT
from kedami_server.lesson import Lesson


def test_committed_schema_is_current():
    """The renderer's types are generated from this file, so it must match the models."""
    assert json.loads(OUTPUT.read_text()) == Lesson.model_json_schema(mode="serialization")
