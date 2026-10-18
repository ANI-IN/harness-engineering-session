"""Small run logs for console tests: a single-arm run (`make show-N`) with a build phase and a test
phase, a multi-session build (Section 2's session stops), and an A/B, written with the real bus."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shipharness.events import EventBus


class LogWriter:
    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self.calls = 0

    def emit(self, arm: str | None, type_: str, data: dict[str, Any]) -> None:
        run_id = f"r-{arm}" if arm else None
        self.bus.publish(type_, data, run_id=run_id, arm=arm)  # type: ignore[arg-type]

    def start(self, arm: str, *, single_arm: bool, feature: str = "F1") -> None:
        layers = ["instructions"] if arm == "harness" else []
        spec = {
            "feature_id": feature,
            "layers": layers,
            "profile": "class",
            "single_arm": single_arm,
        }
        self.emit(arm, "run_start", {"spec": spec, "policy_summary": ""})

    def turn(self, arm: str, session: int, n: int, *, edit: str | None = None) -> None:
        self.emit(
            arm,
            "turn",
            {
                "session_index": session,
                "turn": n,
                "turns_left": 30 - n,
                "input_tokens": 100,
                "cached_tokens": 0,
                "cache_write_tokens": 0,
                "output_tokens": 10,
                "reasoning_tokens": 0,
                "message_excerpt": f"turn {session}.{n}",
            },
        )
        self.calls += 1
        call = f"c{self.calls}"
        name, target = ("apply_patch", edit) if edit else ("read_file", "AGENTS.md")
        self.emit(arm, "tool_call", {"call_id": call, "name": name, "target": target})
        self.emit(
            arm,
            "tool_result",
            {
                "call_id": call,
                "ok": True,
                "exit_code": 0,
                "duration_ms": 5,
                "files_changed": [edit] if edit else [],
                "output_excerpt": "ok",
            },
        )

    def claim(self, arm: str, phase: str = "build", claim: str = "done") -> None:
        self.emit(arm, "claim", {"phase": phase, "claim": claim, "summary": "", "gate_id": None})

    def stop(self, arm: str, session: int) -> None:
        self.emit(
            arm,
            "session_stop",
            {
                "session_index": session,
                "ended_by": "turn_budget",
                "end_sha": "a" * 40,
                "handoff_path": "session-handoff.md",
            },
        )

    def resume(self, arm: str, session: int) -> None:
        self.emit(
            arm,
            "session_resume",
            {"session_index": session, "start_sha": "b" * 40, "prefix_blocks": ["core", "state"]},
        )

    def end(self, arm: str) -> None:
        self.emit(
            arm,
            "run_end",
            {
                "status": "completed",
                "claim": "done",
                "cost_usd": 0.01,
                "turns_total": 5,
                "wall_s": 9,
            },
        )

    def judge(self, arm: str, *, passed: bool = True) -> None:
        self.emit(
            arm,
            "check_result",
            {
                "check": "r1_tenant",
                "passed": passed,
                "new_violations": 0 if passed else 1,
                "baseline_violations": 0,
                "total_probes": 4,
                "findings": [],
                "duration_ms": 10,
            },
        )
        values = {"r1_new_violations": 0 if passed else 1}
        self.emit(
            arm,
            "primary_verdict",
            {
                "arm": arm,
                "run_id": f"r-{arm}",
                "feature_id": "F1",
                "primary_measure": "r1_new_violations>=1",
                "passed": passed,
                "values": values,
                "elapsed_s": 3.0,
            },
        )
        self.emit(
            arm, "verdict", {"primary": values, "passed_primary": passed, "summary": "r1 ok; done"}
        )


def single_arm_run(
    runs: Path, ab_id: str = "ab-20261018-045459-aaaaaa", *, done: bool = True
) -> Path:
    """The harness arm alone: build phase (session 1), test phase (session 2), then judged."""
    log = runs / ab_id / "events.jsonl"
    with EventBus(log, ab_id=ab_id) as bus:
        w = LogWriter(bus)
        w.start("harness", single_arm=True)
        w.turn("harness", 1, 1)
        w.turn("harness", 1, 2, edit="app/api/issues.py")
        w.claim("harness", "build")
        w.turn("harness", 2, 1)
        w.turn("harness", 2, 2, edit="tests/visible/test_search.py")
        w.turn("harness", 2, 3)
        if done:
            w.claim("harness", "test")
            w.end("harness")
            w.judge("harness")
    return log


def multi_session_run(
    runs: Path,
    ab_id: str = "ab-20261018-040749-bbbbbb",
    *,
    finish: bool = True,
    extra_turns: int = 10,
) -> Path:
    """Section 2's session stops: build sessions 1 and 2 (stop and resume), then a test phase."""
    log = runs / ab_id / "events.jsonl"
    with EventBus(log, ab_id=ab_id) as bus:
        w = LogWriter(bus)
        w.start("harness", single_arm=True, feature="F2")
        w.turn("harness", 1, 1)
        w.turn("harness", 1, 2)
        w.claim("harness", "build", "not_done")
        w.stop("harness", 1)
        w.resume("harness", 2)
        for n in range(1, extra_turns + 1):
            w.turn("harness", 2, n)
        if finish:
            w.claim("harness", "build")
            w.turn("harness", 3, 1)
            w.turn("harness", 3, 2)
            w.end("harness")
            w.judge("harness")
    return log


def ab_run(runs: Path, ab_id: str = "ab-20261018-042848-cccccc") -> Path:
    """A finished A/B: both arms, each with a build and a test phase, both judged."""
    log = runs / ab_id / "events.jsonl"
    with EventBus(log, ab_id=ab_id) as bus:
        w = LogWriter(bus)
        for arm in ("bare", "harness"):
            w.start(arm, single_arm=False)
        for arm in ("bare", "harness"):
            w.turn(arm, 1, 1, edit="app/api/issues.py")
            w.claim(arm)
            w.turn(arm, 2, 1)
            w.end(arm)
            w.judge(arm, passed=arm == "harness")
    return log


def write_ab_json(run_dir: Path, **fields: Any) -> Path:
    """An ab.json with only the fields the run list reads (the rest of the real file omitted)."""
    path = run_dir / "ab.json"
    path.write_text(json.dumps(fields), encoding="utf-8")
    return path


LONG_TESTS = (
    "tests/visible/test_issue_version_history.py::test_precondition_check_order_and_openapi",
    "tests/visible/test_issue_version_history.py::test_issue_etag_and_patch_version_changes",
)
LONG_MUTANTS = ("app.services.issues-m401", "app.repositories.projects-m101")


def show_4_run(runs: Path, ab_id: str = "ab-20261018-040352-dddddd") -> Path:
    """The harness arm alone with long test and mutant names, a Filter 2 discard, and mutants."""
    log = runs / ab_id / "events.jsonl"
    with EventBus(log, ab_id=ab_id) as bus:
        w = LogWriter(bus)
        w.start("harness", single_arm=True, feature="F4")
        w.turn("harness", 1, 1, edit="app/services/issues.py")
        w.claim("harness", "build")
        w.turn("harness", 2, 1)
        for i, test_id in enumerate(LONG_TESTS):
            w.emit("harness", "test_proposed", {"test_id": test_id, "phase": "test"})
            w.emit(
                "harness",
                "test_filter_result",
                {"test_id": test_id, "filter": 1, "passed": True, "reason": ""},
            )
            reason = "failed on run 1 of 5: assert 422 == 412" if i == 0 else ""
            w.emit(
                "harness",
                "test_filter_result",
                {"test_id": test_id, "filter": 2, "passed": i != 0, "reason": reason},
            )
        for mutant, outcome in zip(LONG_MUTANTS, ("killed", "survived"), strict=True):
            w.emit(
                "harness",
                "mutant_result",
                {"mutant_id": mutant, "set": "referee", "outcome": outcome, "killed_by": None},
            )
        w.end("harness")
        w.judge("harness")
    return log
