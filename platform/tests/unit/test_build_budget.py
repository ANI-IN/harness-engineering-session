"""Total build budget: $15 for all model spend while the course is built,
counted from the first ledger entry (plus the recorded pre-ledger spend), enforced on every call."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shipharness.config import DEFAULT_PRICES_FILE, Prices, Settings
from shipharness.cost import CapExceeded, Caps, CostTracker, Usage
from shipharness.cost.tracker import record_opening_balance

PRICES = Prices.load(DEFAULT_PRICES_FILE)


def write_ledger(path: Path, entries: list[dict]) -> None:
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")


def tracker(ledger: Path, *, experiment: bool = False, build: float = 15.0) -> CostTracker:
    caps = Caps(run=0.20, review=0.04, session=2.50, batch=2.50, experiment=25.0, build=build)
    return CostTracker(PRICES, caps, ledger, session_id="2026-10-17", experiment=experiment)


def test_build_cap_defaults_to_15_dollars() -> None:
    assert Settings(_env_file=None).max_build_total_usd == 15.0
    assert Caps.from_settings(Settings(_env_file=None)).build == 15.0


def test_build_total_counts_every_ledger_entry_whatever_its_session(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    write_ledger(
        ledger,
        [
            {"ts": "2026-10-16T16:00:00Z", "session": "", "experiment": False, "cost_usd": 4.0},
            {"ts": "2026-10-16T17:00:00Z", "session": "x", "experiment": True, "cost_usd": 5.0},
            {"ts": "2026-10-16T18:00:00Z", "session": "y", "experiment": False, "cost_usd": 5.99},
        ],
    )
    t = tracker(ledger)
    assert t.build_total_usd == pytest.approx(14.99)
    scope = t.scope("run", "r-1", 0.20)
    with pytest.raises(CapExceeded) as info:
        t.check_before_call(scope, "gpt-6-luna", 0, 100_000)  # worst case $0.05
    assert info.value.scope == "build"


def test_build_total_grows_with_each_call_and_shows_spent_and_remaining(tmp_path: Path) -> None:
    t = tracker(tmp_path / "ledger.jsonl", experiment=True)
    t.record(t.scope("run", "r-1", 0.20), "gpt-6-luna", Usage(output_tokens=100_000))  # $0.05
    summary = t.summary()
    assert summary.build_total_usd == pytest.approx(0.05)
    assert summary.remaining()["build"] == pytest.approx(14.95)


def test_cost_line_shows_build_spent_and_remaining(tmp_path: Path) -> None:
    from shipharness.ab.runtime import cost_line

    t = tracker(tmp_path / "ledger.jsonl")
    t.record(t.scope("run", "r-1", 0.20), "gpt-6-luna", Usage(output_tokens=100_000))
    assert "build $0.050000 of $15.00 ($14.950000 left)" in cost_line(t)


def test_opening_balance_is_recorded_once_and_counts(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    write_ledger(
        ledger, [{"ts": "2026-10-16T16:35:58Z", "session": "s", "experiment": False, "cost_usd": 1}]
    )
    record_opening_balance(ledger, 0.0022, note="M3-M4 before the ledger")
    assert tracker(ledger).build_total_usd == pytest.approx(1.0022)
    entry = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert entry["kind"] == "opening" and entry["ts"] < "2026-10-16T16:35:58Z"
    with pytest.raises(ValueError, match="already"):
        record_opening_balance(ledger, 0.0022, note="again")
