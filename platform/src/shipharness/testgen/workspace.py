"""A fresh workspace for testgen: a filtered copy of the learner's repo with one initial commit.

The agent never works in the learner's repository itself. The copy is made with
`iter_workspace_files` (links are never followed) and the git repository is created by the host
before the agent touches it, so its config is the default one.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path, PurePosixPath

from shipharness.filters.scratch import is_scratch
from shipharness.runner.tools import iter_workspace_files

# Never copied into the agent's workspace (I-6: held-out material and local state).
EXCLUDED_DIRS = ("mutants", "harness", "reference", "tests/hidden")
EXCLUDED_SUFFIXES = (".db", ".pyc")


def _excluded(rel: str) -> bool:
    if is_scratch(rel) or rel.endswith(EXCLUDED_SUFFIXES):
        return True
    path = PurePosixPath(rel)
    return any(path.is_relative_to(d) for d in EXCLUDED_DIRS) or rel == ".env"


def _git_env(home: Path) -> dict[str, str]:
    keep = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return {
        **keep,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "HOME": str(home),
        "GIT_TERMINAL_PROMPT": "0",
    }


def prepare_workspace(repo: Path, workspace: Path) -> int:
    """Copy `repo` into the new directory `workspace` and commit it. Returns the file count."""
    repo, workspace = Path(repo), Path(workspace)
    workspace.mkdir(parents=True, exist_ok=False)
    count = 0
    for path in iter_workspace_files(repo):
        rel = path.relative_to(repo).as_posix()
        if _excluded(rel):
            continue
        target = workspace / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        count += 1
    env = _git_env(workspace.parent)
    base = ["git", "-C", str(workspace), "-c", f"core.hooksPath={os.devnull}"]
    ident = ["-c", "user.name=shipharness", "-c", "user.email=shipharness@localhost.invalid"]
    for argv in (
        ["git", "init", "-q", str(workspace)],
        [*base, "-c", "core.autocrlf=false", "add", "-A"],
        [*base, *ident, "commit", "-q", "-m", "testgen: initial import"],
    ):
        result = subprocess.run(argv, capture_output=True, env=env, check=False)
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()[:300]
            raise RuntimeError(f"git failed while preparing the workspace: {detail}")
    return count
