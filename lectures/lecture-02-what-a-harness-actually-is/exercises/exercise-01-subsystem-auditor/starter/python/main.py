"""subsystem-auditor exercise, Python starter.

Two of the five subsystem audits are implemented (instructions, feedback).
Your task: implement audit_tools, audit_environment, and audit_state per
SPEC.md. Run ../../verify.sh --stack=python until it exits 0. Everything
outside those three functions already works.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SUBSYSTEMS = ("instructions", "tools", "environment", "state", "feedback")


def _finding(present: bool, evidence: str | None) -> dict:
    return {"present": present, "evidence": evidence if present else None}


def audit_instructions(repo: Path) -> dict:
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = repo / name
        if path.is_file() and path.read_text(encoding="utf-8").strip():
            return _finding(True, name)
    return _finding(False, None)


def audit_tools(repo: Path) -> dict:
    # Exercise: present when verify.sh exists in the repo; evidence "verify.sh".
    return _finding(False, None)


def audit_environment(repo: Path) -> dict:
    # Exercise: present when a manifest AND a runtime pin exist. Check the
    # Python pair (pyproject.toml + .python-version) first, then the Node
    # pair (package.json + .nvmrc); evidence is "<manifest> + <pin>".
    return _finding(False, None)


def audit_state(repo: Path) -> dict:
    # Exercise: present only when BOTH feature_list.json and
    # claude-progress.md exist; evidence "feature_list.json + claude-progress.md".
    return _finding(False, None)


def audit_feedback(repo: Path) -> dict:
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = repo / name
        if path.is_file():
            for line in path.read_text(encoding="utf-8").split("\n"):
                if line.strip().startswith("- Verification:"):
                    return _finding(True, f"Verification line in {name}")
    return _finding(False, None)


AUDITS = {
    "instructions": audit_instructions,
    "tools": audit_tools,
    "environment": audit_environment,
    "state": audit_state,
    "feedback": audit_feedback,
}


def audit_repo(repo: Path) -> dict:
    subsystems = {name: AUDITS[name](repo) for name in SUBSYSTEMS}
    missing = [name for name in SUBSYSTEMS if not subsystems[name]["present"]]
    present = len(SUBSYSTEMS) - len(missing)
    return {
        "name": repo.name,
        "subsystems": subsystems,
        "score": f"{present}/{len(SUBSYSTEMS)}",
        "missing": missing,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: main.py <repos-dir>", file=sys.stderr)
        return 2
    repos_dir = Path(argv[1])
    if not repos_dir.is_dir():
        print(f"error: not a directory: {repos_dir}", file=sys.stderr)
        return 2
    repos = sorted(path for path in repos_dir.iterdir() if path.is_dir())
    report = {"repos": [audit_repo(repo) for repo in repos], "audited": len(repos)}
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
