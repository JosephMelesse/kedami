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
    state = SimpleNamespace(requests=[], status=200, body=sse(json.dumps(GOOD)))

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
    )

    for output in (Extraction, Plan, SectionDraft, HintDraft, HintReplacements, HintJudgements):
        schema = json.dumps(output_schema(output))
        assert '"const"' not in schema and '"oneOf"' not in schema and 'discriminator' not in schema, output.__name__
