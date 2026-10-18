from __future__ import annotations

import base64
import json
import shlex
from collections.abc import Callable

from shipharness.harness.verify.gate import GATE_CHECKS, GateConfig, run_gate
from shipharness.harness.verify.models import GateResult
from shipharness.sandbox import ExecResult, FakeSandbox

from .fakes import ALL_GATE_CHECKS, check_result, fail, ok, runner_output

PYTEST_OK = "12 passed in 1.20s\n"
PYTEST_FAIL = (
    "FAILED tests/visible/test_a.py::test_one - AssertionError: 1 != 2\n"
    "1 failed, 11 passed in 1.3s\n"
)


def script(
    results: list[dict] | None = None,
    pytest_out: ExecResult | None = None,
    runner: ExecResult | None = None,
) -> Callable[[str], ExecResult]:
    results = results if results is not None else [check_result(c) for c in ALL_GATE_CHECKS]

    def run(command: str) -> ExecResult:
        if "-m shipharness.checks.runner" in command:
            return runner or ok(runner_output(results, command=command))
        if "-m pytest" in command:
            return pytest_out or ok(PYTEST_OK)
        if command.startswith("alembic heads"):
            return ok("abc (head)\n")
        return ok("")

    return run


def config(**overrides: object) -> GateConfig:
    base: dict[str, object] = {"checkpoint": "m1-s1-start", "feature": "F1", "seed": 11}
    base.update(overrides)
    return GateConfig(**base)  # type: ignore[arg-type]


def test_gate_checks_are_the_i8_set_and_never_referee_only() -> None:
    assert list(GATE_CHECKS) == ALL_GATE_CHECKS
    assert "hidden_tests" not in GATE_CHECKS and "flakiness" not in GATE_CHECKS


def test_all_green_gate_passes_with_every_item() -> None:
    sandbox = FakeSandbox(script())
    result = run_gate(sandbox, config(), gate_id="g1", base_sha="", phase="build")
    assert result.passed
    names = [i.name for i in result.items]
    assert names == [
        "visible tests",
        "existing tests",
        "R1",
        "R2",
        "R3",
        "R4",
        "R5",
        "R6",
        "R7",
        "board",
        "clean state",
    ]
    assert all(i.status == "pass" for i in result.items)
    assert result.feedback == ""


def test_gate_runs_checks_on_a_copy_in_tmp_not_the_workspace() -> None:
    sandbox = FakeSandbox(script())
    run_gate(sandbox, config(), gate_id="g1", base_sha="", phase="build")
    [runner_cmd] = [c for c in sandbox.commands if "-m shipharness.checks.runner" in c]
    argv = shlex.split(runner_cmd.split("&&")[-1])
    build = argv[argv.index("--build") + 1]
    assert build.startswith("/tmp/shipharness-gate-g1/")
    assert argv[argv.index("--seed") + 1] == "11"
    assert argv[argv.index("--checks") + 1] == ",".join(ALL_GATE_CHECKS)
    assert any(c.startswith("rm -rf /tmp/shipharness-gate-g1") for c in sandbox.commands)


def test_gate_passes_params_and_baseline_as_files() -> None:
    sandbox = FakeSandbox(script())
    cfg = config(params={"exemptions": {"R4": ["POST /x"]}}, baseline_json='{"results": []}')
    run_gate(sandbox, cfg, gate_id="g2", base_sha="", phase="build")
    written = {}
    for c in sandbox.commands:
        if c.startswith("printf %s"):
            parts = c.split()
            written[parts[-1]] = base64.b64decode(parts[2]).decode()
    params = json.loads(written["/tmp/shipharness-gate-g2/params.json"])
    assert params["exemptions"] == {"R4": ["POST /x"]}
    assert params["artifacts_dir"].startswith("/tmp/shipharness-gate-g2/")
    assert written["/tmp/shipharness-gate-g2/baseline.json"] == '{"results": []}'


def test_failures_give_feedback_with_the_first_three_failures() -> None:
    results = [check_result(c) for c in ALL_GATE_CHECKS]
    results[0] = check_result("r1_tenant", new=2)
    results[1] = check_result("r2_roles", new=2)
    sandbox = FakeSandbox(script(results=results, pytest_out=fail(PYTEST_FAIL)))
    result = run_gate(sandbox, config(), gate_id="g3", base_sha="", phase="build")
    assert not result.passed
    status = {i.name: i.status for i in result.items}
    assert status["visible tests"] == "fail"
    assert status["R1"] == "fail" and status["R2"] == "fail" and status["R3"] == "pass"
    lines = [ln for ln in result.feedback.splitlines() if ln.startswith(("FAIL", "FAILED"))]
    assert len(lines) == 3
    assert lines[0].startswith("FAILED tests/visible/test_a.py::test_one")
    assert lines[1] == "FAIL House rule 1 GET /x/0: violation: r1_tenant problem 0"
    summary = result.feedback.splitlines()[0]
    assert "(visible tests, House rule 1: Tenant isolation, House rule 2: Roles)" in summary
    assert "g3" in result.feedback


def test_runner_crash_fails_every_check_item() -> None:
    sandbox = FakeSandbox(script(runner=fail("ImportError: cannot import name 'x'\n")))
    result = run_gate(sandbox, config(), gate_id="g4", base_sha="", phase="build")
    assert not result.passed
    r1 = next(i for i in result.items if i.name == "R1")
    assert r1.status == "fail" and "check runner" in r1.detail


def test_check_missing_from_runner_output_is_skipped_not_passed() -> None:
    results = [check_result(c) for c in ALL_GATE_CHECKS if c != "board"]
    result = run_gate(
        FakeSandbox(script(results=results)), config(), gate_id="g5", base_sha="", phase="build"
    )
    board = next(i for i in result.items if i.name == "board")
    assert board.status == "skipped"
    assert result.passed


def test_test_phase_gate_runs_only_visible_tests_and_clean_state() -> None:
    sandbox = FakeSandbox(script())
    result = run_gate(sandbox, config(), gate_id="g6", base_sha="", phase="test")
    assert [i.name for i in result.items] == ["visible tests", "clean state"]
    assert not any("checks.runner" in c for c in sandbox.commands)


def test_teamtrack_gate_runs_tests_visible_and_the_head_check() -> None:
    sandbox = FakeSandbox(script())
    run_gate(sandbox, config(), gate_id="g7", base_sha="", phase="test")
    [pytest_cmd] = [c for c in sandbox.commands if "-m pytest" in c]
    assert "python -m pytest tests/visible -q -rfE --no-header -p no:cacheprovider" in pytest_cmd
    assert "alembic heads" in sandbox.commands


def test_gate_on_a_repository_with_tests_in_tests_and_no_migrations() -> None:
    """The boltons worked example: visible tests are the run's directory (tests/), and the clean
    state item skips the migration head check instead of failing on a missing alembic.ini."""

    def run(command: str) -> ExecResult:
        if "-m pytest tests/visible" in command:
            return fail(
                "ERROR: file or directory not found: tests/visible\n\nno tests ran in 0.01s"
            )
        if "-m pytest" in command:
            return ok("6 passed in 0.30s\n")
        if command.startswith("alembic"):
            return fail("FAILED: No 'script_location' key found in configuration.")
        return ok("")

    sandbox = FakeSandbox(run)
    cfg = config(visible_tests_dir="tests", migrations=False)
    result = run_gate(sandbox, cfg, gate_id="g8", base_sha="", phase="test")
    assert result.passed, result.feedback
    visible, clean = result.items
    assert visible.detail == "passed=6 failed=0 errors=0"
    assert "skipped: no migrations configured" in clean.detail
    assert not any(c.startswith("alembic") for c in sandbox.commands)


def test_updates_start_pending_and_progress_is_reported() -> None:
    updates: list[GateResult] = []
    progress: list[dict] = []
    run_gate(
        FakeSandbox(script()),
        config(),
        gate_id="g7",
        base_sha="",
        phase="build",
        on_update=updates.append,
        on_progress=progress.append,
    )
    assert all(i.status == "pending" for i in updates[0].items)
    assert updates[-1].passed
    assert {p["check"] for p in progress} == set(ALL_GATE_CHECKS)
    assert all(p["done"] == 2 for p in progress)


def test_every_gate_command_fits_in_the_harness_time_left() -> None:
    timeouts: list[int] = []
    base = script()

    def recording(command: str) -> ExecResult:
        return base(command)

    class Box(FakeSandbox):
        def exec(self, command: str, timeout_s: int) -> ExecResult:
            timeouts.append(timeout_s)
            return super().exec(command, timeout_s)

    cfg = config(baseline_json='{"results": []}')
    cfg.time_left = lambda: 40.0
    run_gate(Box(recording), cfg, gate_id="g9", base_sha="abc", phase="build")
    assert timeouts and max(timeouts) <= 40


def test_a_failed_input_write_fails_the_check_items_instead_of_crashing() -> None:
    base = script()

    def slow_write(command: str) -> ExecResult:
        if command.startswith("printf %s"):  # the params write times out near the limit
            return ExecResult(exit_code=124, output="timed out", duration_ms=1000, timed_out=True)
        return base(command)

    sandbox = FakeSandbox(slow_write)
    cfg = config(baseline_json='{"results": []}')
    cfg.time_left = lambda: 2.0
    result = run_gate(sandbox, cfg, gate_id="g11", base_sha="abc", phase="build")
    assert not result.passed
    status = {i.name: i for i in result.items}
    assert status["visible tests"].status == "pass" and status["clean state"].status == "pass"
    for name in ("existing tests", "R1", "R7", "board"):
        assert status[name].status == "fail"
        assert "could not write the check inputs" in status[name].detail
    assert not any("checks.runner" in c for c in sandbox.commands)
    assert "could not write the check inputs" in result.feedback


def test_gate_commands_keep_their_own_limits_without_a_harness_limit() -> None:
    timeouts: list[int] = []

    class Box(FakeSandbox):
        def exec(self, command: str, timeout_s: int) -> ExecResult:
            timeouts.append(timeout_s)
            return super().exec(command, timeout_s)

    run_gate(Box(script()), config(), gate_id="g10", base_sha="abc", phase="build")
    assert max(timeouts) == 600  # the gate's own limit
