"""Visible tests: evidence-gated status updates (README "Part B").

test_status_sets_* : the evidence is there, so `passes` becomes true with evidence and testedAt.
test_status_keeps_*: something is missing, so the document is unchanged.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any

from shipharness.sandbox import ExecResult, FakeSandbox

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
HEAD = "c0ffee" + "0" * 34
DOC: dict[str, Any] = {
    "$schema": "./feature_list.schema.json",
    "features": [
        {
            "id": "F3",
            "category": "api",
            "description": "Idempotency keys on create-issue",
            "steps": ["POST twice with one key returns the same issue"],
            "passes": False,
            "evidence": None,
            "testedAt": None,
        }
    ],
}
GATE_PASS: dict[str, Any] = {
    "gate_id": "gate-3",
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
DONE = {"phase": "build", "claim": "done", "summary": "F3 done"}


def end(**overrides: Any):  # type: ignore[no-untyped-def]
    from a3scope.status import SessionEnd

    values: dict[str, Any] = {
        "phase": "build",
        "last_claim": DONE,
        "verify_layer": True,
        "gate": GATE_PASS,
        "head_commit": HEAD,
    }
    values.update(overrides)
    return SessionEnd(**values)


def run(session_end, sandbox=None):  # type: ignore[no-untyped-def]
    from a3scope.status import update_status

    box = sandbox or FakeSandbox()
    doc = copy.deepcopy(DOC)
    decision = update_status(doc, "F3", session_end, box, lambda: NOW)
    assert doc == DOC, "update_status must not change the document it was given"
    return decision, box


def test_status_sets_passes_from_a_passed_gate() -> None:
    decision, box = run(end())
    assert decision.kind == "status_set"
    feature = decision.document["features"][0]
    assert feature["passes"] is True
    assert feature["testedAt"] == "2026-10-16T12:00:00Z"
    assert feature["evidence"] == {
        "gate_id": "gate-3",
        "commit": HEAD,
        "visible": "41/41",
        "existing": "38/38",
        "checks": ["R1", "R4"],
    }
    assert decision.evidence == feature["evidence"]
    assert box.commands == []  # the gate already ran; nothing is re-run
    assert "F3" in decision.message and HEAD[:7] in decision.message


def test_status_sets_passes_from_visible_tests_when_verify_is_off() -> None:
    from a3scope.status import VISIBLE_TESTS_COMMAND

    box = FakeSandbox(
        default=ExecResult(exit_code=0, output="....\n4 passed in 0.31s\n", duration_ms=5)
    )
    decision, box = run(end(verify_layer=False, gate=None), box)
    assert decision.kind == "status_set"
    assert box.commands == [VISIBLE_TESTS_COMMAND]
    assert decision.evidence == {
        "gate_id": "visible-tests",
        "commit": HEAD,
        "visible": "4/4",
        "existing": "not run (verify layer off)",
        "checks": [],
    }


def test_status_keeps_false_without_a_done_claim() -> None:
    decision, box = run(end(last_claim=None, verify_layer=False))
    assert decision.kind == "none"
    assert decision.document == DOC
    assert box.commands == []  # no claim: nothing is run


def test_status_keeps_false_when_the_gate_failed() -> None:
    decision, _ = run(end(gate={**GATE_PASS, "passed": False}))
    assert decision.kind == "note"
    assert decision.document == DOC
    assert decision.evidence is None
    assert "F3" in decision.message


def test_status_keeps_false_when_visible_tests_fail() -> None:
    failing = ExecResult(
        exit_code=1,
        output="FAILED tests/visible/test_a.py::test_x - assert 1 == 2\n"
        "1 failed, 3 passed in 0.4s\n",
        duration_ms=5,
    )
    decision, _ = run(end(verify_layer=False, gate=None), FakeSandbox(default=failing))
    assert decision.kind == "note"
    assert decision.document == DOC


def test_status_keeps_false_outside_the_build_phase() -> None:
    decision, box = run(end(phase="test", last_claim={**DONE, "phase": "test"}))
    assert decision.kind == "none" and decision.document == DOC and box.commands == []


def test_status_keeps_false_once_already_set() -> None:
    decision, box = run(end(passes_already_set=True))
    assert decision.kind == "none" and decision.document == DOC and box.commands == []
