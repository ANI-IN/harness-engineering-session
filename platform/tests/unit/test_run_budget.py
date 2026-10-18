"""Run budget: RUN_TIMEOUT_S counts agent time only; harness work has its own HARNESS_TIMEOUT_S."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shipharness.cost import Caps, CostTracker
from shipharness.events import EventBus, read_events
from shipharness.harness.base import BaseLayer, Harness, LayerContext
from shipharness.harness.decisions import HarnessDecision
from shipharness.runner.loop import RunOptions, run_agent
from shipharness.runner.model import ScriptedModelClient, Step, tool_step
from shipharness.sandbox import FakeSandbox
from shipharness.tracing import NullTracer

from .test_loop import PRICES, finish, read_app, spec


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TimedClient(ScriptedModelClient):
    """Each model call takes `per_call` seconds of agent time."""

    def __init__(self, steps: list[Step], clock: FakeClock, per_call: float) -> None:
        super().__init__(steps)
        self.clock, self.per_call = clock, per_call

    def respond(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        self.clock.advance(self.per_call)
        return super().respond(*args, **kwargs)


class SlowGate(BaseLayer):
    """A verify-like layer whose gate takes `gate_s` seconds; fails the first `fails` gates."""

    name = "verify"

    def __init__(self, clock: FakeClock, gate_s: float, fails: int = 1, prepare_s: float = 0.0):
        self.clock, self.gate_s, self.fails, self.prepare_s = clock, gate_s, fails, prepare_s
        self.gates = 0

    def prepare_workspace(self, ctx: LayerContext) -> list[HarnessDecision]:
        self.clock.advance(self.prepare_s)
        return []

    def on_claim_done(self, ctx: LayerContext) -> HarnessDecision | None:
        self.clock.advance(self.gate_s)
        self.gates += 1
        if self.gates <= self.fails:
            return HarnessDecision(kind="gate_fail", layer="verify", message="visible tests fail")
        return HarnessDecision(kind="gate_pass", layer="verify", message="gate passed")


def _run(
    tmp_path: Path,
    steps: list[Step],
    layer: BaseLayer,
    clock: FakeClock,
    *,
    per_call: float,
    run_timeout_s: int = 300,
    harness_timeout_s: float | None = 120,
    sandbox: FakeSandbox | None = None,
):  # type: ignore[no-untyped-def]
    client = TimedClient(steps, clock, per_call)
    tracker = CostTracker(
        PRICES, Caps(0.2, 0.04, 2.5, 2.5, 25.0), tmp_path / "ledger.jsonl", session_id="t"
    )
    options = RunOptions(
        wrapup_turns=2,
        sleep=lambda _s: None,
        clock=clock,
        run_timeout_s=run_timeout_s,
        harness_timeout_s=harness_timeout_s,
    )
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id="ab-1") as bus:
        result = run_agent(
            spec(tmp_path, arm="harness"),
            Harness([layer]),
            sandbox or FakeSandbox(),
            bus,
            tracker,
            NullTracer(),
            client,
            options,
        )
    return result, list(read_events(log)), client


def test_a_slow_gate_does_not_consume_the_agent_budget(tmp_path: Path) -> None:
    clock = FakeClock()
    steps = [finish(), read_app(), read_app(), read_app(), read_app(), read_app(), finish()]
    # 7 calls x 20 s = 140 s of agent time; 2 gates x 250 s = 500 s of harness time.
    result, events, _ = _run(
        tmp_path,
        steps,
        SlowGate(clock, gate_s=250),
        clock,
        per_call=20,
        run_timeout_s=300,
        harness_timeout_s=1000,
    )
    assert result.status == "completed"
    assert result.claim == "done"
    assert result.turns_total == 7
    assert result.agent_wall_s == 140
    assert result.harness_wall_s == 500
    assert result.wall_s == 640
    assert result.abort_reason is None
    assert events[-1].type == "run_end"


def test_agent_time_limit_still_applies_to_agent_work(tmp_path: Path) -> None:
    clock = FakeClock()
    result, _events, client = _run(
        tmp_path, [read_app()] * 8, SlowGate(clock, gate_s=0), clock, per_call=100
    )
    assert result.status == "ABORTED: timeout"
    assert result.turns_total == 4  # 400 s > 300 s after the fourth call
    assert result.sessions[-1].ended_by == "timeout"
    assert result.abort_reason is not None and "agent time limit" in result.abort_reason


def test_a_harness_overrun_ends_the_run_with_the_reason(tmp_path: Path) -> None:
    clock = FakeClock()
    steps = [finish(), read_app(), read_app(), finish()]
    result, events, client = _run(
        tmp_path,
        steps,
        SlowGate(clock, gate_s=150),
        clock,
        per_call=10,
        harness_timeout_s=100,
    )
    assert result.status == "ABORTED: timeout"
    assert result.abort_reason is not None and "harness time limit" in result.abort_reason
    assert result.sessions[-1].ended_by == "timeout"
    assert result.turns_total == 1  # no model call after the gate that crossed the limit
    assert len(client.steps) == 3
    assert result.harness_wall_s == 150
    assert events[-1].type == "run_end" and events[-1].data["status"] == "ABORTED: timeout"


def test_a_slow_workspace_preparation_ends_the_run_before_any_model_call(tmp_path: Path) -> None:
    clock = FakeClock()
    result, _events, client = _run(
        tmp_path,
        [finish()],
        SlowGate(clock, gate_s=0, prepare_s=130),
        clock,
        per_call=10,
        harness_timeout_s=120,
    )
    assert result.status == "ABORTED: timeout"
    assert result.abort_reason is not None and "harness time limit" in result.abort_reason
    assert result.turns_total == 0
    assert client.inputs == []


def test_cost_cap_abort_carries_a_reason(tmp_path: Path) -> None:
    from shipharness.cost import Usage

    clock = FakeClock()
    pricey = Usage(input_tokens=1_000, output_tokens=500_000)
    result, _events, _client = _run(
        tmp_path,
        [tool_step("list_dir", path=".", depth=None, usage=pricey)],
        SlowGate(clock, gate_s=0),
        clock,
        per_call=1,
    )
    assert result.status == "ABORTED: cap"
    assert result.abort_reason is not None and "cost cap" in result.abort_reason


class TimeLeftProbe(BaseLayer):
    """Records how much harness time the loop says is left while its own work runs."""

    name = "verify"

    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.seen: list[float | None] = []

    def prepare_workspace(self, ctx: LayerContext) -> list[HarnessDecision]:
        self.clock.advance(30)
        self.seen.append(ctx.time_left())
        return []

    def on_claim_done(self, ctx: LayerContext) -> HarnessDecision | None:
        self.clock.advance(20)
        self.seen.append(ctx.time_left())
        return HarnessDecision(kind="gate_pass", layer="verify", message="gate passed")


def test_layers_see_the_harness_time_left(tmp_path: Path) -> None:
    clock = FakeClock()
    probe = TimeLeftProbe(clock)
    _run(tmp_path, [finish()], probe, clock, per_call=1, harness_timeout_s=120)
    # 30 s of preparation leaves 90 s; the gate then spends 20 s more of the same budget.
    assert probe.seen == [90, 70]


def test_time_left_is_none_without_a_harness_limit(tmp_path: Path) -> None:
    clock = FakeClock()
    probe = TimeLeftProbe(clock)
    _run(tmp_path, [finish()], probe, clock, per_call=1, harness_timeout_s=None)
    assert probe.seen == [None, None]


def one_response(*steps: Step) -> Step:
    """Several tool calls in one model response."""
    return Step(output_items=[item for step in steps for item in step.output_items])


OUT_OF_SCOPE = "echo pwned > /etc/out_of_scope.txt"


def _results(events, name_of_call: str):  # type: ignore[no-untyped-def]
    calls = [e.data for e in events if e.type == "tool_call" and e.data["name"] == name_of_call]
    ids = {c["call_id"] for c in calls}
    return [e.data for e in events if e.type == "tool_result" and e.data["call_id"] in ids]


def test_calls_after_the_harness_time_limit_in_the_same_response_never_run(
    tmp_path: Path,
) -> None:
    clock = FakeClock()
    sandbox = FakeSandbox()
    steps = [one_response(finish(), tool_step("run", command=OUT_OF_SCOPE, timeout_s=None))]
    result, events, client = _run(
        tmp_path,
        steps,
        SlowGate(clock, gate_s=150, fails=0),
        clock,
        per_call=1,
        harness_timeout_s=100,
        sandbox=sandbox,
    )
    assert result.status == "ABORTED: timeout"
    assert not any(OUT_OF_SCOPE in c for c in sandbox.commands)  # never reached the sandbox
    [refused] = _results(events, "run")
    assert refused["ok"] is False
    assert "not run" in refused["output_excerpt"]
    assert "harness time limit" in refused["output_excerpt"]
    # The transcript stays well formed: every call in the response has exactly one result.
    call_ids = [e.data["call_id"] for e in events if e.type == "tool_call"]
    result_ids = [e.data["call_id"] for e in events if e.type == "tool_result"]
    assert sorted(call_ids) == sorted(result_ids)


def test_calls_after_an_accepted_finish_in_the_same_response_never_run(tmp_path: Path) -> None:
    clock = FakeClock()
    sandbox = FakeSandbox()
    steps = [one_response(finish(), tool_step("run", command=OUT_OF_SCOPE, timeout_s=None))]
    result, events, _client = _run(
        tmp_path,
        steps,
        SlowGate(clock, gate_s=1, fails=0),
        clock,
        per_call=1,
        harness_timeout_s=100,
        sandbox=sandbox,
    )
    assert result.status == "completed" and result.claim == "done"
    assert not any(OUT_OF_SCOPE in c for c in sandbox.commands)
    [refused] = _results(events, "run")
    assert refused["ok"] is False and "not run" in refused["output_excerpt"]
    assert "session ended" in refused["output_excerpt"]


def test_calls_after_a_failed_gate_in_the_same_response_still_run(tmp_path: Path) -> None:
    clock = FakeClock()
    sandbox = FakeSandbox()
    steps = [
        one_response(finish(), tool_step("run", command="echo fixing", timeout_s=None)),
        finish(),
    ]
    result, _events, _client = _run(
        tmp_path, steps, SlowGate(clock, gate_s=1, fails=1), clock, per_call=1, sandbox=sandbox
    )
    assert result.claim == "done"
    assert any("echo fixing" in c for c in sandbox.commands)


class OverrunThenCrash(BaseLayer):
    """A tool check that crosses the harness time limit and then raises."""

    name = "verify"

    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock

    def after_tool(self, ctx: LayerContext, call: Any, result: Any) -> list[HarnessDecision]:
        self.clock.advance(500)
        raise RuntimeError("check crashed")


def test_an_abort_is_not_overwritten_by_a_later_error(tmp_path: Path) -> None:
    clock = FakeClock()
    result, events, _client = _run(
        tmp_path, [read_app(), finish()], OverrunThenCrash(clock), clock, per_call=1
    )
    assert result.status == "ABORTED: timeout"
    assert result.abort_reason is not None and "harness time limit" in result.abort_reason
    assert events[-1].type == "run_end" and events[-1].data["status"] == "ABORTED: timeout"
