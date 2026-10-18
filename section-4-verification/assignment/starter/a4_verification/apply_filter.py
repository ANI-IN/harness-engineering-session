"""Run filter 6 over the tests a `shipharness testgen` run kept.

    uv run python -m a4_verification.apply_filter --repo <repo> --kept <testgen out dir> \\
        --existing <test file or folder> [--existing ...] [--update-report]

`--kept` is the folder testgen printed as "Kept tests and report" (it holds `testgen-report.json`
and the kept test files). `--existing` names the repo's existing tests, relative to `--repo`. The
filter compares each kept test with the existing tests and with the kept tests before it. Nothing
is executed: filter 6 only reads source. Exit 0 after a report, 1 on bad input.

With `--update-report` the filter-6 results also go into `testgen-report.json`: one row per kept
test, with `filter` 6, is appended to `results` after the rows of filters 1-5, and a `filter6`
object records the tests filter 6 kept (`kept`) and how many existing tests it compared
(`existing_tests`). `kept` and the testgen rows stay as testgen wrote them. A second run replaces
the filter-6 rows of the first. This updated report is the assignment's live testgen evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from a4_verification.dedup_filter import NoDuplicateTest
from shipharness.filters import CoverageMap, FilterContext, collect_candidates, run_pipeline
from shipharness.filters.models import FilterResult


def _test_files(repo: Path, targets: list[str]) -> list[str]:
    files: list[str] = []
    for target in targets:
        path = (repo / target).resolve()
        if path.is_dir():
            found = sorted(path.rglob("test_*.py")) + sorted(path.rglob("*_test.py"))
            files.extend(p.relative_to(repo.resolve()).as_posix() for p in found)
        elif path.is_file():
            files.append(path.relative_to(repo.resolve()).as_posix())
        else:
            raise ValueError(f"existing test path not found: {target}")
    return list(dict.fromkeys(files))


def update_report(
    path: Path, report: dict[str, Any], results: list[FilterResult], existing: int
) -> None:
    """Write `report` back with the filter-6 rows appended (earlier filter-6 rows replaced)."""
    rows = [row for row in report.get("results", []) if row.get("filter") != 6]
    rows += [r.model_dump() for r in results]
    kept = [r.test_id for r in results if r.passed]
    updated = {**report, "results": rows, "filter6": {"kept": kept, "existing_tests": existing}}
    path.write_text(json.dumps(updated, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m a4_verification.apply_filter")
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--kept", type=Path, required=True)
    parser.add_argument("--existing", action="append", default=[], required=True)
    parser.add_argument(
        "--update-report",
        action="store_true",
        help="Append the filter-6 results to testgen-report.json (rows with filter 6, `filter6`).",
    )
    args = parser.parse_args(argv)
    report_path = args.kept / "testgen-report.json"
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        existing = collect_candidates(args.repo, _test_files(args.repo, args.existing))
    except (OSError, ValueError) as exc:
        print(f"ERROR {exc}")
        return 1
    kept_ids = [str(t) for t in report.get("kept", [])]
    files = list(dict.fromkeys(tid.split("::", 1)[0] for tid in kept_ids))
    by_id = {c.test_id: c for c in collect_candidates(args.kept, files)}
    cands = [by_id[tid] for tid in kept_ids if tid in by_id]
    ctx = FilterContext(
        workspace=args.kept,
        sandbox=None,
        baseline_coverage=CoverageMap(),
        filter_mutants=[],
        source_shas_at_phase_start={},
    )
    flt = NoDuplicateTest(existing)
    results = run_pipeline(cands, ctx, None, filters=[flt])
    for result in results:
        sign = "+" if result.passed else "-"
        print(f"{sign} {result.test_id}: filter {result.filter}: {result.reason}")
    kept = sum(1 for r in results if r.passed)
    missing = len(kept_ids) - len(cands)
    print(
        f"filter 6 kept {kept} of {len(cands)} kept tests "
        f"({len(existing)} existing tests compared; {missing} kept ids not found)"
    )
    if args.update_report:
        update_report(report_path, report, results, len(existing))
        print(f"report updated: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
