"""One visible-suite run per workspace content (harness/suite_cache.py): the gate, the session stop,
and the passes update reuse an identical run, and give the same results as running it again."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from shipharness.harness import suite_cache
from shipharness.harness.base import LayerContext
from shipharness.harness.scope.status import VISIBLE_TESTS_ARGS, _visible_tests_evidence
from shipharness.harness.state import handoff
from shipharness.harness.verify.gate import run_gate
from shipharness.runner.models import AgentRunSpec
from shipharness.sandbox import ExecResult, FakeSandbox

from .fakes import ALL_GATE_CHECKS, check_result, ok, runner_output
from .test_gate import config

PASSING = "12 passed in 1.20s\n"
FAILING = (
    "FAILED tests/visible/test_a.py::test_one - AssertionError: 1 != 2\n"
    "1 failed, 11 passed in 1.3s\n"
)


def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / "app").mkdir(parents=True)
    (ws / "tests" / "visible").mkdir(parents=True)
    (ws / "app" / "mod.py").write_text("X = 1\n", encoding="utf-8")
    (ws / "tests" / "visible" / "test_a.py").write_text("def test_one(): pass\n", "utf-8")
    return ws


def scripted(pytest_output: str, exit_code: int = 0) -> Callable[[str], ExecResult]:
    def run(command: str) -> ExecResult:
        if "-m shipharness.checks.runner" in command:
            return ok(runner_output([check_result(c) for c in ALL_GATE_CHECKS], command=command))
        if "-m pytest" in command:
            return ExecResult(exit_code=exit_code, output=pytest_output, duration_ms=1)
        if command.startswith("alembic heads"):
            return ok("abc (head)\n")
        return ok("")

    return run


def pytest_runs(sandbox: FakeSandbox) -> int:
    return sum("-m pytest" in c for c in sandbox.commands)


def ctx_for(ws: Path, sandbox: FakeSandbox, state: dict[str, Any]) -> LayerContext:
    spec = AgentRunSpec(
        run_id="r",
        arm="harness",
        feature_id="F4",
        checkpoint="m1-s4-start",
        ticket_text="t",
        model="m",
        reasoning_effort="low",
        workspace=ws,
    )
    return LayerContext(
        spec=spec,
        phase="build",
        session_index=1,
        turn=1,
        workspace=ws,
        sandbox=sandbox,
        state=state,
    )


def test_the_key_follows_code_and_tests_but_not_git_or_the_notes_files(tmp_path: Path) -> None:
    ws = workspace(tmp_path)
    first = suite_cache.content_key(ws)
    (ws / ".git").mkdir()
    (ws / ".git" / "index").write_bytes(b"refreshed")
    (ws / "progress.md").write_text("## Session 1\n", encoding="utf-8")
    (ws / "session-handoff.md").write_text("## Machine summary\n", encoding="utf-8")
    assert suite_cache.content_key(ws) == first
    (ws / "tests" / "visible" / "test_a.py").write_text("def test_one(): assert 0\n", "utf-8")
    assert suite_cache.content_key(ws) != first
    (ws / "tests" / "visible" / "test_a.py").write_text("def test_one(): pass\n", "utf-8")
    (ws / "app" / "data.json").write_text("{}", encoding="utf-8")  # an untracked file counts
    assert suite_cache.content_key(ws) != first


def test_session_stop_after_a_passing_gate_reuses_its_run_with_the_same_line(
    tmp_path: Path,
) -> None:
    ws = workspace(tmp_path)
    cached_box, state = FakeSandbox(scripted(PASSING)), {}
    reuse = (state, suite_cache.content_key(ws))
    gate = run_gate(
        cached_box, config(visible_reuse=reuse), gate_id="g1", base_sha="", phase="build"
    )
    assert gate.passed and pytest_runs(cached_box) == 1
    cached = handoff.visible_tests(cached_box, 60, state=state, workspace=ws)
    assert pytest_runs(cached_box) == 1  # no second run
    fresh = handoff.visible_tests(FakeSandbox(scripted(PASSING)), 60)
    assert cached == fresh == ("passed=12 failed=0 errors=0", [])


def test_a_failing_gate_run_is_not_reused_in_the_workspace(tmp_path: Path) -> None:
    ws = workspace(tmp_path)
    box, state = FakeSandbox(scripted(FAILING, exit_code=1)), {}
    reuse = (state, suite_cache.content_key(ws))
    gate = run_gate(box, config(visible_reuse=reuse), gate_id="g1", base_sha="", phase="build")
    assert not gate.passed
    line = handoff.visible_tests(box, 60, state=state, workspace=ws)
    assert pytest_runs(box) == 2  # failure text may name paths: run again in the workspace
    assert line == handoff.visible_tests(FakeSandbox(scripted(FAILING, exit_code=1)), 60)


def test_passes_update_after_the_session_stop_reuses_the_run_across_the_notes_commit(
    tmp_path: Path,
) -> None:
    ws = workspace(tmp_path)
    box, state = FakeSandbox(scripted(FAILING, exit_code=1)), {}
    stop_line = handoff.visible_tests(box, 60, state=state, workspace=ws)
    (ws / "session-handoff.md").write_text("## Machine summary\n", encoding="utf-8")
    (ws / "progress.md").write_text("## Session 1\n", encoding="utf-8")
    cached = _visible_tests_evidence(ctx_for(ws, box, state), 60)
    assert pytest_runs(box) == 1
    fresh_box = FakeSandbox(scripted(FAILING, exit_code=1))
    assert cached == _visible_tests_evidence(ctx_for(ws, fresh_box, {}), 60)
    assert pytest_runs(fresh_box) == 1
    assert stop_line[0].startswith("passed=11 failed=1")


def test_a_changed_workspace_runs_the_suite_again(tmp_path: Path) -> None:
    ws = workspace(tmp_path)
    box, state = FakeSandbox(scripted(PASSING)), {}
    handoff.visible_tests(box, 60, state=state, workspace=ws)
    (ws / "app" / "mod.py").write_text("X = 2\n", encoding="utf-8")
    handoff.visible_tests(box, 60, state=state, workspace=ws)
    assert pytest_runs(box) == 2


def test_timed_out_or_denied_runs_are_never_reused(tmp_path: Path) -> None:
    ws = workspace(tmp_path)
    state: dict[str, Any] = {}
    key = suite_cache.content_key(ws)
    slow = ExecResult(exit_code=124, output="", duration_ms=1, timed_out=True)
    suite_cache.store(state, key, VISIBLE_TESTS_ARGS, "workspace", slow)
    assert suite_cache.lookup(state, key, VISIBLE_TESTS_ARGS, "workspace") is None


def test_different_pytest_arguments_never_share_a_result(tmp_path: Path) -> None:
    ws = workspace(tmp_path)
    state: dict[str, Any] = {}
    key = suite_cache.content_key(ws)
    suite_cache.store(state, key, VISIBLE_TESTS_ARGS, "workspace", ok(PASSING))
    assert suite_cache.lookup(state, key, "tests -q", "workspace") is None
    assert suite_cache.lookup(state, key, VISIBLE_TESTS_ARGS, "copy") is not None


def test_without_state_every_call_runs_the_suite(tmp_path: Path) -> None:
    box = FakeSandbox(scripted(PASSING))
    handoff.visible_tests(box, 60)
    handoff.visible_tests(box, 60)
    assert pytest_runs(box) == 2
