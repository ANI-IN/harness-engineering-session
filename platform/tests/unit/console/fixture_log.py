"""A realistic two-arm A/B run log covering all 24 event types, plus matching exports.

Story: feature F-07 (issue labels). The bare arm reads the handbook, edits the issue repository,
tries a package install (sandbox denial), claims done, and the referee finds a tenant leak and a
duplicate. The harness arm reads the AGENTS.md map and a skill, gets one patch blocked by scope,
is stopped and resumed (redoing an edit), fails the gate once, passes it, writes tests through the
filters, and passes the referee.
"""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path
from typing import Any

from shipharness.ab.score import REFEREE_VERSION
from shipharness.events import EventBus

AB_ID = "ab-fixture"
RUN = {"bare": "run-bare", "harness": "run-harness"}
LEAK_DETAIL = "Acme user read Globex issue 21 through app/repositories/issues.py"
HOSTILE_EXCERPT = "<script>alert('pwned')</script> done"


def tiny_png(width: int = 4, height: int = 3, rgb: tuple[int, int, int] = (40, 90, 160)) -> bytes:
    """A valid RGB PNG built with the standard library."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    row = b"\x00" + bytes(rgb) * width
    raw = row * height
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _gate_items(r1: str, board: str) -> list[dict[str, str]]:
    return [
        {"name": "visible tests", "status": "pass", "detail": "41 passed"},
        {"name": "existing tests", "status": "pass", "detail": "212 passed"},
        {"name": "R1", "status": r1, "detail": "GET /issues/{id}: Globex issue visible to Acme"},
        {"name": "R2", "status": "pass", "detail": ""},
        {"name": "board", "status": board, "detail": ""},
        {"name": "clean state", "status": "skipped", "detail": "runs after the board check"},
    ]


def build_fixture_run(runs_dir: Path, *, recorded: bool = False, ab_id: str = AB_ID) -> Path:
    """Write runs_dir/<ab_id>/events.jsonl and screenshot PNGs; return the log path."""
    run_dir = Path(runs_dir) / ab_id
    log = run_dir / "events.jsonl"
    shots = run_dir / "screenshots"
    for arm in RUN:
        (shots / arm).mkdir(parents=True, exist_ok=True)
        (shots / arm / "board-0001.png").write_bytes(tiny_png(rgb=(30, 60, 120)))
    (shots / "bare" / "conflict-0001.png").write_bytes(tiny_png(rgb=(120, 30, 30)))

    with EventBus(log, ab_id=ab_id) as bus:

        def emit(arm: str | None, type_: str, data: dict[str, Any]) -> None:
            run_id = RUN[arm] if arm else None
            bus.publish(type_, data, run_id=run_id, arm=arm, recorded=recorded)  # type: ignore[arg-type]

        def tool(
            arm: str, call_id: str, name: str, target: str, ok: bool = True, **res: Any
        ) -> None:
            emit(arm, "tool_call", {"call_id": call_id, "name": name, "target": target})
            emit(
                arm,
                "tool_result",
                {
                    "call_id": call_id,
                    "ok": ok,
                    "exit_code": res.get("exit_code", 0 if ok else 1),
                    "duration_ms": res.get("duration_ms", 40),
                    "files_changed": res.get("files_changed", []),
                    "output_excerpt": res.get("output", "ok"),
                },
            )

        def turn(arm: str, session: int, n: int, message: str) -> None:
            emit(
                arm,
                "turn",
                {
                    "session_index": session,
                    "turn": n,
                    "turns_left": 30 - n,
                    "input_tokens": 9000 + 400 * n,
                    "cached_tokens": 8000,
                    "cache_write_tokens": 0,
                    "output_tokens": 350,
                    "reasoning_tokens": 120,
                    "message_excerpt": message,
                },
            )

        for arm in RUN:
            layers = [] if arm == "bare" else ["instructions", "state", "scope", "verify"]
            emit(
                arm,
                "run_start",
                {
                    "spec": {
                        "feature_id": "F-07",
                        "ticket": "Add labels to issues",
                        "layers": layers,
                    },
                    "policy_summary": "network none, 1 CPU, 1024 MB, 256 pids, read-only root",
                },
            )
            emit(
                arm,
                "sandbox_start",
                {
                    "container_id": "a1b2c3d4e5f6" if arm == "bare" else "f6e5d4c3b2a1",
                    "image": "shipharness-agent:1",
                    "network": "none",
                    "cpus": 1.0,
                    "memory_mb": 1024,
                    "pids_limit": 256,
                    "user": "1000:1000",
                    "read_only_root": True,
                    "unsandboxed": False,
                },
            )
        emit(
            "harness",
            "harness_decision",
            {
                "kind": "note",
                "layer": "instructions",
                "message": "AGENTS.md map and skills catalogue in the context prefix",
            },
        )

        # Session 1, both arms.
        turn("bare", 1, 1, "Reading the handbook to find the issue endpoints.")
        tool("bare", "b1", "read_file", "docs/HANDBOOK.md")
        turn("harness", 1, 1, "Reading the map first.")
        tool("harness", "h1", "read_file", "AGENTS.md")
        emit(
            "harness",
            "harness_decision",
            {
                "kind": "note",
                "layer": "instructions",
                "message": "skill loaded: add-endpoint (tier 2)",
                "paths": [".agents/skills/add-endpoint/SKILL.md"],
                "data": {"skill": "add-endpoint", "tier": 2},
            },
        )
        tool("harness", "h2", "read_file", ".agents/skills/add-endpoint/SKILL.md")
        tool("harness", "h3", "read_file", "docs/SECURITY.md")

        turn("bare", 1, 2, "Adding the label column and endpoint.")
        tool(
            "bare",
            "b2",
            "apply_patch",
            "app/repositories/issues.py",
            files_changed=["app/repositories/issues.py", "app/api/issues.py"],
            output="applied: app/repositories/issues.py, app/api/issues.py",
        )
        turn("bare", 1, 3, "Installing a helper library.")
        tool("bare", "b3", "run", "pip install requests", ok=False, exit_code=126)
        emit(
            "bare",
            "sandbox_denied",
            {
                "command": "pip install requests",
                "reason_code": "network",
                "detail": "the sandbox has no network",
            },
        )
        emit(
            "bare",
            "sandbox_usage",
            {
                "cpu_pct": 37.5,
                "mem_mb": 212.0,
                "mem_limit_mb": 1024.0,
                "pids": 14,
                "time_left_s": 183,
            },
        )
        turn("bare", 1, 4, "Seeding demo labels.")
        tool("bare", "b4", "apply_patch", "app/seed.py", files_changed=["app/seed.py"])
        turn("bare", 1, 5, HOSTILE_EXCERPT)
        tool("bare", "b5", "run_visible_tests", "tests/visible", output="passed=41 failed=0")
        emit(
            "bare",
            "claim",
            {"phase": "build", "claim": "done", "summary": "Labels added.", "gate_id": None},
        )

        turn("harness", 1, 2, "Adding the label repository function.")
        tool(
            "harness",
            "h4",
            "apply_patch",
            "app/repositories/issues.py",
            files_changed=["app/repositories/issues.py"],
        )
        turn("harness", 1, 3, "Editing the migration file.")
        emit(
            "harness",
            "harness_decision",
            {
                "kind": "block",
                "layer": "scope",
                "message": "migrations/ is outside the allowed paths for phase build",
                "paths": ["migrations/versions/0001_initial.py"],
            },
        )
        emit(
            "harness",
            "blocked",
            {
                "phase": "build",
                "paths": ["migrations/versions/0001_initial.py"],
                "action": "reject_patch",
                "reason": "outside allowed paths for phase build",
            },
        )
        tool(
            "harness",
            "h5",
            "apply_patch",
            "migrations/versions/0001_initial.py",
            ok=False,
            output="rejected: path blocked by scope",
        )
        emit(
            "harness",
            "sandbox_usage",
            {
                "cpu_pct": 22.0,
                "mem_mb": 188.5,
                "mem_limit_mb": 1024.0,
                "pids": 11,
                "time_left_s": 171,
            },
        )
        emit(
            "harness",
            "session_stop",
            {
                "session_index": 1,
                "ended_by": "session_turn_limit",
                "end_sha": "abc1234",
                "handoff_path": "session-handoff.md",
            },
        )
        emit(
            "harness",
            "harness_decision",
            {"kind": "session_stop", "layer": "state", "message": "handoff written"},
        )
        emit(
            "harness",
            "session_resume",
            {
                "session_index": 2,
                "start_sha": "abc1234",
                "prefix_blocks": ["map", "getting up to speed", "feature list"],
            },
        )
        turn("harness", 2, 1, "Getting up to speed from progress.md.")
        tool("harness", "h6", "read_file", "progress.md")
        turn("harness", 2, 2, "Finishing the label filter.")
        tool(
            "harness",
            "h7",
            "apply_patch",
            "app/repositories/issues.py",
            files_changed=["app/repositories/issues.py", "app/api/issues.py"],
        )
        tool("harness", "h8", "run_visible_tests", "tests/visible", output="passed=41 failed=0")
        emit(
            "harness",
            "claim",
            {"phase": "build", "claim": "done", "summary": "Labels added.", "gate_id": "g1"},
        )
        emit(
            "harness",
            "check_progress",
            {"check": "R1", "done": 37, "total": 112, "label": "House rule 1 probes 37/112"},
        )
        emit(
            "harness",
            "gate_result",
            {
                "gate_id": "g1",
                "items": _gate_items("fail", "pending"),
                "passed": False,
                "feedback": "R1 GET /issues/{id}",
            },
        )
        emit(
            "harness",
            "harness_decision",
            {"kind": "gate_fail", "layer": "verify", "message": "R1 failed: 1 leak"},
        )
        turn("harness", 2, 3, "Scoping the label query by org.")
        tool(
            "harness",
            "h9",
            "apply_patch",
            "app/repositories/issues.py",
            files_changed=["app/repositories/issues.py"],
        )
        emit(
            "harness",
            "gate_result",
            {
                "gate_id": "g2",
                "items": _gate_items("pass", "pass"),
                "passed": True,
                "feedback": "",
            },
        )
        emit("harness", "harness_decision", {"kind": "gate_pass", "layer": "verify", "message": ""})
        emit(
            "harness",
            "claim",
            {"phase": "build", "claim": "done", "summary": "Labels added.", "gate_id": "g2"},
        )

        # Test phase (harness arm).
        for test_id, results in (
            ("tests/test_labels.py::test_label_scoped_to_org", [True] * 5),
            ("tests/test_labels.py::test_label_with_mocks", [True, True, True, False]),
        ):
            emit("harness", "test_proposed", {"test_id": test_id, "phase": "test"})
            for index, passed in enumerate(results, start=1):
                emit(
                    "harness",
                    "test_filter_result",
                    {
                        "test_id": test_id,
                        "filter": index,
                        "passed": passed,
                        "reason": "" if passed else "mocks the unit under test",
                    },
                )
        for mutant, outcome in (("m-issues-01", "killed"), ("m-issues-02", "survived")):
            emit(
                "harness",
                "mutant_result",
                {
                    "mutant_id": mutant,
                    "set": "filter",
                    "outcome": outcome,
                    "killed_by": "tests/test_labels.py::test_label_scoped_to_org"
                    if outcome == "killed"
                    else None,
                },
            )
        emit(
            "harness",
            "claim",
            {"phase": "test", "claim": "done", "summary": "One test kept.", "gate_id": None},
        )

        # Referee, both arms.
        for arm in RUN:
            emit(
                arm,
                "check_progress",
                {"check": "R1", "done": 112, "total": 112, "label": "House rule 1 probes 112/112"},
            )
        emit(
            "bare",
            "check_result",
            {
                "check": "r1_tenant",
                "passed": False,
                "new_violations": 3,
                "baseline_violations": 1,
                "total_probes": 112,
                "findings": [
                    {
                        "rule": "R1",
                        "severity": "leak",
                        "endpoint": "GET /issues/{id}",
                        "detail": LEAK_DETAIL,
                        "baseline": False,
                    }
                ],
                "duration_ms": 5400,
                "seed": 7,
            },
        )
        emit(
            "bare",
            "check_result",
            {
                "check": "diff_scope",
                "passed": False,
                "new_violations": 1,
                "baseline_violations": 0,
                "total_probes": 3,
                "findings": [
                    {
                        "rule": "scope",
                        "severity": "violation",
                        "endpoint": None,
                        "detail": "out of scope: app/seed.py",
                        "baseline": False,
                    }
                ],
                "duration_ms": 30,
            },
        )
        for arm, check, passed in (
            ("bare", "r4_idempotency", False),
            ("bare", "regression", True),
            ("harness", "r1_tenant", True),
            ("harness", "r4_idempotency", True),
            ("harness", "regression", True),
            ("harness", "hidden_tests", True),
        ):
            emit(
                arm,
                "check_result",
                {
                    "check": check,
                    "passed": passed,
                    "new_violations": 0 if passed else 1,
                    "baseline_violations": 1 if check == "r1_tenant" else 0,
                    "total_probes": 20,
                    "findings": [],
                    "duration_ms": 900,
                },
            )
        for arm, outcome in (("bare", "survived"), ("harness", "killed")):
            emit(
                arm,
                "mutant_result",
                {
                    "mutant_id": "m-repo-07",
                    "set": "referee",
                    "outcome": outcome,
                    "killed_by": "tests/test_labels.py::test_label_scoped_to_org"
                    if outcome == "killed"
                    else None,
                },
            )
        for arm in RUN:
            emit(
                arm,
                "reviewer_output",
                {
                    "findings": [],
                    "tenant_isolation_risk": "none",
                    "verdict": "accept",
                    "summary": "Looks fine.",
                },
            )
        for arm, passed, values in (
            ("bare", False, {"r1_new_violations": 3, "r4_duplicates": 1}),
            ("harness", True, {"r1_new_violations": 0, "r4_duplicates": 0}),
        ):
            emit(
                arm,
                "primary_verdict",
                {
                    "arm": arm,
                    "run_id": RUN[arm],
                    "feature_id": "F-07",
                    "primary_measure": "r1_new_violations>=1 or r4_duplicates>=1",
                    "passed": passed,
                    "values": values,
                    "elapsed_s": 41.0,
                },
            )
        emit(
            "bare",
            "verdict",
            {
                "primary": {"r1_new_violations": 3, "r4_duplicates": 1},
                "passed_primary": False,
                "summary": "R1: 3 new leaks; R4: 1 duplicate",
            },
        )
        emit(
            "harness",
            "verdict",
            {
                "primary": {"r1_new_violations": 0, "r4_duplicates": 0},
                "passed_primary": True,
                "summary": "No new violations",
            },
        )
        for arm, usd in (("bare", 0.081), ("harness", 0.117)):
            emit(
                arm,
                "cost",
                {
                    "scope": "run",
                    "model": "gpt-6-luna",
                    "call_usd": 0.004,
                    "run_usd": usd,
                    "session_usd": 0.62,
                    "limit_usd": 0.20,
                },
            )
        emit(
            "bare",
            "screenshot",
            {
                "path": "screenshots/bare/board-0001.png",
                "view": "board",
                "as_user": "admin@acme.test",
                "overlays": [
                    {"issue_id": 21, "mark": "other_org"},
                    {"issue_id": 7, "mark": "duplicate"},
                ],
            },
        )
        emit(
            "bare",
            "screenshot",
            {
                "path": "screenshots/bare/conflict-0001.png",
                "view": "conflict",
                "as_user": "admin@acme.test",
                "overlays": [{"issue_id": 1, "mark": "lost_update"}],
            },
        )
        emit(
            "harness",
            "screenshot",
            {
                "path": "screenshots/harness/board-0001.png",
                "view": "board",
                "as_user": "admin@acme.test",
                "overlays": [],
            },
        )
        for arm in RUN:
            emit(
                arm,
                "trace_link",
                {"url": f"https://smith.langchain.com/o/x/r/{arm}-agent", "kind": "agent"},
            )
        emit(
            "harness",
            "trace_link",
            {"url": "https://smith.langchain.com/o/x/r/harness-referee", "kind": "referee"},
        )
        emit(
            None,
            "trace_link",
            {"url": "https://smith.langchain.com/o/x/compare/ab-fixture", "kind": "comparison"},
        )
        for arm, status, usd, turns in (
            ("bare", "completed", 0.081, 5),
            ("harness", "completed", 0.117, 8),
        ):
            emit(
                arm,
                "run_end",
                {
                    "status": status,
                    "claim": "done",
                    "cost_usd": usd,
                    "turns_total": turns,
                    "wall_s": 141.0,
                },
            )
    return log


def score(
    n: int,
    *,
    arm: str,
    variant: str,
    passed: bool,
    layers: list[str],
    agrees: bool = True,
    **extra: Any,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "run_id": f"{variant}-{arm}-{n:02d}",
        "ab_id": f"ab-{variant}-{n:02d}",
        "arm": arm,
        "feature_id": {"s1": "F1", "s3": "F3"}.get(variant, f"F-{n:02d}"),
        "variant": variant,
        "checkpoint": f"m1-{variant}-start",
        "layers": layers,
        "status": "completed",
        "claim": "done",
        "passed_primary": passed,
        "reviewer_verdict": "accept",
        "reviewer_agrees": agrees,
        "cost_usd": 0.10,
        "review_cost_usd": 0.01,
        "turns_total": 12,
        "wall_s": 120.0,
        "sandboxed": True,
        "recorded": False,
        "captured_at": "2026-10-16T10:00:00Z",
        "referee_version": REFEREE_VERSION,
    }
    record.update(extra)
    return record


def build_fixture_exports(exports_dir: Path) -> Path:
    """S1: harness 9/10 vs bare 3/10. S3: harness 8/10 vs bare 2/10. Two experiments."""
    scores = Path(exports_dir) / "scores"
    scores.mkdir(parents=True, exist_ok=True)
    plan = (
        ("s1", "bare", [], 3),
        ("s1", "harness", ["instructions"], 9),
        ("s3", "bare", [], 2),
        ("s3", "harness", ["instructions", "state", "scope"], 8),
    )
    for variant, arm, layers, passes in plan:
        for n in range(10):
            record = score(
                n,
                arm=arm,
                variant=variant,
                passed=n < passes,
                layers=layers,
                agrees=n != 0,
            )
            (scores / f"{record['run_id']}.json").write_text(json.dumps(record), encoding="utf-8")
    (scores / "broken.json").write_text("{not json", encoding="utf-8")
    old = score(99, arm="bare", variant="s1", passed=False, layers=[])
    del old["referee_version"]  # scored before the current referee version: not shown
    (scores / "s1-bare-99.json").write_text(json.dumps(old), encoding="utf-8")
    experiments = Path(exports_dir) / "experiments"
    experiments.mkdir(parents=True, exist_ok=True)
    (experiments / "teamtrack-ablation.json").write_text(
        json.dumps(
            {
                "name": "teamtrack-ablation",
                "url": None,
                "comparison_url": None,
                "dataset": "teamtrack-features-v1",
                "split": "s3",
                "arm": "harness",
                "k": 1,
                "metadata": {"batch": "ablation-1", "layers": ["instructions", "state"]},
                "rows": [f"s3-harness-{n:02d}" for n in range(4)],
                "stats": {},
            }
        ),
        encoding="utf-8",
    )
    for variant in ("s1", "s3"):
        (experiments / f"teamtrack-{variant}.json").write_text(
            json.dumps(
                {
                    "name": f"teamtrack-{variant}",
                    "url": f"https://smith.langchain.com/o/x/datasets/d/compare?e={variant}",
                    "comparison_url": f"https://smith.langchain.com/o/x/compare/{variant}",
                    "dataset": "teamtrack-features-v1",
                    "split": variant,
                    "arm": "harness",
                    "k": 10,
                    "metadata": {},
                    "rows": [],
                    "stats": {},
                }
            ),
            encoding="utf-8",
        )
    return Path(exports_dir)
