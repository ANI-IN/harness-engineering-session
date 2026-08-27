"""ablation-report exercise, Python solution.

Aggregates the six minimal-harness-loop reports (baseline + five single
ablations) into one controlled-variable comparison: what changed, per
removed subsystem, against the all-enabled baseline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SUBSYSTEMS = ("instructions", "state", "environment", "tools", "feedback")


def load_report(reports_dir: Path, name: str) -> dict:
    return json.loads((reports_dir / name).read_text(encoding="utf-8"))


def compare(baseline: dict, ablated: dict) -> dict:
    issues = ablated["issues"]
    return {
        "disabled": ablated["disabled"],
        "outcome": ablated["outcome"],
        "outcome_changed": ablated["outcome"] != baseline["outcome"],
        "issues": len(issues),
        "signature": issues[0] if issues else None,
    }


def build_report(reports_dir: Path) -> dict:
    baseline = load_report(reports_dir, "full.json")
    ablations = [
        compare(baseline, load_report(reports_dir, f"disable-{name}.json"))
        for name in SUBSYSTEMS
    ]
    return {
        "baseline": {"outcome": baseline["outcome"], "issues": len(baseline["issues"])},
        "ablations": ablations,
        "all_degraded": all(entry["outcome_changed"] for entry in ablations),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: main.py <reports-dir>", file=sys.stderr)
        return 2
    reports_dir = Path(argv[1])
    if not reports_dir.is_dir():
        print(f"error: not a directory: {reports_dir}", file=sys.stderr)
        return 2
    print(json.dumps(build_report(reports_dir), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
