"""Self-check for assignment A4: run the visible tests against your implementation.

    uv run python section-4-verification/assignment/check.py [--impl <folder>]
    make check-assignment-4 [A4_IMPL=<folder>]

`--impl` is the folder that holds `a4_verification/`, `tests/`, `skill/`, `portfolio/`, and
`live/` (default: the starter in this folder). Prints PASS or FAIL for every visible test with the
reason, then the TODO markers still in your code and portfolio. The visible tests include the
live-evidence checks, which validate the files in `live/` without re-running them. The hidden
grader runs these tests plus hidden seeded violations and hidden candidate tests. No model calls,
no Docker: R8 runs in process on TeamTrack copies.

Exit codes: 0 every visible test passes, 1 otherwise (or the tests could not run).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ASSIGNMENT = Path(__file__).resolve().parent
VISIBLE = ASSIGNMENT / "visible_tests"
STARTER = ASSIGNMENT / "starter"
sys.path.insert(0, str(VISIBLE))

from a4_runner import RunError, run_tests  # noqa: E402

TODO = re.compile(r"\bTODO\b")


def todos(impl: Path) -> list[str]:
    """`file:line: text` for every TODO left in the code, the tests, and the portfolio."""
    found: list[str] = []
    files = [
        *sorted((impl / "a4_verification").glob("*.py")),
        *sorted((impl / "tests").glob("*.py")),
        *sorted((impl / "portfolio").glob("*.md")),
    ]
    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if TODO.search(line):
                found.append(f"{path.relative_to(impl).as_posix()}:{number}: {line.strip()}")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check.py", description=__doc__)
    parser.add_argument("--impl", type=Path, default=STARTER)
    args = parser.parse_args(argv)
    impl = args.impl.resolve()
    print(f"A4 self-check for {impl}")
    try:
        outcomes, _output = run_tests(impl, [VISIBLE])
    except RunError as exc:
        print(f"ERROR the visible tests could not run: {exc}")
        print("self-check: FAILED")
        return 1
    current = None
    for o in sorted(outcomes, key=lambda o: o.criterion):
        if o.criterion != current:
            current = o.criterion
            print(f"\n[{current}]")
        if o.passed:
            print(f"  PASS {o.name}")
        else:
            print(f"  FAIL {o.name}: {o.message}")
    left = todos(impl)
    if left:
        print(f"\nTODO markers left ({len(left)}):")
        for line in left[:40]:
            print(f"  {line}")
    passed = sum(o.passed for o in outcomes)
    verdict = "PASSED" if outcomes and passed == len(outcomes) else "FAILED"
    print(f"\nself-check: {verdict} ({passed}/{len(outcomes)} visible tests pass)")
    if verdict == "PASSED":
        print("Next: submit this folder with its live/; the grader adds the hidden tests.")
    print("Cost: $0.000000 (no model calls)")
    return 0 if verdict == "PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())
