"""Scripted sandbox for unit tests: returns canned results by command prefix."""

from __future__ import annotations

from collections.abc import Callable

from shipharness.sandbox.base import ExecResult


class FakeSandbox:
    def __init__(
        self,
        script: dict[str, ExecResult] | Callable[[str], ExecResult] | None = None,
        default: ExecResult | None = None,
    ) -> None:
        self.script = script or {}
        self.default = default or ExecResult(exit_code=0, output="", duration_ms=1)
        self.commands: list[str] = []
        self.started = False
        self.stopped = False

    def start(self) -> str:
        self.started = True
        return "fake"

    def exec(self, command: str, timeout_s: int) -> ExecResult:
        self.commands.append(command)
        if callable(self.script):
            return self.script(command)
        for prefix, result in self.script.items():
            if command.startswith(prefix):
                return result
        return self.default

    def usage(self) -> dict[str, float]:
        return {"cpu_pct": 0.0, "mem_mb": 0.0, "mem_limit_mb": 0.0, "pids": 0}

    def stop(self) -> None:
        self.stopped = True
