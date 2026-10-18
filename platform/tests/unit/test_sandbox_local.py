from __future__ import annotations

import sys
from pathlib import Path

import pytest

from shipharness.config import Settings
from shipharness.events import EventBus, read_events
from shipharness.sandbox import ExecResult, FakeSandbox, LocalSandbox, default_policy

from .fakes import fake_openai_key

PY = f'"{sys.executable}"'


@pytest.fixture
def policy():  # type: ignore[no-untyped-def]
    return default_policy(Settings(_env_file=None))


def test_local_exec_runs_in_workspace(policy, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "marker.txt").write_text("hi", encoding="utf-8")
    sandbox = LocalSandbox(policy, tmp_path, None, "r-1", "bare")
    sandbox.start()
    result = sandbox.exec(f"{PY} -c \"print(open('marker.txt').read())\"", timeout_s=20)
    assert result.exit_code == 0
    assert "hi" in result.output


def test_local_exec_times_out(policy, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    sandbox = LocalSandbox(policy, tmp_path, None, "r-1", "bare")
    result = sandbox.exec(f'{PY} -c "import time; time.sleep(10)"', timeout_s=1)
    assert result.timed_out is True
    assert result.denied is not None
    assert result.denied.reason_code == "timeout"


def test_local_exec_hides_keys_from_child(
    policy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", fake_openai_key())
    sandbox = LocalSandbox(policy, tmp_path, None, "r-1", "bare")
    cmd = f"{PY} -c \"import os; print(os.environ.get('OPENAI_API_KEY', 'absent'))\""
    result = sandbox.exec(cmd, timeout_s=20)
    assert "absent" in result.output
    assert fake_openai_key() not in result.output


def test_local_start_is_marked_unsandboxed(policy, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id=None) as bus:
        LocalSandbox(policy, tmp_path / "ws", bus, "r-1", "bare").start()
    [start] = list(read_events(log))
    assert start.type == "sandbox_start"
    assert start.data["unsandboxed"] is True


def test_local_exec_denies_network_commands(policy, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    sandbox = LocalSandbox(policy, tmp_path, None, "r-1", "bare")
    result = sandbox.exec("pip install requests", timeout_s=5)
    assert result.denied is not None
    assert result.exit_code != 0


def test_fake_sandbox_returns_scripted_results() -> None:
    fake = FakeSandbox({"pytest": ExecResult(exit_code=1, output="1 failed", duration_ms=5)})
    assert fake.exec("pytest -q", timeout_s=5).output == "1 failed"
    assert fake.exec("ls", timeout_s=5).exit_code == 0
    assert fake.commands == ["pytest -q", "ls"]


def test_local_exec_honours_a_harness_timeout_above_the_tool_cap(policy, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    # The per-tool cap applies to agent tool calls (runner/tools.py); harness commands such as the
    # referee and the verify gate pass their own, longer timeouts.
    capped = policy.model_copy(update={"tool_timeout_s": 1})
    sandbox = LocalSandbox(capped, tmp_path, None, "r-1", "bare")
    result = sandbox.exec(f'{PY} -c "import time; time.sleep(2)"', timeout_s=30)
    assert result.timed_out is False
    assert result.exit_code == 0
