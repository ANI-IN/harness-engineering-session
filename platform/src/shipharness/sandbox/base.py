"""Sandbox protocol and result types."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

ReasonCode = Literal[
    "network",
    "write_outside_workspace",
    "memory",
    "pids",
    "timeout",
    "path_outside_workspace",
]


class SandboxDenial(BaseModel):
    model_config = ConfigDict(frozen=True)

    reason_code: ReasonCode
    detail: str
    command: str = ""


class ExecResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    exit_code: int
    output: str  # combined stdout + stderr, untruncated (the runner truncates)
    duration_ms: int
    timed_out: bool = False
    denied: SandboxDenial | None = None


class Sandbox(Protocol):
    def start(self) -> str: ...
    def exec(self, command: str, timeout_s: int) -> ExecResult: ...
    def usage(self) -> dict[str, float]: ...
    def stop(self) -> None: ...
