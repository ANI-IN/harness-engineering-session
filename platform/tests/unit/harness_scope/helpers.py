"""Shared helpers for the scope and state layer tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shipharness.harness.base import LayerContext
from shipharness.runner.models import AgentRunSpec, ToolCall
from shipharness.sandbox import FakeSandbox

ALLOWED = {
    "build": ["app/api/issues.py", "app/services/*.py", "tests/visible/**"],
    "test": ["tests/visible/**"],
}
TICKET = """Idempotency keys on create-issue

- POST /projects/{id}/issues with Idempotency-Key twice returns the same issue
- A different key creates a second issue
"""


def make_spec(ws: Path, **overrides: Any) -> AgentRunSpec:
    base: dict[str, Any] = dict(
        run_id="r-1",
        arm="harness",
        feature_id="F3",
        checkpoint="m1-s3-start",
        ticket_text=TICKET,
        model="gpt-6-luna",
        reasoning_effort="low",
        layers=frozenset({"state", "scope"}),
        phases=("build", "test"),
        session_budget=[6, 6],
        allowed_paths=ALLOWED,
        workspace=ws,
    )
    base.update(overrides)
    return AgentRunSpec(**base)


def make_ctx(ws: Path, sandbox: Any = None, bus: Any = None, **spec_overrides: Any) -> LayerContext:
    ws.mkdir(parents=True, exist_ok=True)
    spec = make_spec(ws, **spec_overrides)
    return LayerContext(
        spec=spec,
        phase=spec.phases[0],
        session_index=1,
        turn=0,
        workspace=ws,
        sandbox=sandbox or FakeSandbox(),
        bus=bus,
    )


def call(name: str, call_id: str = "c1", **arguments: Any) -> ToolCall:
    return ToolCall(call_id=call_id, name=name, arguments=arguments)  # type: ignore[arg-type]


def patch_for(path: str, old: str | None, new: str) -> str:
    """A minimal unified diff that replaces one line (or creates the file when old is None)."""
    if old is None:
        return f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1 @@\n+{new}\n"
    return f"--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-{old}\n+{new}\n"
