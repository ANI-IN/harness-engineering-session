"""The separate, blinded reviewer (A3's separate evaluator).

One Responses API call with strict structured output (`responses.parse(text_format=Review)`),
`store=False`, under its own cost scope. `max_output_tokens` is sized so the worst case of the call
stays within the review cap. An incomplete or refused response, an API error, or a cap gives no
verdict (`review=None`), never a guessed one.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from shipharness.config import ModelPrice
from shipharness.cost import CapExceeded, CostTracker, usage_from_openai
from shipharness.reviewer.models import Review, ReviewInput
from shipharness.runner.model import classify_openai_error
from shipharness.tracing import Tracer

REVIEWER_PROMPT = """\
You are a senior engineer reviewing a change to a multi-tenant web service before it is merged. \
You see the ticket, the grading criteria, and the diff, nothing else. Judge only what the diff \
ships. List every finding first (file, line if known, severity, which criterion, a short comment), \
then rate the tenant isolation risk, then give the verdict: reject if there is any blocker or the \
ticket is not implemented, accept otherwise. Keep the summary to three sentences."""

MAX_DIFF_CHARS = 80_000
MAX_REVIEW_OUTPUT_TOKENS = 8_000
MIN_REVIEW_OUTPUT_TOKENS = 1_000
_ERRORS = {
    "abort_auth": "OpenAI rejected the request: check OPENAI_API_KEY (authentication failed).",
    "abort_billing": "OpenAI billing limit reached (quota or spend limit).",
    "abort_other": "OpenAI request failed",
    "retry": "OpenAI request kept failing after retries",
}

ReviewStatus = Literal["ok", "incomplete", "refused", "error", "cap"]


@dataclass(frozen=True)
class ReviewOutcome:
    review: Review | None
    status: ReviewStatus
    cost_usd: float
    detail: str = ""


def max_output_tokens_for(price: ModelPrice, est_input_tokens: int, limit_usd: float) -> int:
    """Largest output budget whose worst case (all input uncached) fits within `limit_usd`."""
    input_usd = est_input_tokens * max(price.input, price.cache_write) / 1e6
    room = (limit_usd - input_usd) * 1e6 / price.output
    return max(0, min(MAX_REVIEW_OUTPUT_TOKENS, int(room)))


def build_messages(inp: ReviewInput) -> list[dict[str, Any]]:
    diff = inp.diff
    if len(diff) > MAX_DIFF_CHARS:
        cut = len(diff) - MAX_DIFF_CHARS
        diff = diff[:MAX_DIFF_CHARS] + f"\n[diff truncated: {cut} more characters not shown]\n"
    user = f"Ticket:\n{inp.task}\n\nGrading criteria:\n{inp.grading_criteria}\n\nDiff:\n{diff}"
    return [
        {"role": "developer", "content": [{"type": "input_text", "text": REVIEWER_PROMPT}]},
        {"role": "user", "content": [{"type": "input_text", "text": user}]},
    ]


def _refused(response: Any) -> bool:
    for item in getattr(response, "output", None) or []:
        for part in getattr(item, "content", None) or []:
            if getattr(part, "type", "") == "refusal":
                return True
    return False


def run_review(
    inp: ReviewInput,
    cost: CostTracker,
    tracer: Tracer,
    *,
    client: Any,
    model: str,
    effort: str = "medium",
    key: str | None = None,
    limit_usd: float | None = None,
    max_attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> ReviewOutcome:
    """Review one blinded diff. `client` is an OpenAI client (built with max_retries=0)."""
    key = key or f"review-{uuid.uuid4().hex[:8]}"
    scope = cost.scope("review", key, limit_usd or cost.caps.review)
    messages = build_messages(inp)
    est_input = len(json.dumps(messages)) // 3 + 200
    budget = max_output_tokens_for(cost.prices.get(model), est_input, scope.limit_usd)
    if budget < MIN_REVIEW_OUTPUT_TOKENS:
        return ReviewOutcome(None, "cap", 0.0, f"review cap ${scope.limit_usd} too small")
    try:
        # The worst case is held against every cap under one lock until the call settles, so a
        # concurrent review or arm cannot spend the same room (CostTracker.reserve).
        reservation = cost.reserve(scope, model, est_input, budget)
    except CapExceeded as exc:
        return ReviewOutcome(None, "cap", 0.0, str(exc))
    with tracer.child("reviewer", "chain", blinded=True, model=model) as handle:
        attempt = 0
        while True:
            try:
                response = client.responses.parse(
                    model=model,
                    input=messages,
                    text_format=Review,
                    reasoning={"effort": effort},
                    max_output_tokens=budget,
                    store=False,
                )
                break
            except Exception as exc:  # noqa: BLE001 - classified; the raw message may hold a key
                kind = classify_openai_error(exc)
                attempt += 1
                if kind != "retry" or attempt >= max_attempts:
                    cost.release(reservation)
                    status = getattr(exc, "status_code", "n/a")
                    detail = _ERRORS[kind]
                    if kind == "abort_other":
                        detail = f"{detail}: {type(exc).__name__} (status {status})"
                    return ReviewOutcome(None, "error", scope.spent_usd, detail)
                sleep(float(2 ** (attempt - 1)))
            except BaseException:
                cost.release(reservation)
                raise
        try:
            # No tier is requested (the reviewer stays on the standard tier); the ledger keeps
            # the tier the response reports, and the price follows it.
            tier = getattr(response, "service_tier", None)
            cost.settle(reservation, usage_from_openai(response.usage), str(tier) if tier else None)
        except CapExceeded as exc:
            return ReviewOutcome(None, "cap", round(scope.spent_usd, 6), str(exc))
        spent = round(scope.spent_usd, 6)
        parsed = getattr(response, "output_parsed", None)
        if getattr(response, "status", "completed") == "incomplete":
            details = getattr(response, "incomplete_details", None)
            reason = getattr(details, "reason", "") if details else ""
            return ReviewOutcome(None, "incomplete", spent, f"incomplete: {reason}")
        if _refused(response):
            return ReviewOutcome(None, "refused", spent, "the model refused to review")
        if not isinstance(parsed, Review):
            return ReviewOutcome(None, "error", spent, "no structured review in the response")
        handle.set_outputs({"verdict": parsed.verdict, "risk": parsed.tenant_isolation_risk})
        return ReviewOutcome(parsed, "ok", spent)


def review(inp: ReviewInput, cost: CostTracker, tracer: Tracer, **kwargs: Any) -> Review | None:
    """The Review, or None when there is no verdict."""
    return run_review(inp, cost, tracer, **kwargs).review
