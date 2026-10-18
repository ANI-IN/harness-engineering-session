"""Cost reservation: the worst case of a call is held against every cap until the call settles."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest

from shipharness.config import DEFAULT_PRICES_FILE, Prices
from shipharness.cost import CapExceeded, Caps, CostTracker, Usage
from shipharness.events import EventBus
from shipharness.harness.base import Harness
from shipharness.runner.loop import RunOptions, run_agent
from shipharness.runner.model import ScriptedModelClient, Step, tool_step
from shipharness.sandbox import FakeSandbox
from shipharness.tracing import NullTracer

from .test_loop import FakeAPIError, spec

PRICES = Prices.load(DEFAULT_PRICES_FILE)
# Worst case of one call with 1,000 input tokens and 8,000 output tokens on gpt-6-luna:
# 1,000 x $0.125/M + 8,000 x $0.50/M = $0.004125.
WORST = 0.004125


def tracker(tmp_path: Path, *, batch: float = 2.5, session: float = 2.5) -> CostTracker:
    caps = Caps(run=10.0, review=0.04, session=session, batch=batch, experiment=25.0)
    return CostTracker(PRICES, caps, tmp_path / "ledger.jsonl", session_id="t")


def test_a_reservation_holds_room_until_it_settles(tmp_path: Path) -> None:
    t = tracker(tmp_path, batch=0.006)
    first, second = t.scope("run", "r-1", 10.0), t.scope("run", "r-2", 10.0)
    held = t.reserve(first, "gpt-6-luna", 1_000, 8_000)
    assert t.reserved_usd == pytest.approx(WORST)
    with pytest.raises(CapExceeded) as info:
        t.reserve(second, "gpt-6-luna", 1_000, 8_000)
    assert info.value.scope == "batch"
    cost = t.settle(held, Usage(input_tokens=1_000, output_tokens=1_000))  # $0.0006
    assert cost == pytest.approx(0.0006)
    assert t.reserved_usd == 0.0
    assert t.batch_total_usd == pytest.approx(0.0006)
    t.settle(t.reserve(second, "gpt-6-luna", 1_000, 8_000), Usage(output_tokens=10))


def test_releasing_a_reservation_frees_it_and_records_nothing(tmp_path: Path) -> None:
    t = tracker(tmp_path, batch=0.006)
    scope = t.scope("run", "r-1", 10.0)
    held = t.reserve(scope, "gpt-6-luna", 1_000, 8_000)
    t.release(held)
    t.release(held)  # idempotent
    assert t.reserved_usd == 0.0 and t.batch_total_usd == 0.0
    assert not (tmp_path / "ledger.jsonl").exists()
    t.reserve(scope, "gpt-6-luna", 1_000, 8_000)


def test_the_pre_check_counts_other_reservations(tmp_path: Path) -> None:
    t = tracker(tmp_path, session=0.006)
    t.reserve(t.scope("run", "r-1", 10.0), "gpt-6-luna", 1_000, 8_000)
    with pytest.raises(CapExceeded) as info:
        t.check_before_call(t.scope("review", "rv-1", 10.0), "gpt-6-luna", 1_000, 8_000)
    assert info.value.scope == "session"


def test_the_loop_releases_the_reservation_when_the_call_fails(tmp_path: Path) -> None:
    t = tracker(tmp_path)
    client = ScriptedModelClient([Step(error=FakeAPIError(400, "bad_request"))])
    with EventBus(tmp_path / "events.jsonl", ab_id=None) as bus:
        result = run_agent(spec(tmp_path), Harness([]), FakeSandbox(), bus, t, NullTracer(), client)
    assert result.status == "ERROR"
    assert t.reserved_usd == 0.0
    assert t.batch_total_usd == 0.0


def test_two_arms_racing_near_a_shared_cap_never_overshoot(tmp_path: Path) -> None:
    """Arm A's call is in flight (its worst case is reserved); arm B's call is refused before it
    is made, so the shared batch cap can never be crossed by the two calls together."""
    shared = tracker(tmp_path, batch=0.006)  # room for one worst-case call, not two
    entered, go = threading.Event(), threading.Event()
    actual = Usage(input_tokens=1_000, output_tokens=8_000)  # $0.0041, within the worst case

    class Blocking(ScriptedModelClient):
        def respond(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
            entered.set()
            assert go.wait(timeout=20)
            return super().respond(*args, **kwargs)

    client_a = Blocking([tool_step("list_dir", path=".", depth=None, usage=actual)])
    client_b = ScriptedModelClient([tool_step("list_dir", path=".", depth=None, usage=actual)])
    results: dict[str, Any] = {}

    def arm(name: str, client: ScriptedModelClient) -> None:
        root = tmp_path / name
        root.mkdir()
        with EventBus(root / "events.jsonl", ab_id="ab-1") as bus:
            results[name] = run_agent(
                spec(root, run_id=f"r-{name}", arm="bare" if name == "a" else "harness"),
                Harness([]),
                FakeSandbox(),
                bus,
                shared,
                NullTracer(),
                client,
                RunOptions(wrapup_turns=2, sleep=lambda _s: None),
            )

    thread_a = threading.Thread(target=arm, args=("a", client_a))
    thread_a.start()
    assert entered.wait(timeout=20)
    thread_b = threading.Thread(target=arm, args=("b", client_b))
    thread_b.start()
    thread_b.join(timeout=20)
    go.set()
    thread_a.join(timeout=20)

    assert results["b"].status == "ABORTED: cap"
    assert client_b.inputs == []  # refused before the call was made
    assert results["a"].turns_total == 1
    assert shared.batch_total_usd <= 0.006
    assert shared.reserved_usd == 0.0
