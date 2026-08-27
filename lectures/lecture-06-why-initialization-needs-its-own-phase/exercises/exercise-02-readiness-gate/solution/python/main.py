"""readiness-gate exercise, Python solution.

Turns a set of readiness check results into a tiered verdict and exit
code: blockers stop a session from starting; advice does not, but must
stay visible. Contract: ../../SPEC.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

EXIT_READY = 0
EXIT_BLOCKED = 1
EXIT_ADVICE = 3


def gate(checks: list[dict]) -> tuple[dict, int]:
    blockers_failed = [c["id"] for c in checks if c["severity"] == "blocker" and not c["passed"]]
    advice_failed = [c["id"] for c in checks if c["severity"] == "advice" and not c["passed"]]
    if blockers_failed:
        verdict, code = "blocked", EXIT_BLOCKED
    elif advice_failed:
        verdict, code = "ready-with-advice", EXIT_ADVICE
    else:
        verdict, code = "ready", EXIT_READY
    report = {
        "blockers_failed": blockers_failed,
        "advice_failed": advice_failed,
        "verdict": verdict,
    }
    return report, code


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: main.py <check-results.json>", file=sys.stderr)
        return 2
    try:
        data = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    except OSError as error:
        print(f"error: cannot read results: {error}", file=sys.stderr)
        return 2
    report, code = gate(data["checks"])
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
