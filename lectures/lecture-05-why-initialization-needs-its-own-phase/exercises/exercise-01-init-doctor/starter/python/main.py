"""init-doctor exercise, Python starter.

All four checks run, but three are naive first drafts that stop at
existence (see SPEC.md "Starter state"): dependencies-pinned accepts a
manifest without its runtime pin, init-script accepts any init.sh file,
and progress-artifact accepts any progress file. Fix the three per
SPEC.md; verification-command is already correct. Run
../../verify.sh --stack=python until it exits 0.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PAIRS = [("pyproject.toml", ".python-version"), ("package.json", ".nvmrc")]


def check_dependencies_pinned(repo: Path) -> tuple[bool, str]:
    # Naive draft: a manifest without its runtime pin reproduces the
    # dependency tree on the wrong interpreter. Exercise: every manifest
    # present must have its pin; detail names pairs or the missing pin.
    found = [manifest for manifest, _pin in PAIRS if (repo / manifest).is_file()]
    if not found:
        return False, "no dependency manifest found"
    return True, "; ".join(found)


def check_init_script(repo: Path) -> tuple[bool, str]:
    # Naive draft: a file named init.sh is not a working init phase.
    # Exercise: it must also be executable and enable strict mode
    # (set -euo pipefail); detail names whichever property is missing.
    if (repo / "init.sh").is_file():
        return True, "init.sh present"
    return False, "init.sh missing"


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
    # Naive draft: a progress file without a Next best step line leaves the
    # next session guessing anyway. Exercise: require the tagged line.
    if (repo / "claude-progress.md").is_file():
        return True, "claude-progress.md present"
    return False, "claude-progress.md missing"


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
