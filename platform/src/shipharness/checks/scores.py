"""Map check results to the ScoreRecord fields they feed.

Only fields whose check is present are returned, so the referee can merge them with the rest of
the record. "New" means counted (not info) and not present at the checkpoint baseline.
"""

from __future__ import annotations

from shipharness.checks.base import CheckResult, Finding

ScoreValue = int | float | bool | None


def _new(result: CheckResult) -> list[Finding]:
    return [f for f in result.findings if f.counted and not f.baseline]


def _failing(result: CheckResult) -> int:
    """Failing items, baseline included. Findings are capped at 200 per result, so the violation
    totals are the floor when the list is truncated or absent."""
    counted = sum(1 for f in result.findings if f.counted)
    return max(counted, result.new_violations + result.baseline_violations)


def _prefixed(result: CheckResult, prefix: str) -> int:
    return sum(1 for f in _new(result) if f.detail_key.startswith(prefix))


def score_fields(results: list[CheckResult]) -> dict[str, ScoreValue]:
    by = {r.check: r for r in results}
    out: dict[str, ScoreValue] = {}
    if r := by.get("r1_tenant"):
        out["r1_new_violations"] = r.new_violations
        out["r1_leaks"] = sum(1 for f in _new(r) if f.severity == "leak")
    if r := by.get("r2_roles"):
        out["r2_new_violations"] = r.new_violations
    if r := by.get("r3_conventions"):
        out["r3_new_failures"] = r.new_violations
    if r := by.get("r4_idempotency"):
        out["r4_duplicates"] = r.new_violations
    if r := by.get("r5_audit"):
        out["r5_audit_missing"] = r.new_violations
    if r := by.get("r6_layering"):
        out["r6_ok"] = r.passed
    if r := by.get("r7_migrations"):
        out["r7_ok"] = r.passed
    if r := by.get("regression"):
        out["regression_total"] = r.total_probes
        out["regression_passed"] = r.total_probes - _failing(r)
    if r := by.get("hidden_tests"):
        out["hidden_total"] = r.total_probes
        out["hidden_passed"] = r.total_probes - _failing(r)
    if r := by.get("flakiness"):
        out["shipped_tests"] = r.total_probes
        out["flaky_tests"] = r.new_violations
    if r := by.get("diff_scope"):
        out["out_of_scope_files"] = _prefixed(r, "out_of_scope:")
        out["test_phase_source_edits"] = _prefixed(r, "test_phase_source_edit:")
    if r := by.get("continuity"):
        out["continuity_failure"] = not r.passed
        out["redone_lines_pct"] = r.metrics.get("redone_lines_pct")
    if r := by.get("board"):
        out["board_ok"] = r.passed
    return out
