"""The filter pipeline: every proposed test goes through the five filters in order, cheapest first,
and stops at the first one it fails. Every test gets a recorded result; every discard gets a reason.
"""

from __future__ import annotations

import ast
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal

from shipharness.events import Arm, EventBus
from shipharness.filters.coverage import measure_coverage
from shipharness.filters.filters import DEFAULT_FILTERS, surviving_mutants
from shipharness.filters.models import (
    CandidateTest,
    CoverageMap,
    Filter,
    FilterContext,
    FilterResult,
)
from shipharness.filters.mutants import Mutant
from shipharness.filters.source import source_shas
from shipharness.runner.paths import PathOutsideWorkspace, resolve_in_workspace
from shipharness.sandbox.base import Sandbox

MAX_TEST_FILE_BYTES = 1_000_000


class FilterSetupError(RuntimeError):
    """The phase-start snapshot could not be taken (for example, the existing suite errors)."""


# [walkthrough:S4:filters] start
def run_pipeline(
    cands: list[CandidateTest],
    ctx: FilterContext,
    bus: EventBus | None,
    *,
    filters: Sequence[Filter] = DEFAULT_FILTERS,
    run_id: str | None = None,
    arm: Arm | None = None,
    phase: Literal["build", "test"] = "test",
) -> list[FilterResult]:
    """Run each proposed test through the filters; stop at its first failure. 1 imports and runs,
    2 passes 5 runs, 3 adds coverage or kills a mutant, 4 real assertions and no mocking of the
    unit under test, 5 no source change in the test phase."""
    results: list[FilterResult] = []
    for cand in cands:
        if bus is not None:
            bus.publish(
                "test_proposed", {"test_id": cand.test_id, "phase": phase}, run_id=run_id, arm=arm
            )
        for flt in filters:
            try:
                result = flt.evaluate(cand, ctx)
            except Exception as exc:  # noqa: BLE001 - a crashing filter discards, with a reason
                result = FilterResult(
                    test_id=cand.test_id,
                    filter=flt.number,
                    passed=False,
                    reason=f"filter error: {type(exc).__name__}: {exc}"[:500],
                )
            if not result.reason:
                result = result.model_copy(update={"reason": f"filter {flt.number}: no reason"})
            results.append(result)
            if bus is not None:
                bus.publish("test_filter_result", result, run_id=run_id, arm=arm)
            if not result.passed:
                break  # discarded: later (more expensive) filters never run
    return results


# [walkthrough:S4:filters] end


def run_pipeline_parallel(
    cands: list[CandidateTest],
    ctx: FilterContext,
    bus: EventBus | None,
    *,
    workers: int = 1,
    **kw: Any,
) -> list[FilterResult]:
    """`run_pipeline` with `workers` proposed tests going through the filters at the same time
    (each test's filters still in order, stopping at its first failure). Filter-set mutants are
    applied to the workspace in place, so with any of them the tests go one at a time. Results
    come back in proposal order, the same list `run_pipeline` returns."""
    if workers <= 1 or len(cands) <= 1 or ctx.filter_mutants:
        return run_pipeline(cands, ctx, bus, **kw)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        per_test = list(pool.map(lambda cand: run_pipeline([cand], ctx, bus, **kw), cands))
    return [result for results in per_test for result in results]


def discarded(results: list[FilterResult]) -> dict[str, FilterResult]:
    """Test id -> the result of the filter that discarded it."""
    return {r.test_id: r for r in results if not r.passed}


def kept_tests(results: list[FilterResult], filter_count: int = 5) -> list[str]:
    """Test ids that passed every filter, in proposal order."""
    passed: dict[str, set[int]] = {}
    rejected = set(discarded(results))
    for r in results:
        if r.passed:
            passed.setdefault(r.test_id, set()).add(r.filter)
    wanted = set(range(1, filter_count + 1))
    return [tid for tid, numbers in passed.items() if tid not in rejected and wanted <= numbers]


def _test_nodes(tree: ast.Module) -> list[str]:
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test"
        ):
            names.append(node.name)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            names.extend(
                f"{node.name}::{item.name}"
                for item in node.body
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
                and item.name.startswith("test")
            )
    return names


def collect_candidates(workspace: Path, files: list[str]) -> list[CandidateTest]:
    """One candidate per test function in the given workspace-relative files. A file that does not
    parse becomes a single candidate (its path), so filter 1 discards it with a reason."""
    cands: list[CandidateTest] = []
    for rel in files:
        try:
            path = resolve_in_workspace(workspace, rel)
        except PathOutsideWorkspace:
            continue
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_TEST_FILE_BYTES:
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        rel = Path(path).relative_to(Path(workspace).resolve()).as_posix()
        try:
            names = _test_nodes(ast.parse(source))
        except SyntaxError:
            cands.append(CandidateTest(test_id=rel, file=rel, source=source))
            continue
        cands.extend(
            CandidateTest(test_id=f"{rel}::{name}", file=rel, source=source) for name in names
        )
    return cands


def build_context(
    workspace: Path,
    sandbox: Sandbox,
    *,
    existing_tests: list[str] | None = None,
    mutants: list[Mutant] | None = None,
    target_module: str | None = None,
    python: str = "python",
    timeout_s: int = 300,
    runs: int = 5,
    doctest_modules: bool = False,
) -> FilterContext:
    """Snapshot at the start of the test phase: baseline coverage of the existing suite, filter-set
    mutants that the existing suite does not kill, and source fingerprints (filter 5).

    With `doctest_modules`, the existing suite runs with `--doctest-modules`, so doctests count
    in the baseline. Doctests are collected only from the given targets."""
    tests = list(existing_tests or [])
    baseline = measure_coverage(
        workspace,
        sandbox,
        tests,
        python=python,
        timeout_s=timeout_s,
        doctest_modules=doctest_modules,
    )
    if not baseline.ok:
        raise FilterSetupError(f"baseline coverage of the existing suite failed: {baseline.detail}")
    ctx = FilterContext(
        workspace=Path(workspace),
        sandbox=sandbox,
        baseline_coverage=baseline.coverage if baseline.ok else CoverageMap(),
        filter_mutants=[m for m in (mutants or []) if m.set == "filter"],
        source_shas_at_phase_start=source_shas(workspace),
        existing_tests=tests,
        target_module=target_module,
        python=python,
        timeout_s=timeout_s,
        runs=runs,
        doctest_modules=doctest_modules,
    )
    return ctx.model_copy(update={"surviving_mutant_ids": surviving_mutants(ctx)})
