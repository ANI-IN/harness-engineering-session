#!/usr/bin/env python3
"""Cross-stack conformance runner.

Discovers every curriculum unit (a directory containing SPEC.md + cases.json),
executes its declared cases against BOTH implementations, and diffs three ways:

    python  vs expected/     typescript vs expected/     python vs typescript

All comparisons run through tools/conformance/normalize.py — the definition of
"byte-identical" for this repository. Any post-normalization divergence fails
the build.

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
        "stdout": "expected/basic.out",   # null = assert python == typescript only
        "kind": "auto",                   # normalization kind: auto|json|text
        "files": [                        # artifacts written by the run
          {"path": "out/report.json", "expected": "expected/report.json"}
        ]
      }
    }
  ]
}

For exercise units, entry points name the solution tracks
(e.g. "solution/python/main.py") — starters are exercised by verify.sh.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.conformance.normalize import normalize  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SEARCH_ROOTS = ("lectures", "projects")
STACKS = ("python", "typescript")


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


def _entry_command(unit: Path, entry: str) -> list[str]:
    path = unit / entry
    if entry.endswith(".py"):
        return ["uv", "run", "--project", str(REPO_ROOT), "python", str(path)]
    if entry.endswith(".ts"):
        return ["pnpm", "--dir", str(REPO_ROOT), "exec", "tsx", str(path)]
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

    kind = expect.get("kind", "auto")
    got_stdout = normalize(proc.stdout, kind=kind)

    if proc.returncode != expect["exit_code"]:
        return CaseResult(
            unit.name, name, stack, False,
            f"exit code {proc.returncode} != expected {expect['exit_code']}; "
            f"stderr: {proc.stderr.strip()[:400]}",
        )

    if expect.get("stdout"):
        want = normalize(_read_expected(unit, expect["stdout"]), kind=kind)
        if got_stdout != want:
            return CaseResult(
                unit.name, name, stack, False,
                f"stdout mismatch vs {expect['stdout']} (after normalization)",
                stdout_normalized=got_stdout,
            )

    for artifact in expect.get("files", []):
        written = workdir / artifact["path"]
        if not written.is_file():
            return CaseResult(
                unit.name, name, stack, False,
                f"expected artifact not written: {artifact['path']}",
            )
        got = normalize(written.read_text(encoding="utf-8"), kind=artifact.get("kind", "auto"))
        want = normalize(
            _read_expected(unit, artifact["expected"]), kind=artifact.get("kind", "auto")
        )
        if got != want:
            return CaseResult(
                unit.name, name, stack, False,
                f"artifact mismatch: {artifact['path']} vs {artifact['expected']}",
            )

    return CaseResult(unit.name, name, stack, True, stdout_normalized=got_stdout)


def run_unit(unit: Path) -> UnitReport:
    config = json.loads((unit / "cases.json").read_text(encoding="utf-8"))
    report = UnitReport(str(unit.relative_to(REPO_ROOT)))
    by_case: dict[str, dict[str, CaseResult]] = {}

    for stack in STACKS:
        entry = config["entry"][stack]
        for case in config["cases"]:
            with tempfile.TemporaryDirectory(prefix="conformance-") as tmp:
                workdir = Path(tmp)
                fixtures = unit / "fixtures"
                if fixtures.is_dir():
                    shutil.copytree(fixtures, workdir / "fixtures")
                result = run_case(unit, entry, case, stack, workdir)
            report.results.append(result)
            by_case.setdefault(case["name"], {})[stack] = result

    # Direct cross-stack parity check on stdout, regardless of expected/ pins.
    for case_name, per_stack in by_case.items():
        py, ts = per_stack.get("python"), per_stack.get("typescript")
        if not py or not ts or not (py.ok and ts.ok):
            continue
        if py.stdout_normalized != ts.stdout_normalized:
            report.results.append(
                CaseResult(
                    unit.name, case_name, "python-vs-typescript", False,
                    "normalized stdout differs between the two stacks",
                )
            )
    return report


def main() -> int:
    units = discover_units(REPO_ROOT)
    if not units:
        print("conformance: 0 units with SPEC.md + cases.json found (skeleton state) — OK")
        return 0

    failures = 0
    checked = 0
    for unit in units:
        report = run_unit(unit)
        checked += len(report.results)
        status = "OK" if report.ok else "FAIL"
        print(f"conformance: {report.unit}: {status}")
        for result in report.results:
            marker = "pass" if result.ok else "FAIL"
            line = f"  [{marker}] {result.case} ({result.stack})"
            if result.detail:
                line += f" — {result.detail}"
            print(line)
            if not result.ok:
                failures += 1

    print(f"conformance: {len(units)} unit(s), {checked} check(s), {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
