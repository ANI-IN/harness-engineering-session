"""The five test filters, cheapest first. Every discard carries a reason.

1. Imports and runs: pytest collects the test without errors (TestGen-LLM "builds").
2. Passes 5 consecutive runs (TestGen-LLM: "every one of five executions").
3. Adds line coverage over the existing suite, or kills a filter-set mutant that no existing test
   kills (TestGen-LLM coverage; ACH hardening).
4. Real assertions and no mocking of the unit under test (course filter).
5. No source file changed during the test phase (course filter).
"""

from __future__ import annotations

from shipharness.datasets.names import FILTER_NAMES
from shipharness.filters.ast_checks import check_test
from shipharness.filters.coverage import measure_coverage
from shipharness.filters.models import CandidateTest, FilterContext, FilterResult
from shipharness.filters.mutants import run_mutant
from shipharness.filters.pytest_cmd import (
    UnsafeTestId,
    check_test_id,
    collected,
    counts,
    error_excerpt,
    pytest_command,
)
from shipharness.filters.source import changed_sources
from shipharness.runner.paths import PathOutsideWorkspace, resolve_in_workspace

MAX_MODULE_BYTES = 2_000_000


def _result(number: int, cand: CandidateTest, passed: bool, reason: str) -> FilterResult:
    return FilterResult(test_id=cand.test_id, filter=number, passed=passed, reason=reason)


def _ranges(lines: list[int]) -> str:
    """[14, 16, 17] -> "14,16-17"."""
    parts: list[str] = []
    start = prev = lines[0]
    for n in lines[1:] + [None]:  # type: ignore[list-item]
        if n is not None and n == prev + 1:
            prev = n
            continue
        parts.append(str(start) if start == prev else f"{start}-{prev}")
        if n is not None:
            start = prev = n
    return ",".join(parts)


def surviving_mutants(ctx: FilterContext) -> frozenset[str]:
    """Filter-set mutants that the existing tests do not kill (computed if not given)."""
    if ctx.surviving_mutant_ids is not None:
        return ctx.surviving_mutant_ids
    return frozenset(
        m.id
        for m in ctx.filter_mutants
        if run_mutant(
            m,
            ctx.existing_tests,
            ctx.workspace,
            ctx.sandbox,
            ctx.timeout_s,
            python=ctx.python,
            doctest_modules=ctx.doctest_modules,
        )
        == "survived"
    )


class ImportsAndRuns:
    number = 1
    name = FILTER_NAMES[1]  # Builds and collects

    def evaluate(self, cand: CandidateTest, ctx: FilterContext) -> FilterResult:
        try:
            check_test_id(cand.test_id)
            command = pytest_command(ctx.python, [cand.test_id], extra="--collect-only")
        except UnsafeTestId as exc:
            return _result(1, cand, False, str(exc))
        run = ctx.sandbox.exec(command, ctx.timeout_s)
        if run.timed_out:
            return _result(1, cand, False, f"collection timed out after {ctx.timeout_s} s")
        found = collected(run.output)
        if run.exit_code == 0 and found >= 1:
            return _result(1, cand, True, f"collected {found} test{'s' if found > 1 else ''}")
        if run.exit_code in (4, 5) or (run.exit_code == 0 and found == 0):
            detail = error_excerpt(run.output)
            return _result(
                1, cand, False, f"test not found by pytest (no test collected): {detail}"
            )
        return _result(1, cand, False, f"collection failed: {error_excerpt(run.output)}")


class PassesFiveRuns:
    number = 2
    name = FILTER_NAMES[2]  # Passes five runs

    def evaluate(self, cand: CandidateTest, ctx: FilterContext) -> FilterResult:
        try:
            command = pytest_command(ctx.python, [cand.test_id])
        except UnsafeTestId as exc:
            return _result(2, cand, False, str(exc))
        total = ctx.runs
        for index in range(1, total + 1):
            run = ctx.sandbox.exec(command, ctx.timeout_s)
            problem = ""
            if run.timed_out:
                problem = f"timed out after {ctx.timeout_s} s"
            else:
                totals = counts(run.output)
                if run.exit_code == 0 and totals["passed"] == 0 and totals["skipped"]:
                    problem = "the test was skipped, not passed"
                elif run.exit_code != 0 or totals["passed"] == 0:
                    problem = error_excerpt(run.output)
            if problem:
                if index == 1:
                    return _result(2, cand, False, f"failed on run 1 of {total}: {problem}")
                return _result(
                    2, cand, False, f"flaky: passed {index - 1} of {total} runs, then {problem}"
                )
        return _result(2, cand, True, f"passed {total} of {total} runs")


class AddsCoverageOrKillsMutant:
    number = 3
    name = FILTER_NAMES[3]  # Adds coverage or catches a mutant

    def evaluate(self, cand: CandidateTest, ctx: FilterContext) -> FilterResult:
        note = ""
        run = measure_coverage(
            ctx.workspace, ctx.sandbox, [cand.test_id], python=ctx.python, timeout_s=ctx.timeout_s
        )
        if run.ok:
            added = run.coverage.new_lines(ctx.baseline_coverage)
            if added:
                count = sum(len(lines) for lines in added.values())
                where = "; ".join(f"{path}:{_ranges(lines)}" for path, lines in added.items())
                return _result(3, cand, True, f"adds {count} covered lines: {where}"[:500])
        else:
            note = f" (coverage not measured: {run.detail})"
        survivors = surviving_mutants(ctx)
        checked = [m for m in ctx.filter_mutants if m.id in survivors]
        for m in checked:
            outcome = run_mutant(
                m, [cand.test_id], ctx.workspace, ctx.sandbox, ctx.timeout_s, python=ctx.python
            )
            if outcome == "killed":
                return _result(
                    3, cand, True, f"kills filter-set mutant {m.id} that no existing test kills"
                )
        return _result(
            3,
            cand,
            False,
            "adds no line coverage over the existing suite and kills no filter-set mutant "
            f"that the existing tests miss ({len(checked)} checked){note}",
        )


def _module_source(ctx: FilterContext) -> str | None:
    if not ctx.target_module:
        return None
    rel = ctx.target_module.replace(".", "/")
    for candidate in (f"{rel}.py", f"{rel}/__init__.py", f"src/{rel}.py", f"src/{rel}/__init__.py"):
        try:
            path = resolve_in_workspace(ctx.workspace, candidate)
        except PathOutsideWorkspace:
            continue
        if path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_MODULE_BYTES:
            return path.read_text(encoding="utf-8", errors="replace")
    return None


class RealAssertionsNoMocking:
    number = 4
    name = FILTER_NAMES[4]  # Real assertions

    def evaluate(self, cand: CandidateTest, ctx: FilterContext) -> FilterResult:
        passed, reason = check_test(
            cand.source, cand.test_id, ctx.target_module, _module_source(ctx)
        )
        return _result(4, cand, passed, reason)


class NoSourceChange:
    number = 5
    name = FILTER_NAMES[5]  # No source changes

    def evaluate(self, cand: CandidateTest, ctx: FilterContext) -> FilterResult:
        changes = changed_sources(ctx.source_shas_at_phase_start, ctx.workspace)
        if not changes:
            return _result(5, cand, True, "no source file changed during the test phase")
        listed = ", ".join(f"{path} ({kind})" for path, kind in changes[:5])
        more = f", and {len(changes) - 5} more" if len(changes) > 5 else ""
        return _result(
            5, cand, False, f"source files changed during the test phase: {listed}{more}"
        )


DEFAULT_FILTERS = (
    ImportsAndRuns(),
    PassesFiveRuns(),
    AddsCoverageOrKillsMutant(),
    RealAssertionsNoMocking(),
    NoSourceChange(),
)
