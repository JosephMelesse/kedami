"""The one function every model call goes through.

Requests structured output against a Pydantic model's JSON Schema and validates the reply.
The API key is read by the Anthropic client from ANTHROPIC_API_KEY, loaded from server/.env.
"""

import copy
from typing import Any, TypeVar

import anthropic
from anthropic.lib._parse._transform import transform_schema
from pydantic import BaseModel, ValidationError

from .config import MODEL_ROLES

T = TypeVar("T", bound=BaseModel)

FALLBACK_BETA = "server-side-fallback-2026-07-01"

_client: anthropic.Anthropic | None = None


class ModelError(Exception):
    """A model call that failed in a way a retry of the same request won't fix."""


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(max_retries=4)
    return _client


def call_model(role: str, *, system: str, prompt: list[dict] | str, output: type[T]) -> T:
    """Call the model for `role` and return its reply parsed as `output`.

    Raises ModelError for refusals, truncation, and API errors, and pydantic's
    ValidationError when the reply doesn't satisfy the model's validators.
    """
    config = MODEL_ROLES[role]
    request: dict[str, Any] = {
        "model": config.model,
        "max_tokens": config.max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
        "output_config": {"format": {"type": "json_schema", "schema": output_schema(output)}},
    }
    if config.effort:
        request["output_config"]["effort"] = config.effort
    if config.fallbacks:
        request["betas"] = [FALLBACK_BETA]
        request["fallbacks"] = "default"

    try:
        with client().beta.messages.stream(**request) as stream:
            message = stream.get_final_message()
    except anthropic.AuthenticationError as error:
        raise ModelError("The Anthropic API key is missing or invalid. Set ANTHROPIC_API_KEY in server/.env.") from error
    except anthropic.APIConnectionError as error:
        raise ModelError("Could not reach the Anthropic API.") from error
    except anthropic.APIStatusError as error:
        raise ModelError(f"The Anthropic API returned {error.status_code}: {error.message}") from error
    except anthropic.AnthropicError as error:
        # Includes a missing API key, which the client reports before sending anything.
        raise ModelError(str(error)) from error

    if message.stop_reason == "refusal":
        raise ModelError("The model declined this request.")
    if message.stop_reason == "max_tokens":
        raise ModelError("The model's reply was cut off at the token limit.")
    return output.model_validate_json(_reply_text(message.content))


def _reply_text(content: list) -> str:
    """The JSON reply: text after the last fallback switch, if a fallback model took over."""
    last_switch = max((i for i, block in enumerate(content) if block.type == "fallback"), default=-1)
    return "".join(block.text for block in content[last_switch + 1 :] if block.type == "text")


def output_schema(model: type[BaseModel]) -> dict:
    """The JSON Schema sent for structured output.

    Single-value Literal fields become one-item enums, since the API's schema subset
    has no `const`, and Pydantic's discriminator hints are dropped (each variant's
    `type` enum already tells them apart). Other unsupported constraints are moved
    into descriptions by the SDK and enforced here by validating the reply.
    """
    return transform_schema(_prepare(copy.deepcopy(model.model_json_schema())))


def _prepare(node: Any) -> Any:
    if isinstance(node, dict):
        if "const" in node:
            node["enum"] = [node.pop("const")]
        node.pop("discriminator", None)
        for value in node.values():
            _prepare(value)
    elif isinstance(node, list):
        for item in node:
            _prepare(item)
    return node


__all__ = ["ModelError", "ValidationError", "call_model", "output_schema"]
