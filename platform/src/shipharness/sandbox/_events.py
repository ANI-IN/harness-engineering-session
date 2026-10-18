"""Shared event emission for sandbox runtimes."""

from __future__ import annotations

from shipharness.events import Arm, EventBus
from shipharness.sandbox.base import SandboxDenial


def emit_denial(
    bus: EventBus | None, run_id: str, arm: Arm, denial: SandboxDenial, command: str
) -> None:
    if bus is None:
        return
    bus.publish(
        "sandbox_denied",
        {"command": command[:500], "reason_code": denial.reason_code, "detail": denial.detail},
        run_id=run_id,
        arm=arm,
    )
