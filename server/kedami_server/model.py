"""The one function every model call goes through.

Requests structured output against a Pydantic model's JSON Schema and validates the reply.
The API key is read by the Anthropic client from ANTHROPIC_API_KEY, loaded from server/.env.
A key not scoped to a workspace also needs ANTHROPIC_WORKSPACE_ID there.
"""

import copy
import json
import os
import re
from typing import Any, TypeVar

import anthropic
from anthropic.lib._parse._transform import transform_schema
from pydantic import BaseModel, ValidationError

from .config import MODEL_ROLES

T = TypeVar("T", bound=BaseModel)

FALLBACK_BETA = "server-side-fallback-2026-07-01"
GRAMMAR_TOO_LARGE = "compiled grammar is too large"

_client: anthropic.Anthropic | None = None


class ModelError(Exception):
    """A model call that failed in a way a retry of the same request won't fix."""


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        # The SDK sends a workspace only for profile and federation logins, not for a plain API key.
        workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
        headers = {"anthropic-workspace-id": workspace} if workspace else None
        _client = anthropic.Anthropic(max_retries=4, default_headers=headers)
    return _client


def call_model(role: str, *, system: str, prompt: list[dict] | str, output: type[T]) -> T:
    """Call the model for `role` and return its reply parsed as `output`.

    Raises ModelError for refusals, truncation, and API errors, and pydantic's
    ValidationError when the reply doesn't satisfy the model's validators.
    """
    config = MODEL_ROLES[role]
    schema = output_schema(output)
    request: dict[str, Any] = {
        "model": config.model,
        "max_tokens": config.max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
        "output_config": {"format": {"type": "json_schema", "schema": schema}},
    }
    if config.effort:
        request["output_config"]["effort"] = config.effort
    if config.fallbacks:
        request["betas"] = [FALLBACK_BETA]
        request["fallbacks"] = "default"

    try:
        message = _send(request)
    except anthropic.BadRequestError as error:
        if GRAMMAR_TOO_LARGE not in str(error):
            raise _model_error(error) from error
        # The schema is too complex to enforce. Ask for it in the instructions instead;
        # the reply is still validated below and retried by the caller if it fails.
        del request["output_config"]["format"]
        if not request["output_config"]:
            del request["output_config"]
        request["system"] = f"{system}\n\n{_schema_instructions(schema)}"
        try:
            message = _send(request)
        except anthropic.AnthropicError as retry_error:
            raise _model_error(retry_error) from retry_error
    except anthropic.AnthropicError as error:
        raise _model_error(error) from error

    if message.stop_reason == "refusal":
        raise ModelError("The model declined this request.")
    if message.stop_reason == "max_tokens":
        raise ModelError("The model's reply was cut off at the token limit.")
    return output.model_validate_json(_strip_fence(_reply_text(message.content)))


def _send(request: dict):
    with client().beta.messages.stream(**request) as stream:
        return stream.get_final_message()


def _model_error(error: anthropic.AnthropicError) -> ModelError:
    if isinstance(error, anthropic.AuthenticationError):
        return ModelError("The Anthropic API key is missing or invalid. Set ANTHROPIC_API_KEY in server/.env.")
    if isinstance(error, anthropic.APIConnectionError):
        return ModelError("Could not reach the Anthropic API.")
    if isinstance(error, anthropic.APIStatusError):
        return ModelError(f"The Anthropic API returned {error.status_code}: {error.message}")
    # Includes a missing API key, which the client reports before sending anything.
    return ModelError(str(error))


def _schema_instructions(schema: dict) -> str:
    return (
        "Reply with only a JSON object, with no other text, that matches this JSON Schema. "
        "Include every property; use null for a property that does not apply.\n\n"
        + json.dumps(schema)
    )


def _strip_fence(text: str) -> str:
    """Drop a Markdown code fence around a JSON reply, if the model added one."""
    match = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*", text, re.DOTALL)
    return match.group(1) if match else text


def _reply_text(content: list) -> str:
    """The JSON reply: text after the last fallback switch, if a fallback model took over."""
    last_switch = max((i for i, block in enumerate(content) if block.type == "fallback"), default=-1)
    return "".join(block.text for block in content[last_switch + 1 :] if block.type == "text")


def output_schema(model: type[BaseModel]) -> dict:
    """The JSON Schema sent for structured output.

    Single-value Literal fields become one-item enums, since the API's schema subset
    has no `const`, and Pydantic's discriminator hints are dropped (each variant's
    `type` enum already tells them apart). Every property is required, since optional
    properties enlarge the compiled grammar; nullable fields carry "not used". Other
    unsupported constraints are moved into descriptions by the SDK and enforced here by
    validating the reply.
    """
    return transform_schema(_prepare(copy.deepcopy(model.model_json_schema())))


def _prepare(node: Any) -> Any:
    if isinstance(node, dict):
        if "const" in node:
            node["enum"] = [node.pop("const")]
        node.pop("discriminator", None)
        if isinstance(node.get("properties"), dict):
            node["required"] = list(node["properties"])
        for value in node.values():
            _prepare(value)
    elif isinstance(node, list):
        for item in node:
            _prepare(item)
    return node


__all__ = ["ModelError", "ValidationError", "call_model", "output_schema"]
