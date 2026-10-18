"""A2 self-check: run the visible scenarios against your state layer and show what fails.

    uv run python section-2-state-lifecycle/assignment/check.py [--impl <folder>] [--keep]

`--impl` is the folder that holds your `a2_state` package (default: assignment/starter). Exit code
0 when every criterion passes in every visible scenario, 1 otherwise. No model calls, no network,
no Docker: the agent is the test stand-in agent (a2_scenario/literal_agent.py), a deterministic
program that follows fixed rules, not a model. The self-check also reports whether `<impl>/live/`
holds valid evidence of the required live step (graded, not part of the exit code). The
instructor's grader adds hidden scenarios and prints the score out of 100.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from a2_scenario import live_evidence  # noqa: E402
from a2_scenario.report import load_layer, print_scenario, run_and_evaluate, shown  # noqa: E402
from a2_scenario.scenarios import VISIBLE  # noqa: E402


def print_live(impl: Path) -> None:
    """Whether `<impl>/live/` holds valid evidence of the required live step."""
    head = f"Live evidence (graded, {live_evidence.LIVE_POINTS} points)"
    problems = live_evidence.validate(impl)
    if not (Path(impl) / live_evidence.EVIDENCE_DIR).is_dir():
        print(f"{head}: not found in {shown(Path(impl) / live_evidence.EVIDENCE_DIR)}.")
        print("  Run the required live step once your layer is final (SPEC.md, evidence section).")
    elif problems:
        print(f"{head}: {len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
    else:
        print(f"{head}: valid ({live_evidence.describe(impl)})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A2 self-check (visible scenarios).")
    parser.add_argument("--impl", type=Path, default=HERE / "starter", help="folder with a2_state")
    parser.add_argument("--keep", action="store_true", help="keep the scenario workspaces")
    args = parser.parse_args(argv)
    factory = load_layer(args.impl)
    root = Path(tempfile.mkdtemp(prefix="a2-check-"))
    print(f"A2 self-check: {len(VISIBLE)} visible scenarios against {shown(args.impl)}")
    print(
        "Agent: the test stand-in agent (a2_scenario/literal_agent.py), deterministic, not a model."
    )
    print("Each scenario: four sessions, three forced stops by the session turn budget.\n")
    results = []
    try:
        for scenario in VISIBLE:
            result = run_and_evaluate(factory, scenario, root / scenario.name)
            print_scenario(result)
            if args.keep and result.run is not None:
                print(f"  workspace: {result.run.workspace}")
            print()
            results.append(result)
    finally:
        if not args.keep:
            shutil.rmtree(root, ignore_errors=True)
    checks = [o for r in results for o in r.outcomes]
    passed = sum(1 for o in checks if o.fraction == 1.0)
    print(f"Self-check: {passed} of {len(checks)} checks pass.")
    print_live(args.impl)
    if passed == len(checks):
        print("All visible scenarios pass. The grader adds hidden scenarios of the same kinds.")
        return 0
    print("Fix the FAIL and HALF lines (the hints name the TODOs in a2_state), then run again.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
