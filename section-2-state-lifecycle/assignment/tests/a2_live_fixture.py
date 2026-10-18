"""SYNTHETIC TEST FIXTURE for the A2 live-run evidence checks. Nothing here comes from a real run:
every id contains `synthetic-fixture`, every number is made up, and the output text says so on its
first line. Tests build the files with these helpers; no model is called.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from a2_scenario import live_evidence as le

from shipharness.ab.score import ScoreRecord

NOTE = "SYNTHETIC TEST FIXTURE: not a real run, made up for the tests of the evidence checks"
AB_ID = "ab-synthetic-fixture"
RUN_IDS = {"bare": "run-synthetic-fixture-bare", "harness": "run-synthetic-fixture-harness"}
LAYER_NAME = f"a2_state.layer.{le.LAYER_CLASS}"
CHECKPOINT_SHA = "0" * 40


def score_record(arm: str, **overrides: Any) -> dict[str, Any]:
    """A ScoreRecord with made-up values (validated by the real model, then dumped)."""
    values: dict[str, Any] = dict(
        run_id=RUN_IDS[arm],
        ab_id=AB_ID,
        arm=arm,
        feature_id="F2",
        variant=le.LIVE_VARIANT,
        checkpoint="m1-s2-start",
        checkpoint_sha=CHECKPOINT_SHA,
        layers=["instructions", "state"] if arm == "harness" else [],
        status="completed",
        claim="done",
        r1_new_violations=0,
        r1_leaks=0,
        r2_new_violations=0,
        r3_new_failures=0,
        r4_duplicates=0,
        r5_audit_missing=0,
        r6_ok=True,
        r7_ok=True,
        regression_passed=1,
        regression_total=1,
        hidden_passed=1,
        hidden_total=1,
        mutants_killed=0,
        mutants_total=0,
        shipped_tests=0,
        flaky_tests=0,
        out_of_scope_files=0,
        test_phase_source_edits=0,
        continuity_failure=False,
        redone_lines_pct=0.0,
        board_ok=True,
        reviewer_verdict=None,
        reviewer_agrees=None,
        primary={"continuity_failure": False},
        passed_primary=True,
        cost_usd=0.01,
        review_cost_usd=0.0,
        turns_total=40,
        wall_s=1.0,
        trace_url=None,
        referee_trace_url=None,
        sandboxed=True,
        recorded=False,
        captured_at="synthetic-fixture",
    )
    values.update(overrides)
    return ScoreRecord(**values).model_dump(mode="json")


def _sessions(stops: int, ends: list[str]) -> list[dict[str, Any]]:
    build = [
        {
            "index": i + 1,
            "phase": "build",
            "turns": le.LIVE_BUDGETS[i],
            "ended_by": ends[i] if i < stops else "claim_done",
            "start_sha": "a" * 40,
            "end_sha": "b" * 40,
        }
        for i in range(min(stops + 1, len(le.LIVE_BUDGETS)))
    ]
    test = {**build[-1], "index": len(build) + 1, "phase": "test", "ended_by": "claim_done"}
    return [*build, test]


def write_run(
    runs_dir: Path,
    exports_dir: Path,
    *,
    stops: int = le.FORCED_STOPS,
    model: str = le.LIVE_MODEL,
    records: dict[str, dict[str, Any]] | None = None,
    harness_ends: list[str] | None = None,
    stop_step: bool = True,
) -> Path:
    """A made-up run folder (ab.json, events.jsonl) and its score records under exports/scores/.

    `harness_ends` says how the harness arm's first `stops` sessions ended (default: all by
    turn_budget). With `stop_step` false, the harness stop step leaves no trace: no state-layer
    session_stop decision, and the next session starts from the commit the session ended on."""
    ab_dir = runs_dir / AB_ID
    ab_dir.mkdir(parents=True)
    records = records or {arm: score_record(arm) for arm in RUN_IDS}
    arms = {}
    events: list[dict[str, Any]] = []

    def event(arm: str, run_id: str, kind: str, data: dict[str, Any]) -> None:
        events.append(
            {
                "v": 1,
                "ab_id": AB_ID,
                "run_id": run_id,
                "arm": arm,
                "seq": len(events) + 1,
                "ts": "synthetic-fixture",
                "type": kind,
                "data": data,
            }
        )

    for arm, run_id in RUN_IDS.items():
        harness = arm == "harness"
        ends = list(harness_ends or []) if harness else []
        ends += ["turn_budget"] * (stops - len(ends))
        record = records[arm]
        arms[arm] = {
            "spec": {
                "run_id": run_id,
                "arm": arm,
                "model": model,
                "feature_id": "F2",
                "variant": le.LIVE_VARIANT,
                "checkpoint": "m1-s2-start",
                "session_budget": list(le.LIVE_BUDGETS),
                "layers": record["layers"],
            },
            "result": {
                "run_id": run_id,
                "status": record["status"],
                "claim": record["claim"],
                "sessions": _sessions(stops, ends),
                "cost_usd": record["cost_usd"],
                "turns_total": record["turns_total"],
            },
        }
        for index in range(1, stops + 1):
            ran = harness and stop_step
            if ran:
                paths = ["session-handoff.md", "progress.md"]
                event(
                    arm,
                    run_id,
                    "harness_decision",
                    {
                        "kind": "session_stop",
                        "layer": "state",
                        "message": f"session {index} state written",
                        "paths": paths,
                        "data": {"session_index": index},
                    },
                )
            event(
                arm,
                run_id,
                "session_stop",
                {
                    "session_index": index,
                    "ended_by": ends[index - 1],
                    "end_sha": "b" * 40,
                    "handoff_path": "session-handoff.md" if harness else None,
                },
            )
            event(
                arm,
                run_id,
                "session_resume",
                {
                    "session_index": index + 1,
                    "start_sha": ("c" if ran else "b") * 40,
                    "prefix_blocks": ["core"],
                },
            )
    ab = {"note": NOTE, "checkpoint_sha": CHECKPOINT_SHA, "arms": arms}
    (ab_dir / "ab.json").write_text(json.dumps(ab, indent=2), encoding="utf-8")
    lines = [json.dumps(e) for e in events]
    (ab_dir / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    scores = exports_dir / "scores"
    scores.mkdir(parents=True, exist_ok=True)
    for record in records.values():
        (scores / f"{record['run_id']}.json").write_text(json.dumps(record), encoding="utf-8")
    return ab_dir


def output_text(
    cost_line: str = f"Cost: $0.020000 (this command: {le.LIVE_MODEL} $0.020000; session "
    "$0.020000 of $2.50)",
) -> str:
    """What the A/B command prints, made up (the first line marks it as a fixture)."""
    return "\n".join(
        [
            f"# {NOTE}",
            f"state layer: {LAYER_NAME} from my-a2",
            f"A/B {AB_ID} (F2, layers=['instructions', 'state'])",
            "  bare     completed         claim=done ...",
            "  harness  completed         claim=done ...",
            cost_line,
            "",
        ]
    )


def write_evidence(impl: Path, work: Path, **run_options: Any) -> Path:
    """Synthetic evidence in `<impl>/live/`, written by the same code the live wrapper uses."""
    evidence = impl / le.EVIDENCE_DIR
    task = le.write_task(evidence)
    ab_dir = write_run(work / "runs", work / "exports", **run_options)
    le.collect_evidence(
        impl,
        ab_dir=ab_dir,
        scores_dir=work / "exports" / "scores",
        output=output_text(),
        command=[
            f"python live/run_live.py --impl {impl.name} --forced-stops",
            "shipharness " + " ".join(le.inner_command(f"{impl.name}/live/{task.name}")),
        ],
        layer=LAYER_NAME,
    )
    return evidence
