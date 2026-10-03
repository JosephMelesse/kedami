import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from pydantic import BaseModel, ValidationError

from kedami_server import model
from kedami_server.lesson import Answer
from kedami_server.model import FALLBACK_BETA, ModelError, _reply_text, call_model, output_schema


class Reply(BaseModel):
    answer: Answer


GOOD = {"answer": {"kind": "numeric", "value": 2.36, "rel_tolerance": 0.01, "unit": "s"}}


def sse(text: str, stop_reason: str = "end_turn") -> str:
    events = [
        ("message_start", {"type": "message_start", "message": {
            "id": "msg_1", "type": "message", "role": "assistant", "model": "m", "content": [],
            "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}}}),
        ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}}),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                           "usage": {"output_tokens": 5}}),
        ("message_stop", {"type": "message_stop"}),
    ]
    return "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events)


@pytest.fixture
def api(monkeypatch):
    """Route the real SDK client to a fake API that records requests."""
    state = SimpleNamespace(requests=[], status=200, body=sse(json.dumps(GOOD)), waits=[])
    monkeypatch.setattr(model.time, "sleep", state.waits.append)

    def handle(request: httpx2.Request) -> httpx2.Response:
        state.requests.append(request)
        if state.status != 200:
            return httpx2.Response(state.status, json={"type": "error", "error": {"type": "x", "message": "nope"}})
        return httpx2.Response(200, text=state.body, headers={"content-type": "text/event-stream"})

    fake = anthropic.Anthropic(
        api_key="test", max_retries=0, http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handle))
    )
    monkeypatch.setattr(model, "_client", fake)
    return state


def test_generate_request_shape(api):
    reply = call_model("generate", system="sys", prompt="hello", output=Reply)
    assert reply.answer.value == 2.36
    request = api.requests[0]
    body = json.loads(request.content)
    assert body["model"] == "claude-sonnet-5-5"
    assert body["stream"] is True
    assert body["fallbacks"] == "default"
    assert FALLBACK_BETA in request.headers["anthropic-beta"]
    assert body["output_config"]["effort"] == "high"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["messages"] == [{"role": "user", "content": "hello"}]
    assert body["system"] == "sys"


def test_small_check_has_no_effort_or_fallback(api):
    call_model("small_check", system="sys", prompt=[{"type": "text", "text": "hi"}], output=Reply)
    request = api.requests[0]
    body = json.loads(request.content)
    assert body["model"] == "claude-haiku-4-5"
    assert "fallbacks" not in body and "effort" not in body["output_config"]
    assert FALLBACK_BETA not in request.headers.get("anthropic-beta", "")


def test_reply_failing_validation_raises(api):
    api.body = sse(json.dumps({"answer": {"kind": "choice", "options": ["a", "b"], "correct_index": 5}}))
    with pytest.raises(ValidationError):
        call_model("generate", system="s", prompt="p", output=Reply)


@pytest.mark.parametrize("stop_reason, message", [("refusal", "declined"), ("max_tokens", "cut off")])
def test_unusable_stop_reasons(api, stop_reason, message):
    api.body = sse(json.dumps(GOOD), stop_reason)
    with pytest.raises(ModelError, match=message):
        call_model("generate", system="s", prompt="p", output=Reply)


@pytest.mark.parametrize("status, message", [(401, "API key"), (400, "returned 400"), (529, "returned 529")])
def test_api_errors_become_model_errors(api, status, message):
    api.status = status
    with pytest.raises(ModelError, match=message):
        call_model("generate", system="s", prompt="p", output=Reply)


def test_reply_text_uses_only_text_after_a_fallback_switch():
    content = [
        SimpleNamespace(type="text", text='{"partial'),
        SimpleNamespace(type="fallback"),
        SimpleNamespace(type="thinking"),
        SimpleNamespace(type="text", text='{"a": '),
        SimpleNamespace(type="text", text="1}"),
    ]
    assert _reply_text(content) == '{"a": 1}'


def test_schema_has_no_const_and_closes_objects():
    schema = json.dumps(output_schema(Reply))
    assert '"const"' not in schema
    assert '"enum": ["numeric"]' in schema
    assert '"additionalProperties": true' not in schema


def test_every_generation_schema_converts():
    from kedami_server.generation.schemas import (
        Extraction,
        HintDraft,
        HintJudgements,
        HintReplacements,
        Plan,
        SectionDraft,
        Solutions,
    )

    for output in (Extraction, Plan, SectionDraft, HintDraft, HintReplacements, HintJudgements, Solutions):
        schema = json.dumps(output_schema(output))
        assert '"const"' not in schema and '"oneOf"' not in schema and 'discriminator' not in schema, output.__name__


@pytest.mark.parametrize("workspace, expected", [("wrkspc_test", "wrkspc_test"), ("", None), (None, None)])
def test_workspace_header_comes_from_the_environment(monkeypatch, workspace, expected):
    seen = []

    def handle(request):
        seen.append(request.headers.get("anthropic-workspace-id"))
        return httpx2.Response(200, text=sse(json.dumps(GOOD)), headers={"content-type": "text/event-stream"})

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    if workspace is None:
        monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
    else:
        monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", workspace)
    monkeypatch.setattr(model, "_client", None)
    real = anthropic.Anthropic
    monkeypatch.setattr(
        anthropic,
        "Anthropic",
        lambda **kwargs: real(**kwargs, http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handle))),
    )
    call_model("small_check", system="s", prompt="p", output=Reply)
    assert seen == [expected]


def test_schema_too_complex_is_retried_without_enforcement(api):
    responses = [
        httpx2.Response(400, json={"type": "error", "error": {"type": "invalid_request_error",
                        "message": "The compiled grammar is too large, which would cause performance issues."}}),
        httpx2.Response(200, text=sse("```json\n" + json.dumps(GOOD) + "\n```"), headers={"content-type": "text/event-stream"}),
    ]
    requests = []

    def handle(request):
        requests.append(json.loads(request.content))
        return responses.pop(0)

    model._client = anthropic.Anthropic(
        api_key="test", max_retries=0, http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handle))
    )
    reply = call_model("generate", system="sys", prompt="p", output=Reply)
    assert reply.answer.value == 2.36
    first, second = requests
    assert first["output_config"]["format"]["type"] == "json_schema"
    assert "format" not in second["output_config"] and second["output_config"]["effort"] == "high"
    assert second["system"].startswith("sys\n\nReply with only a JSON object")
    assert '"enum": ["numeric"]' in second["system"]


def test_other_bad_requests_are_not_retried(api):
    api.status = 400
    with pytest.raises(ModelError, match="returned 400"):
        call_model("generate", system="s", prompt="p", output=Reply)
    assert len(api.requests) == 1


def test_every_property_is_required_in_the_sent_schema():
    def objects(node):
        if isinstance(node, dict):
            if "properties" in node:
                yield node
            for value in node.values():
                yield from objects(value)
        elif isinstance(node, list):
            for item in node:
                yield from objects(item)

    from kedami_server.generation.schemas import SectionDraft

    for node in objects(output_schema(SectionDraft)):
        assert set(node["required"]) == set(node["properties"])


def test_section_schema_has_no_unions_of_objects():
    """Nested unions made the API's compiled grammar too large. Only "value or null" is allowed."""
    from kedami_server.generation.schemas import SectionDraft

    def unions(node):
        if isinstance(node, dict):
            if "anyOf" in node:
                yield node["anyOf"]
            for value in node.values():
                yield from unions(value)
        elif isinstance(node, list):
            for item in node:
                yield from unions(item)

    for variants in unions(output_schema(SectionDraft)):
        assert len(variants) == 2 and {"type": "null"} in variants, variants


def stream_error(kind="overloaded_error"):
    event = {"type": "error", "error": {"type": kind, "message": "Overloaded"}}
    return f"event: error\ndata: {json.dumps(event)}\n\n"


def scripted(api, bodies):
    """Reply with each body in turn: an SSE string for a 200, or an int status code."""
    replies = list(bodies)

    def handle(request):
        api.requests.append(request)
        reply = replies.pop(0)
        if isinstance(reply, int):
            return httpx2.Response(reply, json={"type": "error", "error": {"type": "x", "message": "nope"}})
        return httpx2.Response(200, text=reply, headers={"content-type": "text/event-stream"})

    model._client = anthropic.Anthropic(
        api_key="test", max_retries=0, http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handle))
    )


def test_overload_mid_stream_is_retried(api):
    scripted(api, [stream_error(), sse(json.dumps(GOOD))])
    assert call_model("generate", system="s", prompt="p", output=Reply).answer.value == 2.36
    assert len(api.requests) == 2
    assert api.waits == [5]


def test_server_errors_are_retried_with_growing_waits(api):
    scripted(api, [529, 500, stream_error("api_error"), sse(json.dumps(GOOD))])
    call_model("generate", system="s", prompt="p", output=Reply)
    assert api.waits == [5, 15, 45]


def test_persistent_overload_fails_after_the_last_wait(api):
    scripted(api, [stream_error()] * 4)
    with pytest.raises(ModelError, match="Overloaded"):
        call_model("generate", system="s", prompt="p", output=Reply)
    assert len(api.requests) == 4


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_client_errors_are_not_retried(api, status):
    scripted(api, [status])
    with pytest.raises(ModelError):
        call_model("generate", system="s", prompt="p", output=Reply)
    assert len(api.requests) == 1 and api.waits == []


def test_second_solve_request_shape(api):
    call_model("second_solve", system="s", prompt="p", output=Reply)
    body = json.loads(api.requests[0].content)
    assert (body["model"], body["output_config"]["effort"], body["fallbacks"]) == ("claude-opus-5-5", "high", "default")
