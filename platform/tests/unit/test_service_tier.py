"""OpenAI Fast tier (class profile): each call is priced by the tier the response reports, and the
worst case held before a call uses the requested tier's rates, so the caps stay correct.

Rates per 1M tokens for gpt-6-luna (config/prices.toml): Standard 0.10 / 0.01 / 0.125 / 0.50,
Fast 0.20 / 0.02 / 0.25 / 1.00 (input / cached input / cache write / output). A Fast request can be
downgraded to standard; the response then reports service_tier "default" and is charged standard.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from shipharness.config import DEFAULT_PRICES_FILE, Prices, Settings, UnknownModelPrice
from shipharness.cost import CapExceeded, Caps, CostTracker, Usage
from shipharness.runner.model import OpenAIModelClient, Step, tool_step

from .test_loop import run

PRICES = Prices.load(DEFAULT_PRICES_FILE)
USAGE = Usage(input_tokens=1000, cached_tokens=400, cache_write_tokens=100, output_tokens=200)
# uncached 500: Fast (500x0.20 + 400x0.02 + 100x0.25 + 200x1.00) / 1e6 = 0.000333
FAST_COST = 0.000333
# Standard (500x0.10 + 400x0.01 + 100x0.125 + 200x0.50) / 1e6 = 0.0001665
STANDARD_COST = 0.0001665
# Worst case of 1,000 input and 8,000 output tokens: Fast 1,000x0.25 + 8,000x1.00 = $0.00825;
# Standard 1,000x0.125 + 8,000x0.50 = $0.004125.
FAST_WORST, STANDARD_WORST = 0.00825, 0.004125


def tracker(tmp_path: Path, *, batch: float = 2.5) -> CostTracker:
    caps = Caps(run=10.0, review=0.04, session=2.5, batch=batch, experiment=25.0)
    return CostTracker(PRICES, caps, tmp_path / "ledger.jsonl", session_id="t")


def ledger(tmp_path: Path) -> list[dict[str, Any]]:
    lines = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def test_prices_file_has_fast_rates_for_the_agent_model_with_source_and_date() -> None:
    fast = PRICES.get("gpt-6-luna", "fast")
    assert (fast.input, fast.cached_input, fast.cache_write, fast.output) == (
        0.20,
        0.02,
        0.25,
        1.00,
    )
    standard = PRICES.get("gpt-6-luna")
    assert (standard.input, standard.output) == (0.10, 0.50)
    raw = tomllib.loads(DEFAULT_PRICES_FILE.read_text(encoding="utf-8"))
    table = raw["models"]["gpt-6-luna"]["fast"]
    assert table["source"] == "https://developers.openai.com/api/docs/pricing"
    assert table["verified"] == "2026-10-17"


def test_a_model_without_fast_rates_has_no_fast_price() -> None:
    with pytest.raises(UnknownModelPrice, match="Fast"):
        PRICES.get("gpt-5.6-luna", "fast")
    assert PRICES.get("gpt-5.6-luna").input == 0.20  # the standard price is unchanged


def test_settings_accept_the_fast_tier() -> None:
    assert Settings(_env_file=None, openai_service_tier="fast").openai_service_tier == "fast"


def test_a_call_the_response_reports_as_fast_is_charged_fast_rates(tmp_path: Path) -> None:
    t = tracker(tmp_path)
    scope = t.scope("run", "r-1", 10.0)
    held = t.reserve(scope, "gpt-6-luna", 1_000, 8_000, service_tier="fast")
    assert t.settle(held, USAGE, service_tier="fast") == pytest.approx(FAST_COST)
    [entry] = ledger(tmp_path)
    assert entry["service_tier"] == "fast"
    assert entry["cost_usd"] == pytest.approx(FAST_COST)


def test_a_downgraded_fast_request_is_charged_standard_rates(tmp_path: Path) -> None:
    t = tracker(tmp_path)
    scope = t.scope("run", "r-1", 10.0)
    held = t.reserve(scope, "gpt-6-luna", 1_000, 8_000, service_tier="fast")
    assert t.settle(held, USAGE, service_tier="default") == pytest.approx(STANDARD_COST)
    [entry] = ledger(tmp_path)
    assert entry["service_tier"] == "default"
    assert t.reserved_usd == 0.0


@pytest.mark.parametrize("reported", [None, "auto", "flex", "priority"])
def test_any_reported_tier_other_than_fast_is_charged_standard(tmp_path: Path, reported) -> None:  # type: ignore[no-untyped-def]
    t = tracker(tmp_path)
    cost = t.record(t.scope("run", "r-1", 10.0), "gpt-6-luna", USAGE, service_tier=reported)
    assert cost == pytest.approx(STANDARD_COST)
    assert ledger(tmp_path)[0]["service_tier"] == reported


def test_the_reservation_uses_the_requested_tier_rates(tmp_path: Path) -> None:
    t = tracker(tmp_path)
    t.reserve(t.scope("run", "r-1", 10.0), "gpt-6-luna", 1_000, 8_000, service_tier="fast")
    assert t.reserved_usd == pytest.approx(FAST_WORST)
    t2 = tracker(tmp_path / "standard")
    t2.reserve(t2.scope("run", "r-2", 10.0), "gpt-6-luna", 1_000, 8_000, service_tier="auto")
    assert t2.reserved_usd == pytest.approx(STANDARD_WORST)


def test_a_cap_with_room_for_a_standard_call_refuses_a_fast_one(tmp_path: Path) -> None:
    t = tracker(tmp_path, batch=0.006)  # above the standard worst case, below the Fast one
    scope = t.scope("run", "r-1", 10.0)
    with pytest.raises(CapExceeded) as info:
        t.reserve(scope, "gpt-6-luna", 1_000, 8_000, service_tier="fast")
    assert info.value.scope == "batch"
    t.reserve(scope, "gpt-6-luna", 1_000, 8_000)  # standard still fits


def test_the_loop_reserves_at_the_requested_tier_and_prices_the_reported_one(
    tmp_path: Path,
) -> None:
    usage = Usage(input_tokens=1000, output_tokens=200)
    steps = [
        Step(output_items=tool_step("list_dir", path=".").output_items, usage=usage,
             service_tier="fast"),
        Step(output_items=tool_step("finish", claim="done", summary="ok").output_items,
             usage=usage, service_tier="default"),
    ]  # fmt: skip
    result, _events, _client = run(tmp_path, steps, service_tier="fast")
    entries = ledger(tmp_path)
    assert [e["service_tier"] for e in entries] == ["fast", "default"]
    # 1,000 input x 0.20 + 200 output x 1.00 = $0.0004 (fast); half of that at standard.
    assert [e["cost_usd"] for e in entries] == pytest.approx([0.0004, 0.0002])
    assert result.cost_usd == pytest.approx(0.0006)


def test_the_openai_client_passes_the_tier_and_reads_the_reported_one() -> None:
    calls: list[dict[str, Any]] = []

    class Responses:
        def create(self, **kwargs: Any) -> Any:
            calls.append(kwargs)
            return SimpleNamespace(
                output=[],
                usage=SimpleNamespace(input_tokens=10, output_tokens=2),
                status="completed",
                output_text="",
                incomplete_details=None,
                service_tier="default",
            )

    client = OpenAIModelClient(SimpleNamespace(responses=Responses()))
    response = client.respond(
        [], [], model="gpt-6-luna", effort="low", max_output_tokens=100, service_tier="fast"
    )
    assert calls[0]["service_tier"] == "fast"
    assert response.service_tier == "default"


def test_a_fast_tier_for_a_model_without_fast_rates_is_refused_at_startup(tmp_path: Path) -> None:
    from shipharness.ab.runtime import build_runtime

    settings = Settings(
        _env_file=None,
        openai_model="gpt-5.6-luna",
        openai_service_tier="fast",
        langsmith_tracing=False,
        runs_dir=tmp_path / "runs",
        sandbox_mode="none",
    )
    with pytest.raises(UnknownModelPrice, match="gpt-5.6-luna"):
        build_runtime(settings, project="shipharness-pilot", session_id="pilot")


def test_the_reviewer_requests_no_tier_and_the_ledger_keeps_the_reported_one(
    tmp_path: Path,
) -> None:
    from shipharness.reviewer import ReviewInput, run_review
    from shipharness.tracing import NullTracer

    from .reviewer.test_review import completed, fake_client

    client = fake_client(completed(service_tier="default"))
    t = tracker(tmp_path)
    inp = ReviewInput(task="Add a filter.", diff="diff", grading_criteria="R1")
    outcome = run_review(inp, t, NullTracer(), client=client, model="gpt-5.6-luna")
    assert outcome.status == "ok"
    assert "service_tier" not in client.responses.calls[0]  # the reviewer stays standard
    assert ledger(tmp_path)[0]["service_tier"] == "default"
