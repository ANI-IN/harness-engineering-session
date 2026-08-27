#!/usr/bin/env python3
"""Cross-stack conformance runner.

Discovers every curriculum unit (a directory containing SPEC.md + cases.json),
executes its declared cases against BOTH implementations, and diffs three ways:

    python  vs expected/     typescript vs expected/     python vs typescript

All comparisons run through tools/conformance/normalize.py, the definition of
"byte-identical" for this repository. Any post-normalization divergence fails
the build, and the failure names the first diverging field (JSON) or line
(text).

Discovery covers lectures/, projects/, and tools/conformance/selftest/ (the
canary unit that keeps this gate provably functional). The number of
discovered units must meet the floor in tools/expected_counts.json:
a broken discovery glob fails loudly instead of reporting success on an
empty set.

cases.json contract (per unit):
{
  "entry": {"python": "python/main.py", "typescript": "typescript/main.ts"},
  "cases": [
    {
      "name": "basic",
      "args": ["fixtures/input.json"],
      "stdin": null,                      # or a path relative to the unit
      "expect": {
        "exit_code": 0,
        "stdout": "expected/basic.json",  # null = assert python == typescript only
        "kind": "auto",                   # normalization kind: auto|json|text
        "files": [                        # artifacts written by the run
          {"path": "out/report.json", "expected": "expected/report.json"}
        ]
      }
    }
  ]
}

For exercise units, entry points name the solution tracks
(e.g. "solution/python/main.py"); starters are exercised by verify.sh.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.conformance.normalize import first_divergence, normalize  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SEARCH_ROOTS = ("lectures", "projects", "tools/conformance/selftest")
ALL_STACKS = ("python", "typescript")
COUNTS_MANIFEST = REPO_ROOT / "tools" / "expected_counts.json"

# When HARNESS_COVERAGE_LOG names a file, every executed case appends one
# tab-separated identifier line (unit, stage, stack, case). The dedup
# coverage proof compares these sets between the full and deduplicated
# verification paths; see tools/test_dedup_coverage.py.
COVERAGE_LOG_ENV = "HARNESS_COVERAGE_LOG"
_coverage_lock = threading.Lock()


def log_coverage(unit: Path, stage_label: str, stack: str, case_name: str) -> None:
    log_path = os.environ.get(COVERAGE_LOG_ENV)
    if not log_path:
        return
    line = f"{unit_label(unit)}\t{stage_label}\t{stack}\t{case_name}\n"
    with _coverage_lock, open(log_path, "a", encoding="utf-8") as handle:
        handle.write(line)


@dataclass
class CaseResult:
    unit: str
    case: str
    stack: str
    ok: bool
    detail: str = ""
    stdout_normalized: str | None = None


@dataclass
class UnitReport:
    unit: str
    results: list[CaseResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(result.ok for result in self.results)


def unit_label(unit: Path) -> str:
    try:
        return str(unit.relative_to(REPO_ROOT))
    except ValueError:
        return str(unit)


def discover_units(root: Path) -> list[Path]:
    units = []
    for search_root in SEARCH_ROOTS:
        base = root / search_root
        if not base.is_dir():
            continue
        for spec in sorted(base.rglob("SPEC.md")):
            unit_dir = spec.parent
            if (unit_dir / "cases.json").is_file():
                units.append(unit_dir)
    return units


def minimum_units() -> int:
    manifest = json.loads(COUNTS_MANIFEST.read_text(encoding="utf-8"))
    return int(manifest["min_conformance_units"])


def resolve_entry(unit: Path, entry: str, stage: str | None) -> str:
    """Staged units (starter/ + solution/) write cases.json entries relative
    to the stage directory; plain units write them relative to the unit."""
    if (unit / "solution").is_dir() and (unit / "starter").is_dir():
        return f"{stage or 'solution'}/{entry}"
    return entry


def _entry_command(unit: Path, entry: str) -> list[str]:
    path = unit / entry
    if entry.endswith(".py"):
        return ["uv", "run", "--project", str(REPO_ROOT), "python", str(path)]
    if entry.endswith(".ts"):
        # Invoke the tsx binary directly: `pnpm --dir` would reset the child's
        # working directory to the repo root, clobbering the case's temp cwd.
        return [str(REPO_ROOT / "node_modules" / ".bin" / "tsx"), str(path)]
    raise ValueError(f"{unit}: unsupported entry point {entry!r}")


def _read_expected(unit: Path, relative: str) -> str:
    return (unit / relative).read_text(encoding="utf-8")


def run_case(unit: Path, entry: str, case: dict, stack: str, workdir: Path) -> CaseResult:
    name = case["name"]
    expect = case["expect"]
    command = _entry_command(unit, entry) + [str(arg) for arg in case.get("args", [])]
    stdin_text = None
    if case.get("stdin"):
        stdin_text = (unit / case["stdin"]).read_text(encoding="utf-8")

    proc = subprocess.run(
        command,
        cwd=workdir,
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=120,
    )

    if proc.returncode != expect["exit_code"]:
        return CaseResult(
            unit_label(unit), name, stack, False,
            f"exit code {proc.returncode} != expected {expect['exit_code']}; "
            f"stderr: {proc.stderr.strip()[:400]}",
        )

    kind = expect.get("kind", "auto")
    try:
        got_stdout = normalize(proc.stdout, kind=kind)
    except json.JSONDecodeError as error:
        return CaseResult(
            unit_label(unit), name, stack, False,
            f"stdout is not valid JSON (kind={kind}): {error}; "
            f"stdout head: {proc.stdout[:120]!r}",
        )

    if expect.get("stdout"):
        want = normalize(_read_expected(unit, expect["stdout"]), kind=kind)
        if got_stdout != want:
            return CaseResult(
                unit_label(unit), name, stack, False,
                f"stdout mismatch vs {expect['stdout']}: "
                f"diverges at {first_divergence(got_stdout, want)}",
                stdout_normalized=got_stdout,
            )

    for artifact in expect.get("files", []):
        written = workdir / artifact["path"]
        if not written.is_file():
            return CaseResult(
                unit_label(unit), name, stack, False,
                f"expected artifact not written: {artifact['path']}",
            )
        got = normalize(written.read_text(encoding="utf-8"), kind=artifact.get("kind", "auto"))
        want = normalize(
            _read_expected(unit, artifact["expected"]), kind=artifact.get("kind", "auto")
        )
        if got != want:
            return CaseResult(
                unit_label(unit), name, stack, False,
                f"artifact mismatch {artifact['path']}: "
                f"diverges at {first_divergence(got, want)}",
            )

    return CaseResult(unit_label(unit), name, stack, True, stdout_normalized=got_stdout)


def run_unit(
    unit: Path, stacks: tuple[str, ...] = ALL_STACKS, stage: str | None = None
) -> UnitReport:
    config = json.loads((unit / "cases.json").read_text(encoding="utf-8"))
    report = UnitReport(unit_label(unit))
    by_case: dict[str, dict[str, CaseResult]] = {}

    staged = (unit / "solution").is_dir() and (unit / "starter").is_dir()
    stage_label = (stage or "solution") if staged else "plain"
    for stack in stacks:
        entry = resolve_entry(unit, config["entry"][stack], stage)
        for case in config["cases"]:
            with tempfile.TemporaryDirectory(prefix="conformance-") as tmp:
                workdir = Path(tmp)
                fixtures = unit / "fixtures"
                if fixtures.is_dir():
                    shutil.copytree(fixtures, workdir / "fixtures")
                result = run_case(unit, entry, case, stack, workdir)
            log_coverage(unit, stage_label, stack, case["name"])
            report.results.append(result)
            by_case.setdefault(case["name"], {})[stack] = result

    # Direct cross-stack parity check on stdout, regardless of expected/ pins.
    if set(stacks) == set(ALL_STACKS):
        for case_name, per_stack in by_case.items():
            py, ts = per_stack.get("python"), per_stack.get("typescript")
            if not py or not ts or not (py.ok and ts.ok):
                continue
            if py.stdout_normalized != ts.stdout_normalized:
                where = first_divergence(py.stdout_normalized or "", ts.stdout_normalized or "")
                report.results.append(
                    CaseResult(
                        unit_label(unit), case_name, "python-vs-typescript", False,
                        f"normalized stdout differs between the two stacks: diverges at {where}",
                    )
                )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="cross-stack conformance runner")
    parser.add_argument("--unit", help="run only this unit directory")
    parser.add_argument(
        "--stack", choices=["python", "typescript", "both"], default="both",
        help="restrict execution to one stack (cross-stack diff needs both)",
    )
    parser.add_argument(
        "--stage", choices=["starter", "solution"], default=None,
        help="for staged units (exercises): which stage to execute (default solution)",
    )
    parser.add_argument(
        "--jobs", type=int, default=0,
        help="parallel unit workers (default: min(8, cpu count); 1 = sequential)",
    )
    parser.add_argument(
        "--root", default=None,
        help="discovery root override (tests only; skips the unit-count floor)",
    )
    args = parser.parse_args()
    stacks = ALL_STACKS if args.stack == "both" else (args.stack,)

    if args.unit:
        units = [Path(args.unit).resolve()]
        if not (units[0] / "SPEC.md").is_file() or not (units[0] / "cases.json").is_file():
            print(f"conformance: {args.unit} is not a unit (needs SPEC.md + cases.json)")
            return 1
    else:
        root = Path(args.root).resolve() if args.root else REPO_ROOT
        units = discover_units(root)
        if args.root is None:
            floor = minimum_units()
            if len(units) < floor:
                print(
                    f"conformance: FAIL: discovered {len(units)} unit(s) but "
                    f"tools/expected_counts.json requires at least {floor}. "
                    "Either discovery is broken or the manifest is stale."
                )
                return 1

    # Units run in a worker pool (each unit's cases stay sequential inside
    # it), but reports are collected and printed strictly in discovery
    # order, so output and failure positions are deterministic regardless
    # of completion order.
    jobs = args.jobs if args.jobs > 0 else min(8, os.cpu_count() or 2)
    if jobs == 1 or len(units) <= 1:
        reports = [run_unit(unit, stacks, args.stage) for unit in units]
    else:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = [pool.submit(run_unit, unit, stacks, args.stage) for unit in units]
            reports = [future.result() for future in futures]

    failures = 0
    checked = 0
    for report in reports:
        checked += len(report.results)
        status = "OK" if report.ok else "FAIL"
        print(f"conformance: {report.unit}: {status}")
        for result in report.results:
            marker = "pass" if result.ok else "FAIL"
            line = f"  [{marker}] {result.case} ({result.stack})"
            if result.detail:
                line += f" -- {result.detail}"
            print(line)
            if not result.ok:
                failures += 1

    print(f"conformance: {len(units)} unit(s), {checked} check(s), {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
