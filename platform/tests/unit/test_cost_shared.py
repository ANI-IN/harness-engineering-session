"""Caps hold across concurrent commands that share one ledger (`make demo-4`
and `make final` launched together; the pilot runs several `shipharness ab` processes at once).

Each command has its own CostTracker. Before each check and before each write, a tracker reads the
entries other commands appended since its last read, so session, experiment, and build totals are
shared through the ledger.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shipharness.config import DEFAULT_PRICES_FILE, Prices
from shipharness.cost import CapExceeded, Caps, CostTracker, Usage

PRICES = Prices.load(DEFAULT_PRICES_FILE)
CAPS = Caps(run=5.0, review=0.04, session=2.50, batch=2.50, experiment=25.0, build=15.0)


def tracker(ledger: Path, *, experiment: bool = False) -> CostTracker:
    return CostTracker(PRICES, CAPS, ledger, session_id="class", experiment=experiment)


def spend(t: CostTracker, usd: float) -> None:
    t.record(t.scope("run", "r", 5.0), "gpt-6-luna", Usage(output_tokens=int(usd * 2_000_000)))


def test_a_second_command_sees_the_first_commands_session_spend(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    demo, final = tracker(ledger), tracker(ledger)  # both start before either spends
    spend(demo, 1.0)
    spend(final, 1.0)
    assert final.session_total_usd == pytest.approx(2.0)
    assert demo.summary().session_total_usd == pytest.approx(2.0)


def test_session_cap_binds_across_concurrent_commands(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    demo, final = tracker(ledger), tracker(ledger)
    spend(demo, 2.45)
    with pytest.raises(CapExceeded) as info:
        final.check_before_call(final.scope("run", "r2", 5.0), "gpt-6-luna", 0, 200_000)
    assert info.value.scope == "session"


def test_build_total_is_shared_by_experiment_and_class_commands(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    pilot, demo = tracker(ledger, experiment=True), tracker(ledger)
    spend(pilot, 0.5)
    spend(demo, 0.25)
    assert pilot.build_total_usd == pytest.approx(0.75)
    assert demo.summary().build_total_usd == pytest.approx(0.75)


def test_a_partial_last_line_is_read_once_it_is_complete(tmp_path: Path) -> None:
    import json

    ledger = tmp_path / "ledger.jsonl"
    t = tracker(ledger)
    entry = {"ts": "2026-10-17T10:00:00Z", "session": "class", "experiment": False, "cost_usd": 0.5}
    text = json.dumps(entry) + "\n"
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(text[:20])  # another command is mid-write
    assert t.summary().session_total_usd == pytest.approx(0.0)
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(text[20:])
    assert t.summary().session_total_usd == pytest.approx(0.5)
