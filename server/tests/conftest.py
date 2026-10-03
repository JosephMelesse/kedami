import copy
import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample-lesson.json"


@pytest.fixture
def lesson_data() -> dict:
    return copy.deepcopy(json.loads(FIXTURE.read_text()))
