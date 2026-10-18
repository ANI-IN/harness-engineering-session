"""Checks that run tests: existing tests keep passing, hidden tests, flakiness of shipped tests.

Params (runner --params):
- `regression_targets`: pytest targets for the checkpoint's visible suite (default
  ["tests/visible"]). The referee sends the checkpoint's node ids (`file::test`, which runs every
  parameter), so tests the arm added never run here; the gate sends the checkpoint's files. When a
  node id no longer exists, the ids that remain still run.
- `regression_expected`: node ids that existed at the checkpoint; one the run no longer reports
  (removed or renamed by the arm) counts as failed and stays in the total. Parametrized ids match
  by their base name.
- `hidden_tests`: pytest node ids relative to the build directory (mount hidden tests inside the
  build tree, for example at tests/hidden/). A requested id that is not collected counts as failed.
- `shipped_tests`: node ids or files the arm added; `flaky_runs`: repetitions (default 5).
"""

from __future__ import annotations

import time
from pathlib import Path

from shipharness.checks._pytest import (
    PytestRun,
    collect_ids,
    no_tests_finding,
    outcome_finding,
    run_pytest,
)
from shipharness.checks.base import CheckContext, CheckResult, Finding, make_result, register_check

# TestGen-LLM deems a test flaky unless it passes on "every one of five executions" (B11, F-b-19).
DEFAULT_FLAKY_RUNS = 5


@register_check
class RegressionCheck:
    """Existing tests keep passing (internal key `regression`)."""

    name = "regression"
    rule = "regression"

    def run(self, build_dir: Path, ctx: CheckContext) -> CheckResult:
        started = time.monotonic()
        targets = list(ctx.params.get("regression_targets") or ["tests/visible"])
        ctx.progress(0, 1, "existing tests")
        run = run_pytest(build_dir, targets)
        if run.returncode == 4 and any("::" in t for t in targets):
            # A node id the arm removed or renamed stops the whole run: run the ones that remain.
            present = _collectable(build_dir, targets)
            run = run_pytest(build_dir, present) if present else PytestRun(run.returncode)
        ctx.progress(1, 1, "existing tests")
        findings = [outcome_finding("regression", n, run.outcomes[n]) for n in run.failed]
        reported = {node.split("[", 1)[0] for node in run.outcomes}
        expected = ctx.params.get("regression_expected") or []
        missing = [node for node in expected if node not in reported]
        for node in missing:
            findings.append(
                outcome_finding("regression", node, "missing: existing test removed or renamed")
            )
        if not run.outcomes and not missing:
            findings.append(no_tests_finding("regression", run))
        # A missing existing test is still one of the checkpoint's tests: it counts in the total.
        total = len(run.outcomes) + len(missing)
        return make_result(self.name, findings, total_probes=total, started=started)


def _collectable(build_dir: Path, targets: list[str]) -> list[str]:
    """Targets pytest can still collect: node ids matched by base name (parameters stripped),
    plain paths when they exist."""
    files = sorted({t.split("::", 1)[0] for t in targets})
    files = [f for f in files if (build_dir / f).is_file()]
    listed = {node.split("[", 1)[0] for node in collect_ids(build_dir, files)} if files else set()
    return [t for t in targets if (t in listed if "::" in t else (build_dir / t).exists())]


@register_check
class HiddenTestsCheck:
    name = "hidden_tests"
    rule = "hidden"

    def run(self, build_dir: Path, ctx: CheckContext) -> CheckResult:
        started = time.monotonic()
        ids = list(ctx.params.get("hidden_tests") or [])
        if not ids:
            missing = Finding(
                rule="hidden",
                severity="error",
                detail_key="no_ids",
                detail="no hidden test ids given (params.hidden_tests)",
            )
            return make_result(self.name, [missing], total_probes=0, started=started)
        ctx.progress(0, len(ids), "hidden tests")
        run = run_pytest(build_dir, ids)
        outcomes = dict(run.outcomes)
        if any(i not in outcomes for i in ids) and run.returncode == 4:
            # An unknown node id stops the whole run: collect, then run only the ids that exist.
            files = sorted({i.split("::", 1)[0] for i in ids})
            listed = set(collect_ids(build_dir, files))
            present = [i for i in ids if i in listed]
            if present:
                outcomes.update(run_pytest(build_dir, present).outcomes)
        ctx.progress(len(ids), len(ids), "hidden tests")
        findings: list[Finding] = []
        for node in ids:
            outcome = outcomes.get(node, "not collected")
            if outcome != "passed":
                findings.append(outcome_finding("hidden", node, outcome))
        return make_result(self.name, findings, total_probes=len(ids), started=started)


@register_check
class FlakinessCheck:
    """Shipped tests re-run N times; a test that both passes and fails is flaky."""

    name = "flakiness"
    rule = "flaky"

    def run(self, build_dir: Path, ctx: CheckContext) -> CheckResult:
        started = time.monotonic()
        targets = list(ctx.params.get("shipped_tests") or [])
        runs = int(ctx.params.get("flaky_runs", DEFAULT_FLAKY_RUNS))
        if not targets:
            return make_result(self.name, [], total_probes=0, started=started)
        seen: dict[str, set[str]] = {}
        for n in range(1, runs + 1):
            for node, outcome in run_pytest(build_dir, targets).outcomes.items():
                if outcome != "skipped":
                    seen.setdefault(node, set()).add("passed" if outcome == "passed" else "failed")
            ctx.progress(n, runs, f"flakiness run {n}/{runs}")
        findings: list[Finding] = []
        for node, outcomes in sorted(seen.items()):
            if outcomes == {"passed", "failed"}:
                findings.append(outcome_finding("flaky", node, f"passed and failed in {runs} runs"))
            elif outcomes == {"failed"}:
                findings.append(
                    outcome_finding("flaky", node, f"failed in all {runs} runs", "info")
                )
        return make_result(self.name, findings, total_probes=len(seen), started=started)
