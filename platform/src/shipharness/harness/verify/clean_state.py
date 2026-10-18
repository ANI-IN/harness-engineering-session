"""Clean-state check (A2, F-a-84): the work is committed, changed Python files are ruff clean,
there is one migration head (when the repository has migrations), and no debug output was added.
Runs in the arm's own container."""

from __future__ import annotations

import fnmatch
import re
import shlex

from shipharness.harness.verify.models import GateItem
from shipharness.sandbox.base import Sandbox

_GENERATED = (
    "*__pycache__*",
    "*.pyc",
    "*.pytest_cache*",
    "*.ruff_cache*",
    "*.mypy_cache*",
    "*.import_linter_cache*",
    "*node_modules*",
    "*.venv/*",
    "*.coverage",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
)
_DEBUG = re.compile(r"^\+\s*(print\(|breakpoint\(\)|import pdb|pdb\.set_trace\()")
_SHA = re.compile(r"^[0-9a-f]{40}$")


def _generated(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in _GENERATED)


def _status_paths(output: str) -> list[str]:
    paths = []
    for line in output.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].split(" -> ")[-1].strip().strip('"')
        if path and not _generated(path):
            paths.append(path)
    return paths


def _debug_lines(diff: str) -> list[str]:
    found, current = [], ""
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else line[4:]
        elif _DEBUG.match(line) and current:
            found.append(f"{current}: {line[1:].strip()[:80]}")
    return found


# Ruff's documented default rule set. A repository without its own ruff config is checked against
# it, so the gate does not depend on which rules the installed ruff version enables by default
# (ruff 0.17.1 in the agent image also enables B008 and I001, which TeamTrack's FastAPI routers do
# not meet).
DEFAULT_RUFF_SELECT = "E4,E7,E9,F"


def clean_state_check(
    sandbox: Sandbox,
    base_sha: str,
    timeout_s: int = 120,
    *,
    migrations: bool = True,
    ruff_select: str | None = DEFAULT_RUFF_SELECT,
) -> GateItem:
    """`migrations=False` (a repository without alembic.ini or migrations/versions) skips the
    migration head check: `alembic heads` would fail there for a reason the agent cannot fix.
    `ruff_select=None` (the repository has its own ruff config) runs ruff with that config."""
    problems: list[str] = []
    status = sandbox.exec("git status --porcelain --untracked-files=all", timeout_s)
    if status.exit_code != 0:
        problems.append(f"git status failed: {status.output.strip()[:120]}")
    elif dirty := _status_paths(status.output):
        shown = ", ".join(dirty[:5]) + (f" (+{len(dirty) - 5} more)" if len(dirty) > 5 else "")
        problems.append(f"uncommitted changes: {shown} (commit or remove them)")

    if _SHA.match(base_sha):
        names = sandbox.exec(
            f"git diff --name-only --diff-filter=AM {base_sha} -- '*.py'", timeout_s
        )
        changed = [n.strip() for n in names.output.splitlines() if n.strip().endswith(".py")]
        if changed:
            files = " ".join(shlex.quote(n) for n in changed[:200])
            select = f"--select {ruff_select} " if ruff_select else ""
            ruff = sandbox.exec(
                f"ruff check --no-cache --quiet --output-format=concise {select}{files}", timeout_s
            )
            if ruff.exit_code != 0:
                lines = [ln for ln in ruff.output.splitlines() if ln.strip()]
                problems.append(f"ruff: {lines[0][:160] if lines else 'failed'}")
        diff = sandbox.exec(f"git diff -U0 {base_sha} -- '*.py' ':(exclude)tests/**'", timeout_s)
        if debug := _debug_lines(diff.output):
            problems.append("debug output: " + "; ".join(debug[:3]))

    if migrations:
        heads = sandbox.exec("alembic heads", timeout_s)
        count = heads.output.count("(head)")
        if heads.exit_code != 0:
            problems.append(f"alembic heads failed: {heads.output.strip()[-120:]}")
        elif count != 1:
            problems.append(f"migration heads: {count} (expected 1)")

    if problems:
        return GateItem(name="clean state", status="fail", detail="; ".join(problems))
    if not migrations:
        detail = "committed, ruff clean; migration heads skipped: no migrations configured"
        return GateItem(name="clean state", status="pass", detail=detail)
    return GateItem(name="clean state", status="pass", detail="committed, ruff clean, one head")
