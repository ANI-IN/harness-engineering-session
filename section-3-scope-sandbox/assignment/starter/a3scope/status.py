"""Part B: the evidence-gated status update. The harness, not the agent, sets `passes`.

The interface follows src/shipharness/harness/scope/status.py (`update_status`), without the
layer context: the caller passes what the session left behind, the sandbox, and a clock.
README "Detailed requirements, Part B" lists every rule.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from shipharness.sandbox import Sandbox

VISIBLE_TESTS_COMMAND = "python -m pytest tests/visible -q -rfE --no-header -p no:cacheprovider"


@dataclass(frozen=True)
class SessionEnd:
    phase: str  # phase of the session that just ended ("build", "test")
    last_claim: dict[str, Any] | None  # the agent's last finish(): {"phase", "claim", "summary"}
    verify_layer: bool  # True: the verify gate result is the evidence
    gate: dict[str, Any] | None  # verify gate result (GateResult.model_dump shape) or None
    head_commit: str  # HEAD after the session
    passes_already_set: bool = False


@dataclass(frozen=True)
class StatusDecision:
    kind: Literal["status_set", "note", "none"]
    message: str
    document: dict[str, Any]  # the feature-list document to write (a new object)
    evidence: dict[str, Any] | None = None


def update_status(
    document: dict[str, Any],
    feature_id: str,
    end: SessionEnd,
    sandbox: Sandbox,
    now: Callable[[], datetime],
    test_timeout_s: int = 300,
) -> StatusDecision:
    """Set `passes` for `feature_id` if, and only if, the evidence is there.

    Never changes `document`; returns a new one. Runs the visible tests (once) only when the
    verify layer is off and every other condition holds.
    """
    # TODO(A3 Part B): no done claim for the build phase -> "none" and nothing run; verify on ->
    # the gate is the evidence; verify off -> run VISIBLE_TESTS_COMMAND and read the pytest
    # summary. Any doubt -> "note" and passes stays false.
    raise NotImplementedError("TODO(A3 Part B): update_status")
