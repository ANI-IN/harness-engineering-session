"""One visible-suite run per workspace content.

The gate, the session stop, and the passes update each run the same visible tests. When the
workspace content has not changed since a harness run of the suite, the result of that run is
reused instead of running the suite again. Only harness runs fill the cache; the agent's own
run_visible_tests calls never do.

The key is the content of every workspace file, read on the host without following links. Left
out are the directories `iter_workspace_files` skips (`.git`, `__pycache__`, ...) and the two notes
files the harness itself writes at a session stop (`progress.md`, `session-handoff.md`), which no
test imports: the passes update runs right after the session stop commits them.

A result is reused only when it finished (no time-out, no sandbox denial). A result from the
gate's copy of the workspace is reused in the workspace, and the reverse, only when every test
passed (exit 0): the summary is then the counts line alone, the same text in either place.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Literal

from shipharness.runner.tools import iter_workspace_files
from shipharness.sandbox.base import ExecResult, Sandbox

Where = Literal["workspace", "copy"]
STATE_KEY = "harness.visible_suite_runs"
NOTES_FILES = frozenset({"progress.md", "session-handoff.md"})


def content_key(workspace: Path) -> str:
    """sha256 over (path, content sha256) of every workspace file except the notes files."""
    root = Path(workspace)
    digest = hashlib.sha256()
    for path in iter_workspace_files(root):
        rel = path.relative_to(root).as_posix()
        if rel in NOTES_FILES or path.suffix == ".pyc":
            continue
        try:
            data = path.read_bytes()
        except OSError:
            data = b"<unreadable>"
        digest.update(rel.encode() + b"\0" + hashlib.sha256(data).digest())
    return digest.hexdigest()


def _runs(state: dict[str, Any]) -> dict[tuple[str, str], tuple[Where, ExecResult]]:
    runs = state.get(STATE_KEY)
    if not isinstance(runs, dict):
        runs = {}
        state[STATE_KEY] = runs
    return runs


def lookup(state: dict[str, Any], key: str, args: str, where: Where) -> ExecResult | None:
    """The cached result for this content and these pytest arguments, if it may be reused here."""
    found = _runs(state).get((key, args))
    if found is None:
        return None
    ran_in, result = found
    if ran_in != where and result.exit_code != 0:
        return None
    return result


def store(state: dict[str, Any], key: str, args: str, where: Where, result: ExecResult) -> None:
    if result.timed_out or result.denied is not None:
        return
    _runs(state)[(key, args)] = (where, result)


def run(
    state: dict[str, Any],
    sandbox: Sandbox,
    workspace: Path,
    args: str,
    timeout_s: int,
    *,
    where: Where = "workspace",
    command: str | None = None,
) -> ExecResult:
    """Run `python -m pytest <args>` (or `command`, which must run exactly that) unless an
    identical run on the same content can be reused. The key is taken before the run, so files
    the run itself writes make the next lookup miss."""
    key = content_key(workspace)
    cached = lookup(state, key, args, where)
    if cached is not None:
        return cached
    result = sandbox.exec(command or f"python -m pytest {args}", timeout_s)
    store(state, key, args, where, result)
    return result
