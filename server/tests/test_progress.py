import pytest

from kedami_server import db
from kedami_server.lesson import Lesson
from kedami_server.progress import (
    CORRECT,
    IN_PROGRESS,
    MARKED_DONE,
    NOT_STARTED,
    Conflict,
    Record,
    after_check,
    after_hints,
    after_mark_done,
    load,
    load_all,
    problems_done,
    save,
)
from kedami_server.storage import seed_sample

PART = Record(block_id="ps3-4", part_id="a")
CHECKPOINT = Record(block_id="components-check", part_id=None)


# Checking


def test_wrong_then_right():
    wrong = after_check(PART, False, "3")
    assert (wrong.status, wrong.attempts, wrong.last_response) == (IN_PROGRESS, 1, "3")
    right = after_check(wrong, True, "2.36")
    assert (right.status, right.attempts, right.last_response) == (CORRECT, 2, "2.36")


def test_attempts_are_unlimited():
    record = PART
    for _ in range(50):
        record = after_check(record, False, "0")
    assert record.attempts == 50
    assert record.status == IN_PROGRESS


@pytest.mark.parametrize("status", [CORRECT, MARKED_DONE])
def test_no_checks_once_done(status):
    with pytest.raises(Conflict):
        after_check(Record(block_id="b", part_id="a", status=status), True, "1")


def test_checkpoints_follow_the_same_states():
    assert after_check(CHECKPOINT, False, "1").status == IN_PROGRESS
    assert after_check(CHECKPOINT, True, "10").status == CORRECT


# Hints


def test_hint_starts_progress():
    record = after_hints(PART, 1, 2)
    assert (record.status, record.hints_used) == (IN_PROGRESS, 1)


def test_repeated_hint_request_is_idempotent():
    once = after_hints(PART, 1, 2)
    assert after_hints(once, 1, 2) == once
    assert after_hints(after_hints(once, 2, 2), 1, 2).hints_used == 2


@pytest.mark.parametrize("count", [0, 3, -1])
def test_hint_count_must_exist(count):
    with pytest.raises(Conflict):
        after_hints(PART, count, 2)


def test_hint_does_not_change_a_done_part():
    correct = Record(block_id="b", part_id="a", status=CORRECT)
    assert after_hints(correct, 1, 2).status == CORRECT


def test_part_with_no_hints_cannot_reveal_one():
    with pytest.raises(Conflict):
        after_hints(PART, 1, 0)


# Mark done


def test_mark_done_and_undo_from_not_started():
    marked = after_mark_done(PART, True)
    assert marked.status == MARKED_DONE
    assert after_mark_done(marked, False).status == NOT_STARTED


def test_undo_returns_to_in_progress_after_a_hint():
    marked = after_mark_done(after_hints(PART, 1, 2), True)
    assert after_mark_done(marked, False).status == IN_PROGRESS


def test_undo_returns_to_wrong_after_a_wrong_answer():
    wrong = after_check(PART, False, "3")
    undone = after_mark_done(after_mark_done(wrong, True), False)
    assert undone == wrong


def test_mark_done_is_idempotent():
    marked = after_mark_done(PART, True)
    assert after_mark_done(marked, True) == marked


def test_undo_without_mark_changes_nothing():
    wrong = after_check(PART, False, "3")
    assert after_mark_done(wrong, False) == wrong


def test_correct_part_cannot_be_marked_done():
    with pytest.raises(Conflict):
        after_mark_done(after_check(PART, True, "2.36"), True)


def test_checkpoint_cannot_be_marked_done():
    with pytest.raises(Conflict):
        after_mark_done(CHECKPOINT, True)


# Completion


@pytest.fixture
def lesson(lesson_data):
    return Lesson.model_validate(lesson_data)


def done(block_id, part_id, status=CORRECT):
    return Record(block_id=block_id, part_id=part_id, status=status)


def test_problem_is_done_only_when_every_part_is(lesson):
    three_parts = [done("ps3-4", p) for p in "abc"]
    assert problems_done(lesson, three_parts) == 0
    assert problems_done(lesson, three_parts + [done("ps3-4", "d", MARKED_DONE)]) == 1


def test_in_progress_parts_and_checkpoints_do_not_count(lesson):
    records = [done("ps3-5", "5", IN_PROGRESS), done("components-check", None), done("apex-check", None)]
    assert problems_done(lesson, records) == 0


def test_all_problems_done(lesson):
    records = [done("ps3-4", p) for p in "abcd"] + [done("ps3-5", "5", MARKED_DONE)]
    assert problems_done(lesson, records) == 2


def test_progress_for_parts_no_longer_in_the_lesson_is_ignored(lesson):
    assert problems_done(lesson, [done("ps9-1", "a"), done("ps3-5", "zz")]) == 0


# Storage


@pytest.fixture
def data_dir(tmp_path):
    db.init(tmp_path)
    seed_sample(tmp_path)
    return tmp_path


def test_unsaved_part_loads_as_not_started(data_dir):
    with db.connect(data_dir) as conn:
        assert load(conn, "sample", "ps3-4", "a") == PART


def test_save_and_load_round_trip(data_dir):
    record = after_check(after_hints(PART, 2, 2), False, {"text": "x", "correct": False})
    with db.connect(data_dir) as conn:
        saved = save(conn, "sample", record)
    with db.connect(data_dir) as conn:
        assert load(conn, "sample", "ps3-4", "a") == saved
    assert saved.updated is not None


def test_saving_twice_updates_one_row(data_dir):
    with db.connect(data_dir) as conn:
        save(conn, "sample", after_check(PART, False, "1"))
        save(conn, "sample", after_check(after_check(PART, False, "1"), True, "2.36"))
        saved = save(conn, "sample", after_hints(CHECKPOINT, 1, 2))
        records = load_all(conn, "sample")
    assert [(r.block_id, r.part_id, r.status) for r in records] == [
        ("components-check", None, IN_PROGRESS),
        ("ps3-4", "a", CORRECT),
    ]
    assert saved.part_id is None


def test_progress_needs_an_indexed_lesson(data_dir):
    with pytest.raises(Exception, match="FOREIGN KEY"):
        with db.connect(data_dir) as conn:
            save(conn, "missing", PART)
