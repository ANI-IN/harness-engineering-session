"""init-doctor exercise, Python solution: the startup-readiness doctor.

Runs the four readiness checks a fresh session depends on, in order, and
delivers a verdict: exit 0 when every later session can start from a
known-good state, exit 1 when initialization still owes something. All
checks are file-based and language-neutral; SPEC.md pins each rule and the
seeded symptoms in the broken fixture.
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


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: main.py <repo-dir>", file=sys.stderr)
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
