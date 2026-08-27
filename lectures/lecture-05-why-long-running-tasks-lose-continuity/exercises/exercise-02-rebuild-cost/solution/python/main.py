"""rebuild-cost exercise, Python solution.

Compares the simulator's two committed runs and computes what the handoff
artifacts buy: savings are oriented so a positive number always means the
handoff mode did better. Contract: ../../SPEC.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def savings(with_totals: dict, without_totals: dict) -> dict:
    """Costs (reacquisition, rework, drift) save when WITHOUT exceeds WITH;
    completions save when WITH exceeds WITHOUT. Orienting each metric keeps
    'positive = handoff wins' true for all of them."""
    return {
        "reacquisition_lines": without_totals["reacquisition_lines"]
        - with_totals["reacquisition_lines"],
        "features_completed": with_totals["features_completed"]
        - without_totals["features_completed"],
        "rework_sessions": without_totals["rework_sessions"] - with_totals["rework_sessions"],
        "drift_events": without_totals["drift_events"] - with_totals["drift_events"],
    }


def build_report(reports_dir: Path) -> dict:
    with_report = json.loads((reports_dir / "with-handoff.json").read_text(encoding="utf-8"))
    without_report = json.loads((reports_dir / "no-handoff.json").read_text(encoding="utf-8"))
    return {
        "with_handoff": with_report["totals"],
        "without_handoff": without_report["totals"],
        "savings": savings(with_report["totals"], without_report["totals"]),
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
