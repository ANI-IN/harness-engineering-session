from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from shipharness.config import DEFAULT_PRICES_FILE, Prices
from shipharness.cost import CapExceeded, Caps, CostTracker, Usage, cost_of, usage_from_openai

PRICES = Prices.load(DEFAULT_PRICES_FILE)
CAPS = Caps(run=0.20, review=0.04, session=2.50, batch=2.50, experiment=25.00)


def tracker(tmp_path: Path, *, experiment: bool = False, caps: Caps = CAPS) -> CostTracker:
    return CostTracker(
        PRICES, caps, tmp_path / "ledger.jsonl", session_id="2026-10-18", experiment=experiment
    )


def big_usage(output_tokens: int) -> Usage:
    return Usage(input_tokens=0, output_tokens=output_tokens)


def test_cost_formula_prices_cache_reads_and_writes_separately() -> None:
    usage = Usage(
        input_tokens=10_000,
        cached_tokens=6_000,
        cache_write_tokens=2_000,
        output_tokens=1_000,
        reasoning_tokens=500,
    )
    expected = (2_000 * 0.10 + 6_000 * 0.01 + 2_000 * 0.125 + 1_000 * 0.50) / 1e6
    assert cost_of(PRICES.get("gpt-6-luna"), usage) == pytest.approx(expected)


def test_record_returns_call_cost_and_accumulates(tmp_path: Path) -> None:
    t = tracker(tmp_path)
    scope = t.scope("run", "r-1", 0.20)
    cost = t.record(scope, "gpt-6-luna", Usage(input_tokens=1_000_000))
    assert cost == pytest.approx(0.10)
    assert scope.spent_usd == pytest.approx(0.10)


def test_run_cap_raises_and_call_is_still_in_ledger(tmp_path: Path) -> None:
    t = tracker(tmp_path)
    scope = t.scope("run", "r-1", 0.20)
    t.record(scope, "gpt-6-luna", big_usage(300_000))  # $0.15
    with pytest.raises(CapExceeded) as info:
        t.record(scope, "gpt-6-luna", big_usage(200_000))  # +$0.10 -> $0.25
    assert info.value.scope == "run"
    assert info.value.limit_usd == 0.20
    lines = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_check_before_call_uses_worst_case(tmp_path: Path) -> None:
    t = tracker(tmp_path)
    scope = t.scope("run", "r-1", 0.20)
    t.record(scope, "gpt-6-luna", big_usage(300_000))  # $0.15 spent
    # worst case next call: 100k input at cache-write price ($0.0125) + 80k output ($0.04) = $0.0525
    with pytest.raises(CapExceeded):
        t.check_before_call(scope, "gpt-6-luna", est_input_tokens=100_000, max_output_tokens=80_000)
    t.check_before_call(scope, "gpt-6-luna", est_input_tokens=10_000, max_output_tokens=8_000)


def test_session_total_persists_across_trackers(tmp_path: Path) -> None:
    caps = Caps(run=10.0, review=0.04, session=2.50, batch=10.0, experiment=25.0)
    first = tracker(tmp_path, caps=caps)
    first.record(first.scope("run", "r-1", 10.0), "gpt-6-luna", big_usage(4_000_000))  # $2.00
    second = tracker(tmp_path, caps=caps)
    assert second.session_total_usd == pytest.approx(2.00)
    with pytest.raises(CapExceeded) as info:
        second.record(second.scope("run", "r-2", 10.0), "gpt-6-luna", big_usage(2_000_000))
    assert info.value.scope == "session"


def test_batch_total_is_per_tracker_but_experiment_total_persists(tmp_path: Path) -> None:
    caps = Caps(run=10.0, review=0.04, session=2.50, batch=2.50, experiment=25.0)
    first = tracker(tmp_path, experiment=True, caps=caps)
    first.record(first.scope("run", "r-1", 10.0), "gpt-6-luna", big_usage(4_000_000))  # $2.00
    second = tracker(tmp_path, experiment=True, caps=caps)
    assert second.batch_total_usd == 0.0
    assert second.experiment_total_usd == pytest.approx(2.00)
    # Experiment spend does not count against the class session cap.
    assert second.session_total_usd == 0.0
    second.record(second.scope("run", "r-2", 10.0), "gpt-6-luna", big_usage(4_000_000))
    with pytest.raises(CapExceeded) as info:
        second.record(second.scope("run", "r-3", 10.0), "gpt-6-luna", big_usage(2_000_000))
    assert info.value.scope == "batch"


def test_unknown_model_fails_before_spending(tmp_path: Path) -> None:
    t = tracker(tmp_path)
    with pytest.raises(KeyError):
        t.record(t.scope("run", "r-1", 0.2), "gpt-unknown", big_usage(1))


def test_usage_from_openai_reads_fields_defensively() -> None:
    resp_usage = SimpleNamespace(
        input_tokens=500,
        output_tokens=120,
        input_tokens_details=SimpleNamespace(cached_tokens=300),
        output_tokens_details=SimpleNamespace(reasoning_tokens=80),
    )
    usage = usage_from_openai(resp_usage)
    assert usage == Usage(
        input_tokens=500,
        cached_tokens=300,
        cache_write_tokens=0,
        output_tokens=120,
        reasoning_tokens=80,
    )


def test_summary_reports_totals_by_model(tmp_path: Path) -> None:
    t = tracker(tmp_path)
    t.record(t.scope("run", "r-1", 0.2), "gpt-6-luna", Usage(input_tokens=100_000))
    t.record(t.scope("review", "rv-1", 0.04), "gpt-5.6-luna", Usage(input_tokens=100_000))
    summary = t.summary()
    assert summary.total_usd == pytest.approx(0.01 + 0.02)
    assert summary.by_model == {
        "gpt-6-luna": pytest.approx(0.01),
        "gpt-5.6-luna": pytest.approx(0.02),
    }
    entry = json.loads((tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert entry["model"] == "gpt-6-luna"
    assert entry["key"] == "r-1"
