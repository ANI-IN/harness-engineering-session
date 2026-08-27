#!/usr/bin/env python3
"""Run every curriculum verify.sh, with a fail-on-empty floor.

Scans lectures/, projects/, and tools/conformance/selftest/ for verify.sh
scripts and runs each with --stack=both. The number found must meet
min_verify_scripts in tools/expected_counts.json: a broken discovery glob
fails loudly instead of reporting success on an empty set.

This is the single source of the verify loop; the Makefile's `verify` target
calls it (after the pytest and vitest suites).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEARCH_ROOTS = ("lectures", "projects", "tools/conformance/selftest")
COUNTS_MANIFEST = REPO_ROOT / "tools" / "expected_counts.json"


def discover_scripts(root: Path) -> list[Path]:
    scripts = []
    for search_root in SEARCH_ROOTS:
        base = root / search_root
        if base.is_dir():
            scripts.extend(sorted(base.rglob("verify.sh")))
    return scripts


def run_all(root: Path, floor: int) -> int:
    scripts = discover_scripts(root)
    if len(scripts) < floor:
        print(
            f"verify: FAIL: discovered {len(scripts)} verify.sh script(s) but "
            f"tools/expected_counts.json requires at least {floor}. "
            "Either discovery is broken or the manifest is stale."
        )
        return 1

    failures = 0
    for script in scripts:
        label = script.relative_to(root) if script.is_relative_to(root) else script
        command = ["bash", str(script), "--stack=both"]
        # Exercises default to checking the learner's starter workspace; the
        # repo-level invariant is --target=ci (starter fails as intended AND
        # solution passes). See docs/conventions.md.
        if "exercises" in script.parts:
            command.append("--target=ci")
        print(f"verify: running {label}")
        proc = subprocess.run(command, cwd=script.parent)
        if proc.returncode != 0:
            print(f"verify: FAIL: {label} exited {proc.returncode}")
            failures += 1

    print(f"verify: {len(scripts)} script(s), {failures} failure(s)")
    return 1 if failures else 0


def main() -> int:
    floor = int(json.loads(COUNTS_MANIFEST.read_text(encoding="utf-8"))["min_verify_scripts"])
    return run_all(REPO_ROOT, floor)


if __name__ == "__main__":
    sys.exit(main())
