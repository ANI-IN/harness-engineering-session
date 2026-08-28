"""init-check: the session replay and the startup-readiness doctor.

`replay` is the demo: a scripted session with a fixed step budget attempts
the same feature task against a repository, and every failing readiness
check injects its cost at the exact moment it bites (a missing progress
log costs re-derivation at the start; a missing pin costs a mid-install
failure; a non-strict init script costs a mysterious mid-feature failure).
On the broken fixture the budget runs out mid-feature: the collapsing
session is demonstrated, not narrated. `doctor` (the original surface)
runs the same four checks up front and predicts the replay, which is the
lecture's argument: initialization is the phase that buys the session
back. SPEC.md pins the rules, the step costs, and the seeded symptoms.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PAIRS = [("pyproject.toml", ".python-version"), ("package.json", ".nvmrc")]


def check_dependencies_pinned(repo: Path) -> tuple[bool, str]:
    found = []
    missing = []
    for manifest, pin in PAIRS:
        if (repo / manifest).is_file():
            if (repo / pin).is_file():
                found.append(f"{manifest} + {pin}")
            else:
                missing.append(f"{manifest} present but {pin} missing")
    if missing:
        return False, "; ".join(missing)
    if not found:
        return False, "no dependency manifest found"
    return True, "; ".join(found)


def check_init_script(repo: Path) -> tuple[bool, str]:
    script = repo / "init.sh"
    if not script.is_file():
        return False, "init.sh missing"
    if not os.access(script, os.X_OK):
        return False, "init.sh is not executable"
    if "set -euo pipefail" not in script.read_text(encoding="utf-8"):
        return False, "init.sh does not enable strict mode (set -euo pipefail)"
    return True, "init.sh executable with strict mode"


def check_verification_command(repo: Path) -> tuple[bool, str]:
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = repo / name
        if path.is_file():
            match = re.search(
                r"^- Verification: (.+)$", path.read_text(encoding="utf-8"), re.MULTILINE
            )
            if match:
                return True, f"{name}: {match.group(1).strip()}"
    return False, "no Verification line in AGENTS.md or CLAUDE.md"


def check_progress_artifact(repo: Path) -> tuple[bool, str]:
    path = repo / "claude-progress.md"
    if not path.is_file():
        return False, "claude-progress.md missing"
    if not re.search(
        r"^- Next best step: .+$", path.read_text(encoding="utf-8"), re.MULTILINE
    ):
        return False, "claude-progress.md has no Next best step line"
    return True, "claude-progress.md with a Next best step line"


CHECKS = [
    ("dependencies-pinned", check_dependencies_pinned),
    ("init-script", check_init_script),
    ("verification-command", check_verification_command),
    ("progress-artifact", check_progress_artifact),
]


def doctor(repo: Path) -> dict:
    checks = []
    for check_id, run in CHECKS:
        passed, detail = run(repo)
        checks.append({"id": check_id, "passed": passed, "detail": detail})
    return {"checks": checks, "ready": all(check["passed"] for check in checks)}


STEP_BUDGET = 12
FEATURE_STEPS = 5


def replay(repo: Path) -> dict:
    """The scripted session (SPEC.md, "The replay"). Costs derive from the
    same four checks the doctor runs; nothing here re-inspects files."""
    verdict = {check["id"]: check for check in doctor(repo)["checks"]}
    events = []
    remaining = STEP_BUDGET

    def spend(action: str, outcome: str) -> bool:
        nonlocal remaining
        if remaining <= 0:
            return False
        remaining -= 1
        events.append({"step": STEP_BUDGET - remaining, "action": action, "outcome": outcome})
        return True

    overhead = 0
    if verdict["progress-artifact"]["passed"]:
        spend("read the progress log", "resume point found; no re-derivation")
    else:
        spend("read the progress log", "missing; the session starts by guessing")
        spend("re-derive project state", "scan the repository structure")
        spend("re-derive project state", "reconstruct decisions already made once")
        overhead += 2
    if verdict["dependencies-pinned"]["passed"]:
        spend("install dependencies", "pinned interpreter; install clean")
    else:
        spend("install dependencies", "wrong interpreter; ModuleNotFoundError mid-install")
        spend("pin and reinstall", "environment rebuilt by hand")
        overhead += 1
    strict_init = verdict["init-script"]["passed"]
    spend(
        "run init.sh",
        "environment verified strictly" if strict_init
        else "exited 0 over a half-built environment (no strict mode)",
    )

    completed = True
    for step in range(1, FEATURE_STEPS + 1):
        if not spend(f"feature step {step}", "progress on the export feature"):
            completed = False
            break
        if step == 2 and not strict_init:
            ok = spend(
                "feature test fails mysteriously",
                "traced back to the half-built environment init.sh hid",
            )
            ok = ok and spend("rebuild the environment", "the loud failure init.sh owed us")
            overhead += 2
            if not ok:
                completed = False
                break

    verified = False
    if completed:
        if verdict["verification-command"]["passed"]:
            command = verdict["verification-command"]["detail"]
            verified = spend(f"run the verification command ({command})", "pass")
            completed = verified
        else:
            spend("claim done", "no verification command recorded; the claim is unbacked")

    return {
        "repo": repo.name,
        "budget": STEP_BUDGET,
        "events": events,
        "steps_spent": STEP_BUDGET - remaining,
        "setup_overhead": overhead,
        "feature_completed": completed,
        "verified": verified,
    }


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "replay":
        repo = Path(argv[2])
        if not repo.is_dir():
            print(f"error: not a directory: {repo}", file=sys.stderr)
            return 2
        report = replay(repo)
        print(json.dumps(report, indent=2))
        return 0 if report["feature_completed"] and report["verified"] else 1
    if len(argv) != 2:
        print("usage: main.py <repo-dir> | main.py replay <repo-dir>", file=sys.stderr)
        return 2
    repo = Path(argv[1])
    if not repo.is_dir():
        print(f"error: not a directory: {repo}", file=sys.stderr)
        return 2
    report = doctor(repo)
    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
