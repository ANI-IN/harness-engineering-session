#!/usr/bin/env python3
"""One-shot status artifact: gate exit codes, floors, and tree counts.

Runs every make gate, prints each real exit code, and prints the floors
(from tools/expected_counts.json) beside the counts discovered in the tree,
so a status report can be pasted from this output instead of being retyped
by hand. Exits non-zero if any gate failed or any count is below its floor.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import run_verify  # noqa: E402
from tools.conformance import runner  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
GATES = (
    "doctor", "verify-dedup", "conformance",
    "lint", "lint-links", "lint-mermaid", "lint-structure",
)


def main() -> int:
    failures = 0
    print("gate            exit")
    for gate in GATES:
        proc = subprocess.run(
            ["make", gate], cwd=REPO_ROOT, capture_output=True, text=True
        )
        print(f"{gate:15s} {proc.returncode}")
        if proc.returncode != 0:
            failures += 1
            tail = "\n".join(proc.stdout.strip().split("\n")[-6:])
            print(f"--- {gate} output tail ---\n{tail}\n---")

    print(
        "note: verify-dedup runs the verify gate with unit conformance covered"
        " once, by the conformance gate above; coverage equality is proven by"
        " tools/test_dedup_coverage.py (docs/conventions.md, dedup mode)."
    )
    floors = json.loads((REPO_ROOT / "tools" / "expected_counts.json").read_text())
    counts = {
        "conformance_units": len(runner.discover_units(REPO_ROOT)),
        "verify_scripts": len(run_verify.discover_scripts(REPO_ROOT)),
        "lectures": len(list(REPO_ROOT.glob("lectures/lecture-*"))),
        "exercises": len(list(REPO_ROOT.glob("lectures/lecture-*/exercises/exercise-*"))),
        "projects": len(list(REPO_ROOT.glob("projects/project-*"))),
    }
    print("\ncount              found  floor")
    for name, found in counts.items():
        floor = floors.get(f"min_{name}", 0)
        marker = "" if found >= floor else "  BELOW FLOOR"
        print(f"{name:18s} {found:5d}  {floor:5d}{marker}")
        if found < floor:
            failures += 1

    print(f"\nstatus: {'FAIL' if failures else 'OK'} ({failures} problem(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
