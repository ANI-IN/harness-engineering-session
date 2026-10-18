from __future__ import annotations

import time

from shipharness.checks import CheckContext, CheckResult, Finding, mark_baseline
from shipharness.checks.base import make_result


def finding(
    detail_key: str, endpoint: str | None = None, severity: str = "violation", rule: str = "R3"
) -> Finding:
    return Finding(
        rule=rule,
        severity=severity,  # type: ignore[arg-type]
        endpoint=endpoint,
        detail=f"detail for {detail_key}",
        detail_key=detail_key,
    )


def result(*findings: Finding) -> CheckResult:
    return make_result("r3_conventions", list(findings), total_probes=5, started=time.monotonic())


def test_baseline_key_distinguishes_failures_on_the_same_endpoint() -> None:
    # Review M5: two different failures on one endpoint must not collapse into one baseline key.
    baseline = result(finding("bare_array", "GET /v1/issues"))
    current = result(
        finding("bare_array", "GET /v1/issues"), finding("error_envelope", "GET /v1/issues")
    )
    marked = mark_baseline(current, baseline)
    assert marked.new_violations == 1
    assert marked.findings[0].detail_key == "error_envelope"
    assert marked.findings[0].baseline is False


def test_baseline_key_distinguishes_findings_without_an_endpoint() -> None:
    baseline = result(finding("test:tests/a.py::test_one", rule="regression"))
    current = result(
        finding("test:tests/a.py::test_one", rule="regression"),
        finding("test:tests/a.py::test_two", rule="regression"),
    )
    assert mark_baseline(current, baseline).new_violations == 1


def test_info_findings_are_reported_but_never_counted() -> None:
    made = result(finding("exempt", "POST /x", severity="info"))
    assert made.passed is True
    assert made.new_violations == 0
    marked = mark_baseline(made, None)
    assert marked.passed is True
    assert marked.new_violations == 0
    assert len(marked.findings) == 1


def test_make_result_sorts_counted_findings_first_and_caps_at_200() -> None:
    findings = [finding(f"i{n}", severity="info") for n in range(150)]
    findings += [finding(f"v{n}") for n in range(100)]
    made = result(*findings)
    assert len(made.findings) == 200
    assert made.findings[0].severity == "violation"
    assert made.new_violations == 100
    assert made.passed is False


def test_errors_count_as_failures() -> None:
    made = result(finding("crash", severity="error"))
    assert made.passed is False
    assert made.new_violations == 1


def test_check_context_carries_params_and_exemptions() -> None:
    ctx = CheckContext(
        checkpoint="m1-base",
        feature_id="F1",
        params={"hidden_tests": ["tests/hidden/test_f1.py::test_a"]},
        exemptions={"R4": ["POST /projects/{project_id}/issues"]},
    )
    assert ctx.params["hidden_tests"] == ["tests/hidden/test_f1.py::test_a"]
    assert ctx.is_exempt("R4", "POST /projects/{project_id}/issues")
    assert not ctx.is_exempt("R4", "POST /projects")
    assert not ctx.is_exempt("R1", "POST /projects/{project_id}/issues")
