from __future__ import annotations

from shipharness.checks import Finding
from shipharness.checks.base import CheckResult, make_result
from shipharness.checks.scores import score_fields


def result(check: str, *findings: Finding, total: int = 10) -> CheckResult:
    return make_result(check, list(findings), total_probes=total, started=0.0)


def f(rule: str, key: str, severity: str = "violation", baseline: bool = False) -> Finding:
    return Finding(
        rule=rule,
        severity=severity,
        detail_key=key,
        detail=key,
        baseline=baseline,  # type: ignore[arg-type]
    )


def test_score_fields_maps_each_check() -> None:
    fields = score_fields(
        [
            result("r1_tenant", f("R1", "no_path", "leak"), f("R1", "foreign_path")),
            result("regression", f("regression", "test:a"), total=120),
            result("hidden_tests", f("hidden", "test:h"), total=4),
            result("flakiness", f("flaky", "test:x"), f("flaky", "test:y", "info"), total=6),
            result(
                "diff_scope",
                f("scope", "out_of_scope:app/api/middleware.py"),
                f("scope", "test_phase_source_edit:app/services/x.py"),
            ),
            result("board"),
        ]
    )
    assert fields == {
        "r1_new_violations": 2,
        "r1_leaks": 1,
        "regression_total": 120,
        "regression_passed": 119,
        "hidden_total": 4,
        "hidden_passed": 3,
        "shipped_tests": 6,
        "flaky_tests": 1,
        "out_of_scope_files": 1,
        "test_phase_source_edits": 1,
        "board_ok": True,
    }


def test_baseline_findings_do_not_count_as_new_leaks() -> None:
    r1 = result("r1_tenant", f("R1", "no_path", "leak"))
    r1 = r1.model_copy(
        update={
            "findings": [r1.findings[0].model_copy(update={"baseline": True})],
            "new_violations": 0,
        }
    )
    assert score_fields([r1])["r1_leaks"] == 0


def test_failing_counts_use_violation_totals_when_findings_are_capped_or_absent() -> None:
    from shipharness.checks.base import CheckResult
    from shipharness.checks.scores import score_fields

    no_findings = CheckResult(
        check="hidden_tests",
        passed=False,
        new_violations=1,
        baseline_violations=0,
        total_probes=4,
        findings=[],
        duration_ms=1,
    )
    capped = CheckResult(
        check="regression",
        passed=False,
        new_violations=250,
        baseline_violations=10,
        total_probes=400,
        findings=[],
        duration_ms=1,
    )
    fields = score_fields([no_findings, capped])
    assert (fields["hidden_passed"], fields["hidden_total"]) == (3, 4)
    assert (fields["regression_passed"], fields["regression_total"]) == (140, 400)
