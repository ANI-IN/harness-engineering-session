"""Run A4 test folders against one implementation and read back per-test outcomes.

Used by `assignment/check.py` (visible tests) and by the instructor's grader (visible + hidden).
pytest runs in a subprocess, so the implementation's `a4_verification` package is imported in a
fresh process and the check registry starts empty.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

TIMEOUT_S = 1800


@dataclass(frozen=True)
class Outcome:
    nodeid: str
    criterion: str
    passed: bool
    message: str = ""

    @property
    def name(self) -> str:
        return self.nodeid.rsplit("::", 1)[-1]


class RunError(RuntimeError):
    """pytest did not produce results (collection error, crash, or timeout)."""


def run_tests(
    impl: Path, paths: list[Path], timeout_s: int = TIMEOUT_S
) -> tuple[list[Outcome], str]:
    """Run pytest on `paths` with `A4_IMPL=impl`; return the outcomes and pytest's output."""
    with tempfile.TemporaryDirectory(prefix="a4-results-") as tmp:
        results = Path(tmp) / "results.json"
        env = {**os.environ, "A4_IMPL": str(impl), "A4_RESULTS": str(results)}
        command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rN"]
        command += [str(p) for p in paths]
        try:
            run = subprocess.run(
                command, capture_output=True, text=True, env=env, timeout=timeout_s
            )
        except subprocess.TimeoutExpired as exc:
            raise RunError(f"pytest timed out after {timeout_s} s") from exc
        output = run.stdout + run.stderr
        if not results.is_file():
            raise RunError(f"pytest produced no results (exit {run.returncode}):\n{output[-3000:]}")
        rows = json.loads(results.read_text(encoding="utf-8"))
    outcomes = [
        Outcome(
            nodeid=row["nodeid"],
            criterion=row.get("criterion", ""),
            passed=bool(row.get("passed")),
            message=" ".join(str(row.get("message", "")).split())[:300],
        )
        for row in rows
    ]
    return outcomes, output
