"""session-handoff.md: the machine part, written by the harness at a session stop.

Everything here reads the untrusted workspace as data: files on the host (no links followed, size
caps), git through the sandbox only, and every agent-controlled string masked and capped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shipharness.harness import suite_cache
from shipharness.harness.scope.status import VISIBLE_TESTS_ARGS, VISIBLE_TESTS_COMMAND
from shipharness.log_setup import mask_keys
from shipharness.runner.models import SessionResult
from shipharness.runner.tools import _is_link, iter_workspace_files, summarise_pytest
from shipharness.sandbox.base import Sandbox

MACHINE = "## Machine summary"
NOTES = "## Notes from the agent"
GIT_LOG_COMMAND = "git log --oneline --no-decorate --no-color -5"
LINE_CAP = 160
MAX_SCAN_BYTES = 200_000
_TODO = re.compile(r"\b(TODO|FIXME|XXX)\b")
_REVISION = re.compile(r"""^revision\s*(?::[^=\n]+)?=\s*["']([^"']+)["']""", re.MULTILINE)
_DOWN = re.compile(r"^down_revision\s*(?::[^=\n]+)?=\s*(.+)$", re.MULTILINE)
_QUOTED = re.compile(r"""["']([^"']+)["']""")


def clean(text: str, cap: int = LINE_CAP) -> str:
    """Agent-controlled text for the handoff: keys masked, one line, capped."""
    return re.sub(r"[\r\n\t]+", " ", mask_keys(text)).strip()[:cap]


@dataclass
class MachineSummary:
    result: SessionResult
    files_changed: list[str]
    tests: str
    failures: list[str] = field(default_factory=list)
    commits: list[str] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)
    heads: str = ""
    docs_read: list[str] = field(default_factory=list)  # harness documents opened so far

    def render(self) -> str:
        r = self.result
        shown = self.files_changed[:30]
        more = len(self.files_changed) - len(shown)
        files = ", ".join(shown) + (f", and {more} more" if more else "")
        lines = [
            f"Written by the harness at the end of session {r.index} ({r.phase} phase, ended by "
            f"{r.ended_by} after {r.turns} turns).",
            "",
            f"- Commits: start {r.start_sha[:7] or 'none'}, end {r.end_sha[:7] or 'none'}",
            f"- Files changed in this session ({len(self.files_changed)}): {files or 'none'}",
            f"- Visible tests: {self.tests}",
            *(f"  - {line}" for line in self.failures),
            "- Last commits:" if self.commits else "- Last commits: none found",
            *(f"  - {line}" for line in self.commits),
            "- Open TODO markers in changed files:" if self.todos else "- Open TODO markers: none",
            *(f"  - {line}" for line in self.todos),
            f"- Migration heads: {self.heads}",
            "- Harness documents read so far: " + (", ".join(self.docs_read) or "none"),
        ]
        return "\n".join(lines)


def visible_tests(
    sandbox: Sandbox,
    timeout_s: int,
    *,
    state: dict[str, Any] | None = None,
    workspace: Path | None = None,
) -> tuple[str, list[str]]:
    """The visible-test status line and its first failures. With the run's `state` and
    `workspace`, an identical harness run on the same content is reused (suite_cache)."""
    if state is not None and workspace is not None:
        run = suite_cache.run(
            state, sandbox, workspace, VISIBLE_TESTS_ARGS, timeout_s, command=VISIBLE_TESTS_COMMAND
        )
    else:
        run = sandbox.exec(VISIBLE_TESTS_COMMAND, timeout_s)
    lines = summarise_pytest(run.output).splitlines()
    head = clean(lines[0]) if lines else "no output"
    failures = [clean(line) for line in lines[1:] if line.startswith(("FAILED", "ERROR"))]
    return f"{head} (exit {run.exit_code})" if run.exit_code else head, failures[:5]


def last_commits(sandbox: Sandbox) -> list[str]:
    run = sandbox.exec(GIT_LOG_COMMAND, 30)
    if run.exit_code != 0:
        return []
    return [clean(line) for line in run.output.splitlines() if line.strip()][:5]


def todo_markers(workspace: Path, paths: list[str], limit: int = 10) -> list[str]:
    rows: list[str] = []
    for rel in paths:
        path = Path(workspace) / rel
        if _is_link(path) or not path.is_file() or path.stat().st_size > MAX_SCAN_BYTES:
            continue
        text = path.read_bytes().decode("utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), start=1):
            if _TODO.search(line):
                rows.append(clean(f"{rel}:{number}: {line.strip()}"))
                if len(rows) >= limit:
                    return rows
    return rows


def migration_heads(workspace: Path) -> str:
    """Heads of the Alembic history, read from `migrations/versions/*.py` as text (never run)."""
    versions = Path(workspace) / "migrations" / "versions"
    if _is_link(versions) or not versions.is_dir():
        return "no migrations found"
    revisions: list[str] = []
    parents: set[str] = set()
    for path in iter_workspace_files(versions):
        if path.suffix != ".py" or path.stat().st_size > MAX_SCAN_BYTES:
            continue
        text = path.read_bytes().decode("utf-8", errors="replace")
        match = _REVISION.search(text)
        if match:
            revisions.append(match.group(1))
            down = _DOWN.search(text)
            if down:
                parents.update(_QUOTED.findall(down.group(1)))
    if not revisions:
        return "no migrations found"
    heads = sorted(clean(r, 60) for r in revisions if r not in parents)
    note = "" if len(heads) == 1 else "; there must be exactly one (House rule 7: Migrations)"
    return f"{len(heads)} ({', '.join(heads)}){note}"


def merge(existing: str | None, template: str, summary: str) -> str:
    """Header from the template, the new machine summary, and the agent's notes kept as written."""
    header = template.split(MACHINE, 1)[0]
    notes = template[template.index(NOTES) :]
    if existing and NOTES in existing:
        notes = existing[existing.index(NOTES) :]
    return f"{header}{MACHINE}\n\n{summary}\n\n{notes.rstrip()}\n"
