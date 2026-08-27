#!/usr/bin/env python3
"""Enforce the four-acceptance-runs record for every exercise.

Every exercise in the tree must have all four acceptance runs recorded in
build_state.json (starter and solution, each stack), so the count is
enforced rather than remembered. build_state.json is a gitignored local
working file: when it is absent (fresh clones, CI), this check reports that
and passes; there, the equivalent enforcement is each exercise verify.sh's
--target=ci mode, which performs the four runs live on every `make verify`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = REPO_ROOT / "build_state.json"
REQUIRED_RUNS = ("starter-python", "starter-typescript", "solution-python", "solution-typescript")


def exercise_keys(root: Path) -> list[str]:
    keys = []
    for exercise in sorted(root.glob("lectures/lecture-*/exercises/exercise-*")):
        keys.append(f"{exercise.parent.parent.name}/{exercise.name}")
    return keys


def check(state: dict, keys: list[str]) -> list[str]:
    errors = []
    recorded = state.get("acceptance_runs", {})
    for key in keys:
        runs = recorded.get(key)
        if runs is None:
            errors.append(f"{key}: no acceptance runs recorded in build_state.json")
            continue
        missing = [name for name in REQUIRED_RUNS if name not in runs]
        if missing:
            errors.append(
                f"{key}: {len(REQUIRED_RUNS) - len(missing)}/4 acceptance runs recorded; "
                f"missing {', '.join(missing)}"
            )
    return errors


def main() -> int:
    keys = exercise_keys(REPO_ROOT)
    if not STATE_PATH.is_file():
        print(
            f"check-build-state: build_state.json absent (CI/fresh clone); "
            f"{len(keys)} exercise(s) are covered live by verify.sh --target=ci"
        )
        return 0
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    errors = check(state, keys)
    print(f"check-build-state: {len(keys)} exercise(s), 4 runs required each")
    for error in errors:
        print(f"  FAIL {error}")
    if errors:
        print(f"check-build-state: {len(errors)} error(s)")
        return 1
    print("check-build-state: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
