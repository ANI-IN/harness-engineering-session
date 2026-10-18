"""ScoreRecord fixtures (no tests here)."""

from __future__ import annotations

from typing import Any

from shipharness.ab.score import ScoreRecord


def record(**overrides: Any) -> ScoreRecord:
    base: dict[str, Any] = dict(
        run_id="r-20261016-100000-aaaaaa",
        ab_id="ab-20261016-100000-bbbbbb",
        arm="bare",
        feature_id="F1",
        variant="canonical",
        checkpoint="m1-s1-start",
        layers=[],
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
        regression_passed=20,
        regression_total=20,
        hidden_passed=4,
        hidden_total=4,
        mutants_killed=2,
        mutants_total=4,
        shipped_tests=3,
        flaky_tests=0,
        out_of_scope_files=0,
        test_phase_source_edits=0,
        continuity_failure=None,
        redone_lines_pct=None,
        board_ok=True,
        reviewer_verdict=None,
        reviewer_agrees=None,
        primary={"r1_new_violations": 0},
        passed_primary=True,
        cost_usd=0.05,
        review_cost_usd=0.0,
        turns_total=20,
        wall_s=100.0,
        trace_url=None,
        referee_trace_url=None,
        sandboxed=True,
        recorded=False,
        captured_at="2026-10-16T10:00:00.000Z",
    )
    base.update(overrides)
    return ScoreRecord(**base)
