from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from shipharness.config import DEFAULT_PRICES_FILE, Prices
from shipharness.cost import Caps, CostTracker
from shipharness.events import EventBus, read_events
from shipharness.harness.base import Harness, LayerContext
from shipharness.harness.verify.layer import VerifyLayer
from shipharness.layout import find_repo_root
from shipharness.runner.loop import RunOptions, run_agent
from shipharness.runner.model import ScriptedModelClient, tool_step
from shipharness.runner.models import AgentRunSpec
from shipharness.sandbox import ExecResult, FakeSandbox
from shipharness.tracing import NullTracer

from .fakes import ALL_GATE_CHECKS, check_result, ok, runner_output


def make_spec(ws: Path, **overrides: Any) -> AgentRunSpec:
    base: dict[str, Any] = dict(
        run_id="r-1",
        arm="harness",
        feature_id="F1",
        checkpoint="m1-s1-start",
        ticket_text="Add filters.",
        model="gpt-6-luna",
        reasoning_effort="low",
        layers=frozenset({"verify"}),
        phases=("build",),
        session_budget=[10],
        workspace=ws,
    )
    base.update(overrides)
    return AgentRunSpec(**base)


class Script:
    """FakeSandbox script: runner results change per call; pytest passes."""

    def __init__(self, runs: list[list[dict]]) -> None:
        self.runs = list(runs)
        self.runner_calls: list[str] = []

    def __call__(self, command: str) -> ExecResult:
        if "-m shipharness.checks.runner" in command:
            self.runner_calls.append(command)
            results = self.runs.pop(0) if len(self.runs) > 1 else self.runs[0]
            return ok(runner_output(results, command=command))
        if "-m pytest" in command:
            return ok("3 passed in 0.5s\n")
        if command.startswith("alembic heads"):
            return ok("abc (head)\n")
        return ok("")


GREEN = [check_result(c) for c in ALL_GATE_CHECKS]
RED = [check_result("r1_tenant", new=1), *GREEN[1:]]


def ctx_for(tmp_path: Path, sandbox: FakeSandbox, bus: EventBus | None = None, **kw: Any):
    ws = tmp_path / "ws"
    ws.mkdir(exist_ok=True)
    return LayerContext(
        spec=make_spec(ws, **kw),
        phase="build",
        session_index=1,
        turn=1,
        workspace=ws,
        sandbox=sandbox,
        bus=bus,
    )


def test_verify_is_registered_and_ignores_unknown_kwargs() -> None:
    harness = Harness.from_names(frozenset({"verify"}), instructions_root="x", unknown=1)
    assert harness.names == frozenset({"verify"})


def test_prepare_workspace_records_a_baseline_from_the_pristine_workspace(tmp_path: Path) -> None:
    script = Script([GREEN])
    ctx = ctx_for(tmp_path, FakeSandbox(script))
    layer = VerifyLayer(seed=5)
    layer.prepare_workspace(ctx)
    assert len(script.runner_calls) == 1
    assert "--baseline" not in script.runner_calls[0]
    layer.on_claim_done(ctx)
    assert "--baseline" in script.runner_calls[1]


def test_given_baseline_is_used_without_computing_one(tmp_path: Path) -> None:
    script = Script([GREEN])
    ctx = ctx_for(tmp_path, FakeSandbox(script))
    layer = VerifyLayer(baseline_json='{"results": []}')
    layer.prepare_workspace(ctx)
    assert script.runner_calls == []


def test_failing_gate_returns_gate_fail_and_writes_state(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id=None) as bus:
        ctx = ctx_for(tmp_path, FakeSandbox(Script([RED])), bus)
        decision = VerifyLayer(baseline_json='{"results": []}').on_claim_done(ctx)
    assert decision is not None and decision.kind == "gate_fail"
    assert "FAIL House rule 1" in decision.message
    assert decision.data["gate_id"] == ctx.state["verify.gate"]["gate_id"]
    assert ctx.state["verify.gate"]["passed"] is False
    events = list(read_events(log))
    gates = [e for e in events if e.type == "gate_result"]
    assert gates[0].data["items"][0]["status"] == "pending"
    assert gates[-1].data["passed"] is False
    assert {e.data["check"] for e in events if e.type == "check_progress"} == set(ALL_GATE_CHECKS)


def test_passing_gate_returns_gate_pass_and_ids_increase(tmp_path: Path) -> None:
    ctx = ctx_for(tmp_path, FakeSandbox(Script([RED, GREEN])))
    layer = VerifyLayer(baseline_json='{"results": []}')
    first = layer.on_claim_done(ctx)
    second = layer.on_claim_done(ctx)
    assert first is not None and second is not None
    assert second.kind == "gate_pass"
    assert first.data["gate_id"] != second.data["gate_id"]
    assert ctx.state["verify.gate"]["passed"] is True


def test_context_prefix_is_stable_and_mentions_the_gate(tmp_path: Path) -> None:
    ctx = ctx_for(tmp_path, FakeSandbox(Script([GREEN])))
    layer = VerifyLayer()
    first = layer.context_prefix(ctx)
    assert first == layer.context_prefix(ctx)
    assert "finish" in first[0] and "clean state" in first[0]


def test_gate_params_carry_existing_tests_and_exemptions(tmp_path: Path) -> None:
    import base64
    import json

    script = Script([GREEN])
    sandbox = FakeSandbox(script)
    ctx = ctx_for(tmp_path, sandbox)
    (ctx.workspace / "tests" / "visible").mkdir(parents=True)
    (ctx.workspace / "tests" / "visible" / "test_a.py").write_text("def test_a(): pass\n")
    layer = VerifyLayer(baseline_json="{}", exemptions={"R4": ["POST /projects/{id}/issues"]})
    layer.prepare_workspace(ctx)
    layer.on_claim_done(ctx)
    [params_cmd] = [c for c in sandbox.commands if c.startswith("printf") and "params" in c]
    params = json.loads(base64.b64decode(params_cmd.split()[2]))
    assert params["regression_targets"] == ["tests/visible/test_a.py"]
    assert params["exemptions"] == {"R4": ["POST /projects/{id}/issues"]}


# --- run_agent integration --------------------------------------------------------------------


def test_run_with_verify_layer_retries_after_gate_failure(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    steps = [
        tool_step("finish", claim="done", summary="first try"),
        tool_step("finish", claim="done", summary="fixed"),
    ]
    tracker = CostTracker(
        Prices.load(DEFAULT_PRICES_FILE),
        Caps(0.2, 0.04, 2.5, 2.5, 25.0),
        tmp_path / "l.jsonl",
        session_id="t",
    )
    log = tmp_path / "events.jsonl"
    client = ScriptedModelClient(steps)
    with EventBus(log, ab_id=None) as bus:
        result = run_agent(
            make_spec(ws),
            Harness([VerifyLayer(baseline_json='{"results": []}')]),
            FakeSandbox(Script([RED, GREEN])),
            bus,
            tracker,
            NullTracer(),
            client,
            RunOptions(sleep=lambda _s: None),
        )
    assert result.claim == "done" and result.turns_total == 2
    claims = [e.data for e in read_events(log) if e.type == "claim"]
    assert [c["gate_id"] is not None for c in claims] == [True, True]
    assert claims[0]["gate_id"] != claims[1]["gate_id"]


# --- test phase: filter pipeline hook -----------------------------------------------------------

EXISTING = "def test_old():\n    assert 1\n"
NEW_FILE = """import pytest


def test_keeps():
    assert 2 == 2


@pytest.mark.parametrize("x", [1])
def test_drops(x):
    assert True


class TestGroup:
    def test_method(self):
        assert 3 == 3
"""


def phase_ctx(tmp_path: Path, pipeline: Callable[..., Any]) -> tuple[LayerContext, Any]:
    sandbox = FakeSandbox(Script([GREEN]))
    ctx = ctx_for(tmp_path, sandbox, phases=("build", "test"))
    visible = ctx.workspace / "tests" / "visible"
    visible.mkdir(parents=True)
    (visible / "test_old.py").write_text(EXISTING, encoding="utf-8")
    layer = VerifyLayer(baseline_json="{}", pipeline=pipeline)
    ctx.phase = "test"
    layer.context_prefix(ctx)  # first hook of the test phase: snapshot taken here
    return ctx, layer


def test_test_phase_discards_failing_tests_and_keeps_the_rest(tmp_path: Path) -> None:
    seen: list[list[dict]] = []

    def pipeline(cands: list[dict], ctx: LayerContext, shas: dict[str, str]) -> list[dict]:
        seen.append(cands)
        out = []
        for c in cands:
            passed = not c["test_id"].endswith("test_drops")
            out.append(
                {"test_id": c["test_id"], "filter": 4, "passed": passed, "reason": "no assert"}
            )
        return out

    ctx, layer = phase_ctx(tmp_path, pipeline)
    new = ctx.workspace / "tests" / "visible" / "test_new.py"
    new.write_text(NEW_FILE, encoding="utf-8")
    (ctx.workspace / "tests" / "visible" / "test_old.py").write_text(
        EXISTING + "\n\ndef test_extra():\n    assert 4\n", encoding="utf-8"
    )
    [decision] = layer.on_phase_end(ctx)
    ids = sorted(c["test_id"] for c in seen[0])
    assert ids == [
        "tests/visible/test_new.py::TestGroup::test_method",
        "tests/visible/test_new.py::test_drops",
        "tests/visible/test_new.py::test_keeps",
        "tests/visible/test_old.py::test_extra",
    ]
    text = new.read_text(encoding="utf-8")
    assert "def test_keeps" in text and "test_method" in text
    assert "test_drops" not in text and "parametrize" not in text
    assert decision.kind == "note"
    assert decision.data["discarded"] == {"tests/visible/test_new.py::test_drops": "no assert"}
    assert len(decision.data["kept"]) == 3
    assert any(c.startswith("git add -A tests/visible") for c in ctx.sandbox.commands)


def test_file_left_without_tests_is_removed(tmp_path: Path) -> None:
    def pipeline(cands: list[dict], ctx: LayerContext, shas: dict[str, str]) -> list[dict]:
        return [
            {"test_id": c["test_id"], "filter": 2, "passed": False, "reason": "flaky"}
            for c in cands
        ]

    ctx, layer = phase_ctx(tmp_path, pipeline)
    new = ctx.workspace / "tests" / "visible" / "test_bad.py"
    new.write_text("def test_flaky():\n    assert random()\n", encoding="utf-8")
    layer.on_phase_end(ctx)
    assert not new.exists()


def test_unparseable_test_file_is_discarded_without_the_pipeline(tmp_path: Path) -> None:
    calls: list[int] = []

    def pipeline(cands: list[dict], ctx: LayerContext, shas: dict[str, str]) -> list[dict]:
        calls.append(len(cands))
        return []

    ctx, layer = phase_ctx(tmp_path, pipeline)
    broken = ctx.workspace / "tests" / "visible" / "test_broken.py"
    broken.write_text("def test_x(:\n", encoding="utf-8")
    [decision] = layer.on_phase_end(ctx)
    assert not broken.exists()
    assert "does not parse" in next(iter(decision.data["discarded"].values()))


def test_missing_filter_package_is_reported_and_tests_are_kept(tmp_path: Path) -> None:
    from shipharness.harness.verify import testphase

    def unavailable(cands: list[dict], ctx: LayerContext, shas: dict[str, str]) -> list[dict]:
        raise testphase.PipelineUnavailable("shipharness.filters is not installed")

    ctx, layer = phase_ctx(tmp_path, unavailable)
    new = ctx.workspace / "tests" / "visible" / "test_new.py"
    new.write_text(NEW_FILE, encoding="utf-8")
    [decision] = layer.on_phase_end(ctx)
    assert "unavailable" in decision.message
    assert new.read_text(encoding="utf-8") == NEW_FILE


def test_build_phase_end_runs_no_filters(tmp_path: Path) -> None:
    def pipeline(*_a: Any) -> list[dict]:
        raise AssertionError("filters run only at the end of the test phase")

    ctx = ctx_for(tmp_path, FakeSandbox(Script([GREEN])))
    assert VerifyLayer(pipeline=pipeline).on_phase_end(ctx) == []


@pytest.mark.parametrize("name", ["tests/visible/../../x.py"])
def test_test_ids_never_leave_the_workspace(tmp_path: Path, name: str) -> None:
    from shipharness.harness.verify.testphase import remove_tests

    with pytest.raises(ValueError):
        remove_tests(tmp_path, {name: ["test_a"]})


def _written_params(sandbox: FakeSandbox) -> list[dict]:
    import base64
    import json

    return [
        json.loads(base64.b64decode(c.split()[2]))
        for c in sandbox.commands
        if c.startswith("printf") and "params.json" in c
    ]


def test_gate_leaves_exemptions_to_the_adapter_unless_given(tmp_path: Path) -> None:
    sandbox = FakeSandbox(Script([GREEN]))
    ctx = ctx_for(tmp_path, sandbox)
    VerifyLayer(baseline_json="{}").on_claim_done(ctx)
    [params] = _written_params(sandbox)
    assert "exemptions" not in params  # the runner then uses the adapter's documented exemptions


def test_baseline_and_gate_use_the_same_params(tmp_path: Path) -> None:
    script = Script([GREEN])
    sandbox = FakeSandbox(script)
    ctx = ctx_for(tmp_path, sandbox)
    layer = VerifyLayer(seed=5, exemptions={"R4": ["POST /x"]})
    layer.prepare_workspace(ctx)
    layer.on_claim_done(ctx)
    assert all("--params" in c for c in script.runner_calls)
    baseline, gate = _written_params(sandbox)
    gate.pop("artifacts_dir", None)
    baseline.pop("artifacts_dir", None)
    assert baseline == gate


def test_gate_params_report_no_new_violations_on_the_untouched_checkpoint(tmp_path: Path) -> None:
    """The documented legacy exemptions must not turn into new violations at the gate."""
    from shipharness.checks.base import CheckResult
    from shipharness.checks.runner import run_checks

    repo = find_repo_root(Path(__file__)) / "platform" / "teamtrack"
    ctx = ctx_for(tmp_path, FakeSandbox(Script([GREEN])))
    params = VerifyLayer()._params(ctx)
    kw: dict[str, Any] = dict(checkpoint="m1-s1-start", feature_id="F1", seed=5)
    base, _ = run_checks(repo, ["r4_idempotency"], **kw)  # how the baseline runs today
    baseline = {r.check: CheckResult.model_validate(r.model_dump()) for r in base}
    gate, _ = run_checks(repo, ["r4_idempotency"], params=params, baseline=baseline, **kw)
    assert [r.new_violations for r in gate] == [0]


def test_removing_the_last_method_of_a_class_keeps_the_file_valid(tmp_path: Path) -> None:
    import ast

    from shipharness.harness.verify.testphase import remove_tests

    visible = tmp_path / "tests" / "visible"
    visible.mkdir(parents=True)
    path = visible / "test_new.py"
    path.write_text(
        "class TestGroup:\n    def test_drop(self):\n        assert 1\n\n\n"
        "def test_keep():\n    assert 1\n",
        encoding="utf-8",
    )
    remove_tests(tmp_path, {"tests/visible/test_new.py": ["TestGroup::test_drop"]})
    text = path.read_text(encoding="utf-8")
    ast.parse(text)
    assert "test_drop" not in text and "def test_keep" in text


def test_baseline_that_cannot_write_its_params_is_reported_unavailable(tmp_path: Path) -> None:
    def script(command: str) -> ExecResult:
        if command.startswith("printf"):
            return ExecResult(exit_code=1, output="base64: not found", duration_ms=1)
        return ok("")

    ctx = ctx_for(tmp_path, FakeSandbox(script))
    decisions = VerifyLayer().prepare_workspace(ctx)
    assert [d.message for d in decisions] == ["gate baseline unavailable"]


def test_verify_layer_fits_baseline_and_gate_in_the_harness_time_left(tmp_path: Path) -> None:
    timeouts: list[int] = []
    script = Script([GREEN])

    class Box(FakeSandbox):
        def exec(self, command: str, timeout_s: int) -> ExecResult:
            timeouts.append(timeout_s)
            return super().exec(command, timeout_s)

    ctx = ctx_for(tmp_path, Box(script))
    ctx.time_left = lambda: 25.0
    layer = VerifyLayer(seed=5)
    layer.prepare_workspace(ctx)
    layer.on_claim_done(ctx)
    assert script.runner_calls  # the baseline and the gate both ran
    assert max(timeouts) <= 25


# --- gate baseline cache (M6 pilot: about 60 s of harness time per arm at S4 and later) ----------


def _checkpoint_ws(tmp_path: Path, name: str, message: str, body: str = "x = 1\n") -> Path:
    """A workspace whose root commit holds the checkpoint, like an arm's (commit ids differ per
    run; the tree does not)."""
    import subprocess

    ws = tmp_path / name
    (ws / "app").mkdir(parents=True)
    (ws / "app" / "main.py").write_text(body, encoding="utf-8")
    ident = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false"]
    subprocess.run(["git", *ident, "init", "-q"], cwd=ws, check=True)
    subprocess.run(["git", *ident, "add", "-A"], cwd=ws, check=True)
    subprocess.run(["git", *ident, "commit", "-qm", message], cwd=ws, check=True)
    return ws


def _prepare(ws: Path, cache: Path) -> tuple[VerifyLayer, Script, list[str]]:
    script = Script([GREEN])
    ctx = LayerContext(
        spec=make_spec(ws, checkpoint="m1-s4-start", feature_id="F4"),
        phase="build",
        session_index=1,
        turn=1,
        workspace=ws,
        sandbox=FakeSandbox(script),
        bus=None,
    )
    layer = VerifyLayer(seed=5, gate_baseline_cache_dir=cache)
    notes = [d.message for d in layer.prepare_workspace(ctx)]
    return layer, script, notes


def test_gate_baseline_is_reused_for_the_same_checkpoint_commit(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    first, first_script, first_notes = _prepare(_checkpoint_ws(tmp_path, "a", "one"), cache)
    second, second_script, second_notes = _prepare(_checkpoint_ws(tmp_path, "b", "two"), cache)
    assert len(first_script.runner_calls) == 1
    assert second_script.runner_calls == []
    assert first_notes == ["gate baseline recorded"]
    assert second_notes == ["gate baseline reused (same checkpoint commit)"]
    assert second.baseline_json == first.baseline_json


def test_gate_baseline_is_recomputed_when_the_checkpoint_differs(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    _prepare(_checkpoint_ws(tmp_path, "a", "one"), cache)
    _, script, _ = _prepare(_checkpoint_ws(tmp_path, "b", "two", body="x = 2\n"), cache)
    assert len(script.runner_calls) == 1


def test_gate_baseline_is_not_cached_without_a_checkpoint_commit(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    for name in ("a", "b"):
        ws = tmp_path / name
        ws.mkdir()
        _, script, _ = _prepare(ws, cache)
        assert len(script.runner_calls) == 1


# --- demo setting: a cap on the tests that go through the filters (make show-4 only) ----------


def _all_pass(seen: list[list[dict]]) -> Callable[..., list[dict]]:
    def pipeline(cands: list[dict], ctx: LayerContext, shas: dict[str, str]) -> list[dict]:
        seen.append(cands)
        return [
            {"test_id": c["test_id"], "filter": 5, "passed": True, "reason": "ok"} for c in cands
        ]

    return pipeline


def test_the_cap_filters_the_first_n_proposed_tests_and_removes_the_rest(tmp_path: Path) -> None:
    seen: list[list[dict]] = []
    ctx, layer = phase_ctx(tmp_path, _all_pass(seen))
    layer.max_filtered_tests = 2
    new = ctx.workspace / "tests" / "visible" / "test_new.py"
    new.write_text(NEW_FILE, encoding="utf-8")
    [decision] = layer.on_phase_end(ctx)
    assert [c["test_id"] for c in seen[0]] == [
        "tests/visible/test_new.py::test_keeps",
        "tests/visible/test_new.py::test_drops",
    ]
    assert decision.data["kept"] == [c["test_id"] for c in seen[0]]
    assert decision.data["discarded"] == {
        "tests/visible/test_new.py::TestGroup::test_method": (
            "not filtered: this demo filters only the first 2 proposed tests"
        )
    }
    text = new.read_text(encoding="utf-8")
    assert "test_method" not in text and "def test_keeps" in text


def test_without_the_cap_every_proposed_test_is_filtered(tmp_path: Path) -> None:
    seen: list[list[dict]] = []
    ctx, layer = phase_ctx(tmp_path, _all_pass(seen))
    assert VerifyLayer().max_filtered_tests is None
    (ctx.workspace / "tests" / "visible" / "test_new.py").write_text(NEW_FILE, encoding="utf-8")
    [decision] = layer.on_phase_end(ctx)
    assert len(seen[0]) == 3 and decision.data["discarded"] == {}
