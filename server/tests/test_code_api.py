"""Saving code, recording a Submit, and flagging tests for a code part. See architecture/code-problems.md."""

import json

import pytest
from fastapi.testclient import TestClient

from kedami_server import db, test_flags
from kedami_server.import_leetcode import OUTPUT
from kedami_server.app import create_app
from kedami_server.config import Settings
from kedami_server.lesson import Lesson
from kedami_server.storage import seed_sample

AUTH = {"Authorization": "Bearer t"}
BASE = "/lessons/sample/blocks"
STARTER = "class Solution:\n    def twoSum(self, nums, target):\n        "
CODE = "class Solution:\n    def twoSum(self, nums, target):\n        return [0, 1]\n"
TESTS = [
    {"args": "nums = [3, 3], target = 6", "expected": "[0, 1]", "compare": "equal"},
    {"args": "nums = [2, 7], target = 9", "expected": "[0, 1]", "compare": "equal"},
]


def code_block(tests=TESTS) -> dict:
    answer = {
        "kind": "code", "platform": "leetcode", "number": 1, "title": "Two Sum", "slug": "two-sum",
        "difficulty": "Easy", "method": "twoSum", "starter_code": STARTER, "tests": tests,
    }
    return {"type": "problem", "id": "leetcode-1", "source_ref": "LeetCode #1", "prompt": "",
            "parts": [{"id": "1", "label": "1", "prompt": "Given an array...", "answer": answer, "hints": [],
                       "verified": False}]}


def write_lesson(data_dir, block) -> Lesson:
    path = data_dir / "lessons" / "sample.json"
    data = json.loads(path.read_text())
    data["sections"][0]["blocks"] = [b for b in data["sections"][0]["blocks"] if b["id"] != "leetcode-1"] + [block]
    path.write_text(json.dumps(data))
    return Lesson.model_validate(data)


@pytest.fixture
def data_dir(tmp_path):
    db.init(tmp_path)
    seed_sample(tmp_path)
    write_lesson(tmp_path, code_block())
    return tmp_path


@pytest.fixture
def client(data_dir):
    return TestClient(create_app(Settings(port=0, token="t", data_dir=data_dir, allowed_origins=())))


def post(client, path, body):
    return client.post(f"{BASE}/{path}", json=body, headers=AUTH)


def state(client):
    body = client.get("/lessons/sample/progress", headers=AUTH).json()
    record = next((r for r in body["progress"] if r["block_id"] == "leetcode-1"), None)
    return record, body["flags"]


# Saving code


def test_saving_changed_code_starts_the_part(client):
    record = post(client, "leetcode-1/code", {"part_id": "1", "code": CODE}).json()["progress"]
    assert (record["status"], record["last_response"], record["attempts"]) == ("in_progress", CODE, 0)
    assert state(client)[0]["last_response"] == CODE


def test_saving_the_starter_code_records_nothing(client):
    assert post(client, "leetcode-1/code", {"part_id": "1", "code": STARTER}).json()["progress"]["status"] == "not_started"
    record = state(client)[0]
    assert (record["status"], record["last_response"]) == ("not_started", None)


def test_a_done_part_keeps_its_state_while_its_code_is_edited(client):
    post(client, "leetcode-1/submit", {"part_id": "1", "code": CODE, "passed": True})
    edited = post(client, "leetcode-1/code", {"part_id": "1", "code": CODE + "# faster\n"}).json()["progress"]
    assert (edited["status"], edited["last_response"]) == ("correct", CODE + "# faster\n")
    post(client, "leetcode-1/mark-done", {"part_id": "1", "done": False})


def test_code_over_the_limit_is_refused(client):
    assert post(client, "leetcode-1/code", {"part_id": "1", "code": "x" * 100_001}).status_code == 422


# Submitting


def test_a_failed_then_passing_submit_is_recorded(client):
    failed = post(client, "leetcode-1/submit", {"part_id": "1", "code": "bad", "passed": False}).json()["progress"]
    assert (failed["status"], failed["attempts"], failed["last_response"]) == ("in_progress", 1, "bad")
    passed = post(client, "leetcode-1/submit", {"part_id": "1", "code": CODE, "passed": True}).json()["progress"]
    assert (passed["status"], passed["attempts"], passed["last_response"]) == ("correct", 2, CODE)
    summary = client.get("/lessons", headers=AUTH).json()["lessons"][0]
    assert summary["problems_done"] >= 1


def test_a_correct_part_takes_no_more_submits(client):
    post(client, "leetcode-1/submit", {"part_id": "1", "code": CODE, "passed": True})
    assert post(client, "leetcode-1/submit", {"part_id": "1", "code": CODE, "passed": False}).status_code == 409


def test_a_marked_part_takes_no_submit_until_undone(client):
    post(client, "leetcode-1/mark-done", {"part_id": "1", "done": True})
    assert post(client, "leetcode-1/submit", {"part_id": "1", "code": CODE, "passed": True}).status_code == 409
    post(client, "leetcode-1/mark-done", {"part_id": "1", "done": False})
    assert post(client, "leetcode-1/submit", {"part_id": "1", "code": CODE, "passed": True}).status_code == 200


@pytest.mark.parametrize("body", [{"part_id": "1", "code": CODE, "passed": "yes"}, {"part_id": "1", "code": CODE}])
def test_a_submit_must_say_whether_it_passed(client, body):
    assert post(client, "leetcode-1/submit", body).status_code == 422


@pytest.mark.parametrize("route", ["code", "submit", "flags"])
def test_code_routes_refuse_parts_that_arent_code_problems(client, route):
    body = {"part_id": "a", "code": CODE, "passed": True, "action": "clear"}
    body = {k: v for k, v in body.items() if k in {"code": ("part_id", "code"), "submit": ("part_id", "code", "passed"),
                                                     "flags": ("part_id", "action")}[route]}
    response = post(client, f"ps3-4/{route}", body)
    assert response.status_code == 422 and "isn't a code problem" in response.json()["detail"]


def test_code_routes_need_a_real_part(client):
    assert post(client, "leetcode-1/code", {"part_id": "9", "code": CODE}).status_code == 404


# Flags


def flag(client, action, test=None):
    body = {"part_id": "1", "action": action} | ({"test": test} if test else {})
    return post(client, "leetcode-1/flags", body)


def test_flagging_and_unflagging_a_test(client):
    first = {"args": TESTS[0]["args"], "expected": TESTS[0]["expected"]}
    flags = flag(client, "flag", first).json()["flags"]
    assert flags == [{"block_id": "leetcode-1", "part_id": "1", **first}]
    assert flag(client, "flag", first).json()["flags"] == flags  # flagging again changes nothing
    assert state(client)[1] == flags
    assert flag(client, "unflag", first).json()["flags"] == []


def test_clearing_removes_every_flag_on_the_part(client):
    for test in TESTS:
        flag(client, "flag", {"args": test["args"], "expected": test["expected"]})
    assert len(state(client)[1]) == 2
    assert flag(client, "clear").json()["flags"] == []


@pytest.mark.parametrize(
    "test", [None, {"args": "nums = [1]", "expected": "[0]"}, {"args": TESTS[0]["args"], "expected": "[1, 0]"}]
)
def test_only_a_test_in_the_problem_can_be_flagged(client, test):
    response = flag(client, "flag", test)
    assert response.status_code == 422


def test_flagging_doesnt_change_the_parts_state(client):
    post(client, "leetcode-1/submit", {"part_id": "1", "code": "bad", "passed": False})
    flag(client, "flag", {"args": TESTS[0]["args"], "expected": TESTS[0]["expected"]})
    assert state(client)[0]["status"] == "in_progress"


def test_deleting_the_lesson_deletes_its_flags(client, data_dir):
    flag(client, "flag", {"args": TESTS[0]["args"], "expected": TESTS[0]["expected"]})
    assert client.delete("/lessons/sample", headers=AUTH).status_code == 200
    with db.connect(data_dir) as conn:
        assert conn.execute("SELECT COUNT(*) FROM test_flags").fetchone()[0] == 0


# Current tests

CURRENT = [{"args": "nums = [1, 2], target = 3", "expected": "[0, 1]", "compare": "unordered"}]


def write_import(data_dir, slug="two-sum", tests=CURRENT):
    problem = {"number": 1, "slug": slug, "difficulty": "Easy", "description": "Given...", "starter_code": STARTER,
               "method": "twoSum", "tests": tests}
    (data_dir / OUTPUT).write_text(json.dumps(problem) + "\n")


def served_tests(client):
    lesson = client.get("/lessons/sample", headers=AUTH).json()["lesson"]
    block = next(b for s in lesson["sections"] for b in s["blocks"] if b["id"] == "leetcode-1")
    return block["parts"][0]["answer"]["tests"]


def test_a_lesson_is_served_the_imports_current_tests_and_its_json_is_unchanged(client, data_dir):
    before = (data_dir / "lessons" / "sample.json").read_text()
    write_import(data_dir)
    assert served_tests(client) == CURRENT
    assert (data_dir / "lessons" / "sample.json").read_text() == before


@pytest.mark.parametrize("imported", [None, {"slug": "add-two-numbers"}, {"tests": []}, {"tests": [{"args": "x"}]}])
def test_the_lessons_copy_is_served_when_the_problem_isnt_imported_as_it_was(client, data_dir, imported):
    if imported is not None:
        write_import(data_dir, **imported)
    assert served_tests(client) == TESTS


def test_only_a_served_test_can_be_flagged(client, data_dir):
    write_import(data_dir)
    current = {"args": CURRENT[0]["args"], "expected": CURRENT[0]["expected"]}
    assert flag(client, "flag", current).status_code == 200
    assert flag(client, "flag", {"args": TESTS[0]["args"], "expected": TESTS[0]["expected"]}).status_code == 422
