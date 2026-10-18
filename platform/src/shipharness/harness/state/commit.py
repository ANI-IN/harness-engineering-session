"""Harness commits of harness-written files, run inside the sandbox.

Host code never runs git against the workspace (its `.git/config` belongs to the agent). The commit
runs in the arm's sandbox, like the agent's own commands, and names its paths so that anything the
agent staged stays out of the harness commit (`git commit -- <paths>` commits only those paths).
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from shipharness.sandbox.base import ExecResult, Sandbox

HARNESS_GIT_NAME = "shipharness"
HARNESS_GIT_EMAIL = "harness@shipharness.invalid"
_SAFE_PATH = re.compile(r"^[A-Za-z0-9._/-]+$")
_UNSAFE_MESSAGE = re.compile(r"[^A-Za-z0-9 ._:()/,-]")


def commit_command(paths: Sequence[str], message: str) -> str:
    """Shell command (valid in bash and cmd.exe) that stages and commits only `paths`."""
    bad = [p for p in paths if not _SAFE_PATH.match(p) or p.startswith(("-", "/")) or ".." in p]
    if not paths or bad:
        raise ValueError(f"unsafe or empty path list for a harness commit: {bad or paths}")
    quoted = " ".join(f'"{p}"' for p in paths)
    text = _UNSAFE_MESSAGE.sub("", message)[:120] or "harness update"
    return (
        f"git add -A -- {quoted} && git -c user.name={HARNESS_GIT_NAME} "
        f"-c user.email={HARNESS_GIT_EMAIL} commit -q --no-verify "
        f'-m "{text}" -- {quoted}'
    )


def commit_paths(
    sandbox: Sandbox, paths: Sequence[str], message: str, timeout_s: int = 60
) -> ExecResult:
    """Commit harness-written files. A non-zero exit (for example, nothing changed) is returned,
    not raised: the files on disk are what the agent reads either way."""
    return sandbox.exec(commit_command(paths, message), timeout_s)
