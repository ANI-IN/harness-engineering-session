"""subsystem-auditor exercise, Python starter.

All five audits run, but three are naive first drafts with a realistic
mistake each (see SPEC.md "Starter state"): the tools audit trusts what the
instructions MENTION instead of what exists, the environment audit checks
the manifest but not the runtime pin, and the state audit checks the
feature list but not the progress file. Fix audit_tools, audit_environment,
and audit_state to the SPEC's criteria. Run ../../verify.sh --stack=python
until it exits 0. Everything else already works.
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
    # Naive draft: trusts the instructions file's word for it. Describing a
    # tool is not having it. Exercise: present when verify.sh EXISTS in the
    # repo; evidence "verify.sh".
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = repo / name
        if path.is_file() and "verify.sh" in path.read_text(encoding="utf-8"):
            return _finding(True, f"verify.sh mentioned in {name}")
    return _finding(False, None)


def audit_environment(repo: Path) -> dict:
    # Naive draft: a manifest alone. Dependencies without a runtime pin
    # reproduce the tree on the wrong interpreter. Exercise: require the
    # pin too; check the Python pair (pyproject.toml + .python-version)
    # first, then the Node pair (package.json + .nvmrc); evidence is
    # "<manifest> + <pin>".
    for manifest in ("pyproject.toml", "package.json"):
        if (repo / manifest).is_file():
            return _finding(True, manifest)
    return _finding(False, None)


def audit_state(repo: Path) -> dict:
    # Naive draft: the feature list alone. Scope without narrative still
    # loses sessions. Exercise: present only when BOTH feature_list.json
    # and claude-progress.md exist; evidence
    # "feature_list.json + claude-progress.md".
    if (repo / "feature_list.json").is_file():
        return _finding(True, "feature_list.json")
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
