from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from shipharness.config import DEFAULT_PRICES_FILE, Prices
from shipharness.cost import Caps, CostTracker
from shipharness.datasets.names import rule_label
from shipharness.reviewer import Review, ReviewInput, run_review
from shipharness.reviewer.criteria import DEFAULT_CRITERIA, grading_criteria
from shipharness.reviewer.review import REVIEWER_PROMPT, max_output_tokens_for
from shipharness.tracing import NullTracer

PRICES = Prices.load(DEFAULT_PRICES_FILE)

GOOD = Review(
    findings=[
        {
            "file": "app/api/issues.py",
            "line": 12,
            "severity": "blocker",
            "criterion": "R1 tenant isolation",
            "comment": "query is not filtered by org",
        }
    ],
    tenant_isolation_risk="likely",
    verdict="reject",
    summary="Leaks other orgs' issues.",
)


def usage(inp: int = 1200, out: int = 300) -> SimpleNamespace:
    return SimpleNamespace(
        input_tokens=inp,
        output_tokens=out,
        input_tokens_details=SimpleNamespace(cached_tokens=0, cache_write_tokens=0),
        output_tokens_details=SimpleNamespace(reasoning_tokens=100),
    )


class FakeResponses:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def fake_client(*responses: Any) -> SimpleNamespace:
    return SimpleNamespace(responses=FakeResponses(list(responses)))


def completed(parsed: Review | None = GOOD, **kw: Any) -> SimpleNamespace:
    base = dict(
        output_parsed=parsed,
        status="completed",
        usage=usage(),
        output=[],
        incomplete_details=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def tracker(tmp_path: Path, review_cap: float = 0.04) -> CostTracker:
    return CostTracker(
        PRICES, Caps(0.2, review_cap, 2.5, 2.5, 25.0), tmp_path / "ledger.jsonl", session_id="t"
    )


INPUT = ReviewInput(
    task="Add cursor pagination.", diff="diff --git a/x b/x\n", grading_criteria="R1"
)
MODEL = "gpt-5.6-luna"


def test_review_input_has_no_arm_field() -> None:
    with pytest.raises(ValidationError):
        ReviewInput(task="t", diff="d", grading_criteria="c", arm="bare")  # type: ignore[call-arg]


def test_successful_review_returns_the_parsed_review_and_records_cost(tmp_path: Path) -> None:
    client = fake_client(completed())
    cost = tracker(tmp_path)
    outcome = run_review(INPUT, cost, NullTracer(), client=client, model="gpt-5.6-luna")
    assert outcome.status == "ok"
    assert outcome.review == GOOD
    assert outcome.cost_usd > 0
    [call] = client.responses.calls
    assert call["store"] is False
    assert call["model"] == "gpt-5.6-luna"
    assert call["text_format"] is Review
    ledger = [json.loads(x) for x in (tmp_path / "ledger.jsonl").read_text().splitlines()]
    assert ledger[0]["kind"] == "review"


def test_request_contains_task_criteria_and_diff_but_no_arm_label(tmp_path: Path) -> None:
    client = fake_client(completed())
    run_review(INPUT, tracker(tmp_path), NullTracer(), client=client, model="gpt-5.6-luna")
    sent = json.dumps(client.responses.calls[0]["input"])
    assert "Add cursor pagination." in sent and "diff --git a/x b/x" in sent
    assert REVIEWER_PROMPT.split(".")[0] in sent
    for label in ("bare", "harness arm", "arm="):
        assert label not in sent


def test_incomplete_response_gives_no_verdict(tmp_path: Path) -> None:
    resp = completed(
        parsed=None,
        status="incomplete",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
    )
    outcome = run_review(
        INPUT, tracker(tmp_path), NullTracer(), client=fake_client(resp), model="gpt-5.6-luna"
    )
    assert outcome.review is None
    assert outcome.status == "incomplete"
    assert outcome.cost_usd > 0  # tokens were still billed


def test_refusal_gives_no_verdict(tmp_path: Path) -> None:
    refusal = SimpleNamespace(
        type="message", content=[SimpleNamespace(type="refusal", refusal="I can't help")]
    )
    resp = completed(parsed=None, output=[refusal])
    outcome = run_review(
        INPUT, tracker(tmp_path), NullTracer(), client=fake_client(resp), model="gpt-5.6-luna"
    )
    assert outcome.review is None and outcome.status == "refused"


def test_api_error_gives_no_verdict_and_no_key_in_detail(tmp_path: Path) -> None:
    class AuthError(Exception):
        status_code = 401

    key = "sk-" + "proj-" + "Z9y8X7w6" * 4
    client = fake_client(AuthError(f"bad key {key}"))
    outcome = run_review(INPUT, tracker(tmp_path), NullTracer(), client=client, model=MODEL)
    assert outcome.review is None and outcome.status == "error"
    assert key not in outcome.detail and "OPENAI_API_KEY" in outcome.detail


def test_rate_limit_is_retried(tmp_path: Path) -> None:
    class RateLimited(Exception):
        status_code = 429

    client = fake_client(RateLimited("slow down"), completed())
    sleeps: list[float] = []
    outcome = run_review(
        INPUT,
        tracker(tmp_path),
        NullTracer(),
        client=client,
        model="gpt-5.6-luna",
        sleep=sleeps.append,
    )
    assert outcome.status == "ok" and sleeps == [1.0]


def test_max_output_tokens_keep_the_worst_case_under_the_review_cap() -> None:
    price = PRICES.get("gpt-5.6-luna")
    tokens = max_output_tokens_for(price, est_input_tokens=10_000, limit_usd=0.04)
    worst = (10_000 * max(price.input, price.cache_write) + tokens * price.output) / 1e6
    assert worst <= 0.04
    assert tokens <= 8000


def test_review_that_cannot_fit_the_cap_is_not_sent(tmp_path: Path) -> None:
    client = fake_client(completed())
    outcome = run_review(
        INPUT, tracker(tmp_path, review_cap=0.0001), NullTracer(), client=client, model=MODEL
    )
    assert outcome.status == "cap" and outcome.review is None
    assert client.responses.calls == []


def test_long_diffs_are_truncated_with_a_note(tmp_path: Path) -> None:
    client = fake_client(completed())
    big = ReviewInput(task="t", diff="+x\n" * 100_000, grading_criteria="c")
    run_review(big, tracker(tmp_path), NullTracer(), client=client, model="gpt-5.6-luna")
    sent = json.dumps(client.responses.calls[0]["input"])
    assert "[diff truncated" in sent
    assert len(sent) < 120_000


def test_grading_criteria_come_from_security_and_architecture(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SECURITY.md").write_text("# Security\nR1: filter by org.\n")
    (tmp_path / "ARCHITECTURE.md").write_text("# Architecture\nR6: api never imports db.\n")
    text = grading_criteria(tmp_path)
    assert "R1: filter by org." in text and "R6: api never imports db." in text
    assert text == grading_criteria(tmp_path)  # stable


def test_grading_criteria_fall_back_to_the_house_rules(tmp_path: Path) -> None:
    assert grading_criteria(tmp_path / "missing") == DEFAULT_CRITERIA
    for rule in ("R1", "R2", "R3", "R4", "R5", "R6", "R7"):
        assert f"- {rule_label(rule)}. " in DEFAULT_CRITERIA
    assert not re.search(r"\bR[1-8]\b", DEFAULT_CRITERIA)  # never a bare code
