"""The MCP server's tools, called the way Claude Code calls them, against the app in process."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from mcp.server.mcpserver.exceptions import ToolError

from kedami_server import mcp
from kedami_server.lesson import Lesson

from ..generation.factories import section_one, section_two
from .conftest import AUTH, PAGES, extraction_body, number, plan_body

TOOLS = {
    "list_waiting_lessons", "start_lesson", "save_pages", "save_extraction", "save_plan", "save_section",
    "save_hints", "get_questions", "save_verification", "finish_lesson", "fail_lesson",
    "get_solution_request", "save_solution", "get_simulation_request", "save_simulation", "get_selection",
}


def call(name, **arguments):
    result = asyncio.run(mcp.server.call_tool(name, arguments))
    return json.loads(result.content[0].text)


@pytest.fixture
def connected(agent, monkeypatch):
    monkeypatch.setattr(mcp, "client", lambda: TestClient(agent.client.app, headers=AUTH))
    return agent


def test_every_tool_is_offered():
    tools = asyncio.run(mcp.server.list_tools())
    assert {t.name for t in tools} == TOOLS
    assert all(t.description for t in tools)


def test_the_server_instructions_say_when_to_call_get_selection():
    # Claude Code may hold back tool descriptions, but always shows these.
    assert "get_selection" in mcp.INSTRUCTIONS and '"this"' in mcp.INSTRUCTIONS
    assert "don't give the final answer" in mcp.INSTRUCTIONS


def test_tool_inputs_carry_the_lesson_schemas():
    tools = {t.name: t for t in asyncio.run(mcp.server.list_tools())}
    schema = json.dumps(tools["save_section"].input_schema)
    assert '"blocks"' in schema and "worked_example" in schema
    assert '"concepts"' in json.dumps(tools["save_extraction"].input_schema)


def test_a_whole_lesson_through_the_tools(connected):
    lesson_id = connected.new_lesson()
    assert [w["id"] for w in call("list_waiting_lessons")["lessons"]] == [lesson_id]
    assert call("start_lesson", lesson_id=lesson_id)["subject"] == "physics"
    call("save_pages", lesson_id=lesson_id, files=PAGES["files"])
    call("save_extraction", lesson_id=lesson_id, extraction=extraction_body())
    sections = call("save_plan", lesson_id=lesson_id, plan=plan_body())["sections"]
    assert [s["number"] for s in sections] == [1, 2]
    targets = call("save_section", lesson_id=lesson_id, number=1, section=section_one())["targets"]
    call("save_section", lesson_id=lesson_id, number=2, section=section_two())
    dropped = call("save_hints", lesson_id=lesson_id, number=1, items=[
        {"target": targets[1]["key"], "hints": ["Use cosine.", "It is 8.66 m/s."]}
    ])["dropped"]
    assert [d["hint"] for d in dropped] == ["It is 8.66 m/s."]
    questions = call("get_questions", lesson_id=lesson_id, number=1)
    assert questions["materials"][0].endswith("normalized/problem-set.md")
    verified = call("save_verification", lesson_id=lesson_id, number=1, solutions=[number("ps1-1/a", 8.66)])
    assert verified["verified"] == ["ps1-1/a"]
    call("finish_lesson", lesson_id=lesson_id)

    lesson = Lesson.model_validate(connected.lesson(lesson_id)["lesson"])
    part = lesson.find_block("ps1-1").parts[0]
    assert (part.hints, part.verified) == (["Use cosine."], True)


def test_a_refusal_is_a_tool_error_with_the_reason(connected):
    lesson_id = connected.new_lesson()
    call("start_lesson", lesson_id=lesson_id)
    with pytest.raises(ToolError, match="Save the pages first"):
        call("save_extraction", lesson_id=lesson_id, extraction=extraction_body())


def test_an_invalid_section_is_refused_before_it_reaches_kedami(connected):
    with pytest.raises(ToolError):
        call("save_section", lesson_id="x", number=1, section={"blocks": []})


def test_without_the_environment_the_tools_say_how_to_connect(monkeypatch):
    monkeypatch.delenv("KEDAMI_PORT", raising=False)
    monkeypatch.setenv("KEDAMI_TOKEN", "${KEDAMI_TOKEN}")
    with pytest.raises(ToolError, match="Terminal screen"):
        call("list_waiting_lessons")


def test_an_unreachable_server_says_so(monkeypatch):
    monkeypatch.setenv("KEDAMI_PORT", "1")
    monkeypatch.setenv("KEDAMI_TOKEN", "t")
    with pytest.raises(ToolError, match="isn't reachable"):
        call("list_waiting_lessons")
