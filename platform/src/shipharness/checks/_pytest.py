"""Run pytest inside a build in a child process and collect per-test outcomes."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from shipharness.checks._proc import run_python, tail
from shipharness.checks.base import Finding

PLUGIN = "shipharness.checks._pytest_plugin"


@dataclass
class PytestRun:
    returncode: int
    outcomes: dict[str, str] = field(default_factory=dict)  # nodeid -> outcome (last one wins)
    output: str = ""

    @property
    def failed(self) -> list[str]:
        return sorted(n for n, o in self.outcomes.items() if o not in ("passed", "skipped"))


def run_pytest(build_dir: Path, targets: list[str], timeout: float = 600) -> PytestRun:
    """`python -m pytest <targets>` from the build directory with the outcome plugin loaded."""
    with tempfile.TemporaryDirectory(prefix="shipharness-pytest-") as tmp:
        report = Path(tmp) / "report.jsonl"
        args = ["-m", "pytest", *targets, "-q", "-p", "no:cacheprovider", "-p", PLUGIN]
        args += ["-o", "addopts=", "--color=no"]
        proc = run_python(
            args, build_dir, {"SHIPHARNESS_PYTEST_REPORT": str(report)}, timeout=timeout
        )
        outcomes: dict[str, str] = {}
        if report.exists():
            for line in report.read_text(encoding="utf-8").splitlines():
                record = json.loads(line)
                outcomes[record["nodeid"]] = record["outcome"]
    return PytestRun(proc.returncode, outcomes, proc.stdout + "\n" + proc.stderr)


def collect_ids(build_dir: Path, targets: list[str]) -> list[str]:
    """Node ids pytest would run for `targets` (modules that fail to import list nothing)."""
    args = ["-m", "pytest", *targets, "--collect-only", "-q", "-p", "no:cacheprovider"]
    proc = run_python([*args, "-o", "addopts=", "--color=no"], build_dir)
    return [line.strip() for line in proc.stdout.splitlines() if "::" in line]


def outcome_finding(rule: str, nodeid: str, outcome: str, severity: str = "violation") -> Finding:
    return Finding(
        rule=rule,
        severity=severity,  # type: ignore[arg-type]
        detail_key=f"test:{nodeid}",
        detail=f"{nodeid}: {outcome}",
    )


def no_tests_finding(rule: str, run: PytestRun) -> Finding:
    return Finding(
        rule=rule,
        severity="error",
        detail_key="no_tests",
        detail=f"pytest ran no tests (exit {run.returncode}): {tail(run.output)}",
    )
