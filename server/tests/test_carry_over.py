import copy

import pytest

from kedami_server import db
from kedami_server.lesson import Lesson
from kedami_server.progress import (
    CORRECT,
    IN_PROGRESS,
    MARKED_DONE,
    NOT_STARTED,
    Record,
    carried_over,
    carry_over,
    load_all,
    save,
)
from kedami_server.storage import seed_sample


@pytest.fixture
def lesson(lesson_data):
    return Lesson.model_validate(lesson_data)


def blocks(data):
    return {b["id"]: b for s in data["sections"] for b in s["blocks"]}


def changed(lesson_data, edit) -> Lesson:
    data = copy.deepcopy(lesson_data)
    edit(blocks(data))
    return Lesson.model_validate(data)


def part(part_id="a", block_id="ps3-4", **fields):
    return Record(block_id=block_id, part_id=part_id, **fields)


def test_checkpoint_progress_resets(lesson):
    assert carried_over(Record(block_id="components-check", part_id=None, status=CORRECT, last_response="10"), lesson) is None


@pytest.mark.parametrize("block_id, part_id", [("ps9-9", "a"), ("ps3-4", "z")])
def test_progress_for_parts_that_no_longer_exist_is_deleted(lesson, block_id, part_id):
    assert carried_over(part(part_id, block_id, status=CORRECT, last_response="2.36"), lesson) is None


def test_marked_done_stays_marked_done(lesson_data):
    new = changed(lesson_data, lambda b: b["ps3-4"]["parts"][0]["answer"].update(value=99.0))
    record = part(status=MARKED_DONE, last_response="2.36", attempts=1)
    assert carried_over(record, new) == record


def test_correct_answer_that_still_matches_stays_correct(lesson):
    record = part(status=CORRECT, last_response="2.36", attempts=2)
    assert carried_over(record, lesson) == record


def test_correct_answer_that_no_longer_matches_becomes_wrong(lesson_data):
    new = changed(lesson_data, lambda b: b["ps3-4"]["parts"][0]["answer"].update(value=3.1))
    result = carried_over(part(status=CORRECT, last_response="2.36", attempts=2), new)
    assert (result.status, result.last_response, result.attempts) == (IN_PROGRESS, "2.36", 2)


def test_wrong_answer_that_now_matches_becomes_correct(lesson_data):
    new = changed(lesson_data, lambda b: b["ps3-4"]["parts"][0]["answer"].update(value=3.1))
    assert carried_over(part(status=IN_PROGRESS, last_response="3.1", attempts=1), new).status == CORRECT


def test_response_that_no_longer_fits_the_answer_form_is_wrong(lesson_data):
    def to_choice(b):
        b["ps3-4"]["parts"][0]["answer"] = {"kind": "choice", "options": ["2.36 s", "3 s"], "correct_index": 0}
    result = carried_over(part(status=CORRECT, last_response="2.36"), changed(lesson_data, to_choice))
    assert result.status == IN_PROGRESS


def test_self_check_judgment_stands(lesson):
    record = part("d", status=CORRECT, last_response={"text": "sin 2θ", "correct": True}, attempts=1)
    assert carried_over(record, lesson) == record


def test_self_check_that_became_a_number_is_rechecked(lesson_data):
    def to_numeric(b):
        b["ps3-4"]["parts"][3]["answer"] = {"kind": "numeric", "value": 1.0, "rel_tolerance": 0.01, "unit": None}
    record = part("d", status=CORRECT, last_response={"text": "x", "correct": True})
    assert carried_over(record, changed(lesson_data, to_numeric)).status == IN_PROGRESS


def test_hints_used_is_capped_and_can_reset_the_state(lesson_data):
    new = changed(lesson_data, lambda b: b["ps3-4"]["parts"][0].update(hints=[]))
    assert carried_over(part(status=IN_PROGRESS, hints_used=2), new) == part(status=NOT_STARTED, hints_used=0)
    fewer = changed(lesson_data, lambda b: b["ps3-4"]["parts"][0].update(hints=["one"]))
    assert carried_over(part(status=IN_PROGRESS, hints_used=2), fewer) == part(status=IN_PROGRESS, hints_used=1)


def test_carrying_over_twice_changes_nothing_more(lesson_data):
    new = changed(lesson_data, lambda b: b["ps3-4"]["parts"][0]["answer"].update(value=3.1))
    once = carried_over(part(status=CORRECT, last_response="2.36", hints_used=1), new)
    assert carried_over(once, new) == once


def test_carry_over_in_the_database(tmp_path, lesson_data):
    db.init(tmp_path)
    seed_sample(tmp_path)
    with db.connect(tmp_path) as conn:
        save(conn, "sample", part("a", status=CORRECT, last_response="2.36"))
        save(conn, "sample", part("b", status=MARKED_DONE))
        save(conn, "sample", Record(block_id="apex-check", part_id=None, status=CORRECT, last_response=0))
        save(conn, "sample", part("5", "ps3-5", status=CORRECT, last_response=[0, 2]))
    data = copy.deepcopy(lesson_data)
    blocks(data)["ps3-4"]["parts"][0]["answer"]["value"] = 3.1
    for section in data["sections"]:
        section["blocks"] = [b for b in section["blocks"] if b["id"] != "ps3-5"]
    new = Lesson.model_validate(data)
    with db.connect(tmp_path) as conn:
        carry_over(conn, "sample", new)
        records = {(r.block_id, r.part_id): r.status for r in load_all(conn, "sample")}
    assert records == {("ps3-4", "a"): IN_PROGRESS, ("ps3-4", "b"): MARKED_DONE}
