"""Model client: OpenAI Responses API (stateless replay) and a scripted client for tests."""

from __future__ import annotations

import copy
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict

from shipharness.cost import Usage, usage_from_openai

ErrorClass = Literal["retry", "abort_billing", "abort_auth", "abort_other"]
_BILLING_CODES = {
    "insufficient_quota",
    "credit_balance_exhausted",
    "organization_spend_limit_exceeded",
    "project_spend_limit_exceeded",
    "organization_usage_limit_exceeded",
    "billing_hard_limit_reached",
}


class ModelResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    output_items: list[dict[str, Any]]
    usage: Usage
    status: str = "completed"
    text: str = ""
    incomplete_reason: str | None = None
    service_tier: str | None = None  # the tier the response reports; it sets the call's price


class ModelClient(Protocol):
    def respond(
        self,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        model: str,
        effort: str,
        max_output_tokens: int,
        service_tier: str,
    ) -> ModelResponse: ...


class OpenAIModelClient:
    """Responses API with store=False: the full transcript is replayed each turn."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def respond(
        self,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        model: str,
        effort: str,
        max_output_tokens: int,
        service_tier: str,
    ) -> ModelResponse:
        response = self.client.responses.create(
            model=model,
            input=input_items,
            tools=tools,
            tool_choice="auto",
            parallel_tool_calls=False,
            reasoning={"effort": effort},
            max_output_tokens=max_output_tokens,
            store=False,
            service_tier=service_tier,
        )
        items = [item.model_dump(exclude_none=True) for item in response.output]
        details = getattr(response, "incomplete_details", None)
        tier = getattr(response, "service_tier", None)
        return ModelResponse(
            output_items=items,
            usage=usage_from_openai(response.usage),
            status=str(getattr(response, "status", "completed") or "completed"),
            text=str(getattr(response, "output_text", "") or ""),
            incomplete_reason=getattr(details, "reason", None) if details else None,
            service_tier=str(tier) if tier else None,
        )


def _error_code(exc: BaseException) -> str | None:
    code = getattr(exc, "code", None)
    if code:
        return str(code)
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error", body)
        if isinstance(error, dict) and error.get("code"):
            return str(error["code"])
    return None


def classify_openai_error(exc: BaseException) -> ErrorClass:
    """Decide whether an API error is retried or ends the arm (billing 429s are never retried)."""
    status = getattr(exc, "status_code", None)
    name = type(exc).__name__
    if status == 429:
        return "abort_billing" if _error_code(exc) in _BILLING_CODES else "retry"
    if status in (401, 403):
        return "abort_auth"
    if (isinstance(status, int) and status >= 500) or name in (
        "APIConnectionError",
        "APITimeoutError",
        "InternalServerError",
    ):
        return "retry"
    return "abort_other"


# ---- scripted client (tests and replays of model behaviour in unit tests) ----------------------


@dataclass
class Step:
    output_items: list[dict[str, Any]] = field(default_factory=list)
    usage: Usage = field(default_factory=lambda: Usage(input_tokens=100, output_tokens=20))
    text: str = ""
    error: BaseException | None = None
    service_tier: str | None = None  # the tier the scripted response reports


def tool_step(name: str, usage: Usage | None = None, **arguments: Any) -> Step:
    item = {
        "type": "function_call",
        "id": f"fc_{uuid.uuid4().hex[:8]}",
        "call_id": f"call_{uuid.uuid4().hex[:8]}",
        "name": name,
        "arguments": json.dumps(arguments),
    }
    return Step(output_items=[item], **({"usage": usage} if usage else {}))


def text_step(text: str) -> Step:
    item = {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": text}],
    }
    return Step(output_items=[item], text=text)


class ScriptedModelClient:
    """Returns pre-defined steps in order and records what it was sent."""

    def __init__(self, steps: list[Step]) -> None:
        self.steps = list(steps)
        self.inputs: list[list[dict[str, Any]]] = []
        self.tools: list[list[dict[str, Any]]] = []

    def respond(
        self,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        model: str,
        effort: str,
        max_output_tokens: int,
        service_tier: str,
    ) -> ModelResponse:
        self.inputs.append(copy.deepcopy(input_items))
        self.tools.append(copy.deepcopy(tools))
        step = self.steps.pop(0) if self.steps else text_step("(script exhausted)")
        if step.error is not None:
            raise step.error
        return ModelResponse(
            output_items=step.output_items,
            usage=step.usage,
            text=step.text,
            service_tier=step.service_tier,
        )
