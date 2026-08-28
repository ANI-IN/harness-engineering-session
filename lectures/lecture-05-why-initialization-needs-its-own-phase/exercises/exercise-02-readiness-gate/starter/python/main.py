"""readiness-gate exercise, Python starter.

The counting works; the tiering does not. The naive draft treats every
failed check as a blocker, so advice-only failures block the session and
exit 1 where the SPEC requires ready-with-advice and exit 3. Fix gate()
per SPEC.md. Run ../../verify.sh --stack=python until it exits 0.
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
    # Naive draft: severity exists so that advice does not block; treating
    # every failure as a blocker erases the tier. Exercise: blockers give
    # "blocked"/exit 1; advice-only gives "ready-with-advice"/exit 3;
    # otherwise "ready"/exit 0.
    if blockers_failed or advice_failed:
        verdict, code = "blocked", EXIT_BLOCKED
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
