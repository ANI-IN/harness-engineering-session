#!/usr/bin/env python3
"""Canonical acceptance-run transcript for one exercise.

Performs the four acceptance runs (starter and solution, each stack) and
prints one deterministic line per run. Exercise READMEs embed this command
in a generated block, so every published four-run transcript is produced by
execution and re-verified by `make verify`; a report that quotes the block
cannot show a count different from what was executed.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.conformance import runner  # noqa: E402


def transcript(unit: Path) -> tuple[str, int]:
    lines = []
    performed = 0
    failures = 0
    for stage in ("starter", "solution"):
        for stack in ("python", "typescript"):
            report = runner.run_unit(unit, (stack,), stage)
            performed += 1
            checks = len(report.results)
            if report.ok:
                exit_code = 0
                detail = f"pass ({checks} check{'s' if checks != 1 else ''})"
            else:
                exit_code = 1
                first_fail = next(r for r in report.results if not r.ok)
                marker = "diverges at"
                detail = (
                    first_fail.detail[first_fail.detail.index(marker):]
                    if marker in first_fail.detail
                    else first_fail.detail
                )
            expected_ok = stage == "solution"
            if (exit_code == 0) != expected_ok:
                failures += 1
                verdict = "INVARIANT BROKEN"
            else:
                verdict = "as intended" if stage == "starter" else "PASS"
            lines.append(f"{stage}/{stack}: exit {exit_code} ({verdict}: {detail})")
    lines.append(f"{performed}/4 acceptance runs performed")
    return "\n".join(lines), (1 if failures else 0)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: run_acceptance.py <exercise-dir>", file=sys.stderr)
        return 2
    unit = Path(sys.argv[1]).resolve()
    if not (unit / "cases.json").is_file():
        print(f"error: not a conformance unit: {unit}", file=sys.stderr)
        return 2
    text, status = transcript(unit)
    print(text)
    return status


if __name__ == "__main__":
    sys.exit(main())
