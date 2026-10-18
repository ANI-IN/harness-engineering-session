"""Evidence-gated `passes`: only the harness sets it, and only with evidence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shipharness.harness.scope.layer import ScopeLayer
from shipharness.runner.models import SessionResult
from shipharness.sandbox import ExecResult, FakeSandbox

from .helpers import make_ctx

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
PASSING = ExecResult(exit_code=0, output="....\n4 passed in 0.31s\n", duration_ms=5)
FAILING = ExecResult(
    exit_code=1,
    output="FAILED tests/visible/test_a.py::test_x - assert 1 == 2\n1 failed, 3 passed in 0.4s\n",
    duration_ms=5,
)
GATE_PASS = {
    "gate_id": "gate-7",
    "passed": True,
    "feedback": "",
    "items": [
        {"name": "visible tests", "status": "pass", "detail": "passed 41/41"},
        {"name": "existing tests", "status": "pass", "detail": "38/38 keep passing"},
        {"name": "R1", "status": "pass", "detail": ""},
        {"name": "R4", "status": "pass", "detail": ""},
        {"name": "clean state", "status": "pass", "detail": ""},
    ],
}


def session(ended_by: str = "claim_done", phase: str = "build") -> SessionResult:
    return SessionResult(
        index=1, phase=phase, turns=4, ended_by=ended_by, start_sha="a" * 40, end_sha="b" * 40
    )  # type: ignore[arg-type]


def prepared(tmp_path: Path, sandbox: Any = None, **spec: Any):  # type: ignore[no-untyped-def]
    ctx = make_ctx(tmp_path / "ws", sandbox or FakeSandbox(), **spec)
    git = ctx.workspace / ".git"
    git.mkdir()
    (git / "HEAD").write_text("c" * 40 + "\n", encoding="utf-8")
    layer = ScopeLayer(now=lambda: NOW)
    layer.prepare_workspace(ctx)
    return ctx, layer


def feature(ctx) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    data = json.loads((ctx.workspace / "feature_list.json").read_text(encoding="utf-8"))
    return data["features"][0]


def test_gate_pass_and_done_claim_set_passes_with_evidence(tmp_path: Path) -> None:
    sandbox = FakeSandbox()
    ctx, layer = prepared(tmp_path, sandbox, layers=frozenset({"state", "scope", "verify"}))
    ctx.state["last_claim"] = {"phase": "build", "claim": "done", "summary": "done"}
    ctx.state["verify.gate"] = GATE_PASS
    decisions = layer.on_session_end(ctx, session())
    entry = feature(ctx)
    assert entry["passes"] is True
    assert entry["testedAt"] == "2026-10-16T12:00:00Z"
    assert entry["evidence"] == {
        "gate_id": "gate-7",
        "commit": "c" * 40,
        "visible": "41/41",
        "existing": "38/38",
        "checks": ["R1", "R4"],
    }
    assert ctx.state["scope.passes_set"] is True
    assert [d.kind for d in decisions] == ["status_set"]
    assert decisions[0].data["evidence"]["gate_id"] == "gate-7"
    assert any("commit" in c and "feature_list.json" in c for c in sandbox.commands[1:])


def test_failed_gate_leaves_passes_false(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path, layers=frozenset({"scope", "verify"}))
    ctx.state["last_claim"] = {"phase": "build", "claim": "done", "summary": ""}
    ctx.state["verify.gate"] = {**GATE_PASS, "passed": False}
    decisions = layer.on_session_end(ctx, session("turn_budget"))
    assert feature(ctx)["passes"] is False
    assert "scope.passes_set" not in ctx.state
    assert [d.kind for d in decisions] == ["note"]
    assert "gate" in decisions[0].message


def test_missing_gate_with_verify_on_leaves_passes_false(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path, layers=frozenset({"scope", "verify"}))
    ctx.state["last_claim"] = {"phase": "build", "claim": "done", "summary": ""}
    layer.on_session_end(ctx, session())
    assert feature(ctx)["passes"] is False


def test_not_done_claim_sets_nothing_and_runs_nothing(tmp_path: Path) -> None:
    sandbox = FakeSandbox(default=PASSING)
    ctx, layer = prepared(tmp_path, sandbox)
    ctx.state["last_claim"] = {"phase": "build", "claim": "not_done", "summary": ""}
    commands_before = list(sandbox.commands)
    assert layer.on_session_end(ctx, session("claim_not_done")) == []
    assert feature(ctx)["passes"] is False
    assert sandbox.commands == commands_before


def test_verify_off_uses_the_visible_tests_in_the_sandbox(tmp_path: Path) -> None:
    sandbox = FakeSandbox({"python -m pytest tests/visible": PASSING})
    ctx, layer = prepared(tmp_path, sandbox)
    ctx.state["last_claim"] = {"phase": "build", "claim": "done", "summary": ""}
    decisions = layer.on_session_end(ctx, session())
    entry = feature(ctx)
    assert entry["passes"] is True
    assert entry["evidence"]["visible"] == "4/4"
    assert entry["evidence"]["gate_id"] == "visible-tests"
    assert entry["evidence"]["commit"] == "c" * 40
    assert decisions[0].kind == "status_set"
    assert any(c.startswith("python -m pytest tests/visible") for c in sandbox.commands)


def test_verify_off_with_failing_visible_tests_leaves_passes_false(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path, FakeSandbox({"python -m pytest": FAILING}))
    ctx.state["last_claim"] = {"phase": "build", "claim": "done", "summary": ""}
    decisions = layer.on_session_end(ctx, session())
    assert feature(ctx)["passes"] is False
    assert "visible tests" in decisions[0].message


def test_verify_off_with_no_tests_collected_leaves_passes_false(tmp_path: Path) -> None:
    empty = ExecResult(exit_code=5, output="no tests ran in 0.01s\n", duration_ms=1)
    ctx, layer = prepared(tmp_path, FakeSandbox({"python -m pytest": empty}))
    ctx.state["last_claim"] = {"phase": "build", "claim": "done", "summary": ""}
    layer.on_session_end(ctx, session())
    assert feature(ctx)["passes"] is False


def test_claim_from_an_earlier_phase_does_not_count(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path, FakeSandbox({"python -m pytest": PASSING}))
    ctx.state["last_claim"] = {"phase": "test", "claim": "done", "summary": ""}
    layer.on_session_end(ctx, session())
    assert feature(ctx)["passes"] is False


def test_test_phase_never_sets_passes(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path, FakeSandbox({"python -m pytest": PASSING}))
    ctx.phase = "test"
    ctx.state["last_claim"] = {"phase": "test", "claim": "done", "summary": ""}
    layer.on_session_end(ctx, session(phase="test"))
    assert feature(ctx)["passes"] is False


def test_passes_is_set_once(tmp_path: Path) -> None:
    sandbox = FakeSandbox({"python -m pytest": PASSING})
    ctx, layer = prepared(tmp_path, sandbox)
    ctx.state["last_claim"] = {"phase": "build", "claim": "done", "summary": ""}
    layer.on_session_end(ctx, session())
    count = len(sandbox.commands)
    assert layer.on_session_end(ctx, session()) == []
    assert len(sandbox.commands) == count


def test_without_last_claim_a_claim_done_session_end_counts(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path, FakeSandbox({"python -m pytest": PASSING}))
    layer.on_session_end(ctx, session("claim_done"))
    assert feature(ctx)["passes"] is True


def test_status_rewrites_the_harness_copy_even_if_the_file_was_tampered(tmp_path: Path) -> None:
    ctx, layer = prepared(tmp_path, FakeSandbox({"python -m pytest": PASSING}))
    (ctx.workspace / "feature_list.json").write_text('{"features": []}', encoding="utf-8")
    ctx.state["last_claim"] = {"phase": "build", "claim": "done", "summary": ""}
    layer.on_session_end(ctx, session())
    assert feature(ctx)["id"] == "F3" and feature(ctx)["passes"] is True
