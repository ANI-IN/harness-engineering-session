"""UNSANDBOXED fallback: commands run on the host in the workspace with timeouts only."""

from __future__ import annotations

import contextlib
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from shipharness.events import Arm, EventBus
from shipharness.sandbox._events import emit_denial
from shipharness.sandbox.base import ExecResult
from shipharness.sandbox.policy import SandboxPolicy, check_command, detect_denial

UNSANDBOXED_BANNER = "UNSANDBOXED — results not official"
_SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD", re.IGNORECASE)


def _child_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not _SECRET_NAME.search(k)}


def _kill_tree(proc: subprocess.Popen[bytes]) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, check=False
        )
    else:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)


class LocalSandbox:
    def __init__(
        self, policy: SandboxPolicy, workspace: Path, bus: EventBus | None, run_id: str, arm: Arm
    ) -> None:
        self.policy = policy
        self.workspace = Path(workspace)
        self.bus = bus
        self.run_id = run_id
        self.arm = arm

    def start(self) -> str:
        self.workspace.mkdir(parents=True, exist_ok=True)
        if self.bus is not None:
            self.bus.publish(
                "sandbox_start",
                {
                    "container_id": "local",
                    "image": "host",
                    "network": "host",
                    "cpus": 0.0,
                    "memory_mb": 0,
                    "pids_limit": 0,
                    "user": "host",
                    "read_only_root": False,
                    "unsandboxed": True,
                },
                run_id=self.run_id,
                arm=self.arm,
            )
        return "local"

    def exec(self, command: str, timeout_s: int) -> ExecResult:
        denial = check_command(self.policy, command)
        if denial is not None:
            emit_denial(self.bus, self.run_id, self.arm, denial, command)
            return ExecResult(
                exit_code=126,
                output=f"DENIED by sandbox: {denial.detail}",
                duration_ms=0,
                denied=denial,
            )
        # The caller sets the limit: agent tool calls are capped at the tool timeout in
        # runner/tools.py; harness commands (gate, referee) pass their own, longer limits.
        kwargs: dict[str, object] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        started = time.monotonic()
        proc = subprocess.Popen(  # noqa: S602 - the fallback runs agent commands through a shell
            command,
            shell=True,
            cwd=self.workspace,
            env=_child_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            **kwargs,  # type: ignore[arg-type]
        )
        timed_out = False
        try:
            raw, _ = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_tree(proc)
            raw, _ = proc.communicate()
        output = (raw or b"").decode("utf-8", errors="replace")
        exit_code = 124 if timed_out else proc.returncode
        duration_ms = int((time.monotonic() - started) * 1000)
        denial = detect_denial(self.policy, output, exit_code, False, timed_out)
        if denial is not None:
            emit_denial(self.bus, self.run_id, self.arm, denial, command)
        return ExecResult(
            exit_code=exit_code,
            output=output,
            duration_ms=duration_ms,
            timed_out=timed_out,
            denied=denial,
        )

    def usage(self) -> dict[str, float]:
        return {"cpu_pct": 0.0, "mem_mb": 0.0, "mem_limit_mb": 0.0, "pids": 0}

    def stop(self) -> None:
        return None
