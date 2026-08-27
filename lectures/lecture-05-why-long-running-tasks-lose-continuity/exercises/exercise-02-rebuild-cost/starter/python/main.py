"""rebuild-cost exercise, Python starter.

The report plumbing works; the savings orientation does not. The naive
draft subtracts without-handoff from with-handoff for every metric, which
flips the sign of every saving and makes the handoff look like a cost.
Fix savings() per SPEC.md: positive must always mean the handoff mode did
better. Run ../../verify.sh --stack=python until it exits 0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def savings(with_totals: dict, without_totals: dict) -> dict:
    # Naive draft: one subtraction direction for every metric. Costs and
    # completions point opposite ways, so this flips the sign of every
    # saving. Exercise: orient each metric so positive always means the
    # handoff mode did better.
    return {
        "reacquisition_lines": with_totals["reacquisition_lines"]
        - without_totals["reacquisition_lines"],
        "features_completed": without_totals["features_completed"]
        - with_totals["features_completed"],
        "rework_sessions": with_totals["rework_sessions"] - without_totals["rework_sessions"],
        "drift_events": with_totals["drift_events"] - without_totals["drift_events"],
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
