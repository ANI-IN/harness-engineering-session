"""The seven agent tools: identical schemas and behaviour for both arms."""

from __future__ import annotations

import hashlib
import os
import re
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from shipharness.events import Arm, EventBus
from shipharness.harness.decisions import HarnessDecision
from shipharness.log_setup import mask_keys
from shipharness.runner import patch_format
from shipharness.runner.git import workspace_git_dir
from shipharness.runner.models import (
    TEAMTRACK_VISIBLE_TESTS,
    ToolCall,
    ToolResult,
    checked_tests_dir,
)
from shipharness.runner.paths import PathOutsideWorkspace, resolve_in_workspace
from shipharness.sandbox.base import Sandbox

TOOL_OUTPUT_MAX_CHARS = 8000
MAX_FILE_BYTES = 1_000_000  # read_file refuses, search skips, larger files (review M6)
MAX_LINE_CHARS = 2000  # read_file shows, search scans, at most this many chars of a line
SEARCH_TIME_BUDGET_S = 10.0  # search stops and says so after this long
TRUNCATION_ADVICE = (
    "the full output is kept in the run log outside the workspace, where you cannot read it; "
    "narrow the command instead, for example pipe it through grep or tail"
)
SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".import_linter_cache",
}
PATCH_FILE = ".git/shipharness-patch.diff"
_SAFE_ID = re.compile(r"[^A-Za-z0-9_-]")


def _is_link(path: Path) -> bool:
    """Symlink or Windows junction. Links in the workspace are never followed by host code."""
    return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())


def iter_workspace_files(root: Path) -> Iterator[Path]:
    """Regular files under `root`, sorted, skipping SKIP_DIRS and never following links."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        dirnames[:] = sorted(
            d for d in dirnames if d not in SKIP_DIRS and not _is_link(current / d)
        )
        for name in sorted(filenames):
            path = current / name
            if not _is_link(path) and path.is_file():
                yield path


def _fn(name: str, description: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
        "strict": True,
    }


_NULL_INT = {"type": ["integer", "null"]}
_NULL_STR = {"type": ["string", "null"]}


def tool_schemas(visible_tests_dir: str = TEAMTRACK_VISIBLE_TESTS) -> list[dict[str, Any]]:
    """The seven tool schemas. Order and text are fixed: the tool list is part of the cached
    prompt prefix. Only run_visible_tests names the run's visible-test directory; for TeamTrack
    (tests/visible) the list is byte-identical to TOOL_SCHEMAS."""
    where = visible_tests_dir
    return [
        _fn(
            "list_dir",
            "List files and directories under a workspace path. Directories end with '/'.",
            {
                "path": {"type": "string", "description": "Workspace-relative directory, e.g. '.'"},
                "depth": {**_NULL_INT, "description": "Levels to descend (1-3, default 1)."},
            },
        ),
        _fn(
            "read_file",
            "Read a UTF-8 text file from the workspace, with line numbers.",
            {
                "path": {"type": "string", "description": "Workspace-relative file path."},
                "start_line": {**_NULL_INT, "description": "First line to show (default 1)."},
                "max_lines": {**_NULL_INT, "description": "Lines to show (default 400)."},
            },
        ),
        _fn(
            "search",
            "Search workspace text files with a regular expression. Returns path:line: text rows.",
            {
                "pattern": {"type": "string", "description": "Python regular expression."},
                "path": {**_NULL_STR, "description": "Workspace-relative directory (default '.')."},
                "max_results": {**_NULL_INT, "description": "Maximum rows (default 50)."},
            },
        ),
        _fn(
            "apply_patch",
            "Apply a patch to the workspace: the '*** Begin Patch' format (*** Add File, "
            "*** Update File, *** Delete File sections; @@ hunks are found by their context lines) "
            "or a unified diff.",
            {"patch": {"type": "string", "description": "Patch text for one or more files."}},
        ),
        _fn(
            "run",
            "Run a shell command in the workspace sandbox (no network). "
            "Returns exit code and output.",
            {
                "command": {"type": "string", "description": "Command line, run with bash -lc."},
                "timeout_s": {**_NULL_INT, "description": "Seconds before the command is stopped."},
            },
        ),
        _fn(
            "run_visible_tests",
            f"Run the visible tests ({where}); returns a summary plus one line per failure.",
            {
                "selector": {
                    **_NULL_STR,
                    "description": f"Optional pytest node selector inside {where}.",
                }
            },
        ),
        _fn(
            "finish",
            "End the current phase. Use claim=done only when the ticket's work for this phase is "
            "complete; use not_done to stop without completing it.",
            {
                "claim": {"type": "string", "enum": ["done", "not_done"]},
                "summary": {
                    "type": "string",
                    "description": "What was done and how it was checked.",
                },
            },
        ),
    ]


TOOL_SCHEMAS: list[dict[str, Any]] = tool_schemas()
TOOL_NAMES: tuple[str, ...] = tuple(tool["name"] for tool in TOOL_SCHEMAS)


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ListDirArgs(_Args):
    path: str = "."
    depth: int | None = None


class ReadFileArgs(_Args):
    path: str
    start_line: int | None = None
    max_lines: int | None = None


class SearchArgs(_Args):
    pattern: str
    path: str | None = None
    max_results: int | None = None


class ApplyPatchArgs(_Args):
    patch: str


class RunArgs(_Args):
    command: str
    timeout_s: int | None = None


class RunVisibleTestsArgs(_Args):
    selector: str | None = None


class FinishArgs(_Args):
    claim: Literal["done", "not_done"]
    summary: str = Field(max_length=2000)


ARG_MODELS: dict[str, type[_Args]] = {
    "list_dir": ListDirArgs,
    "read_file": ReadFileArgs,
    "search": SearchArgs,
    "apply_patch": ApplyPatchArgs,
    "run": RunArgs,
    "run_visible_tests": RunVisibleTestsArgs,
    "finish": FinishArgs,
}

_NODE_PARTS = r"(::[\w\[\]\-.]+)*$"


def selector_pattern(visible_tests_dir: str) -> re.Pattern[str]:
    """Selectors run_visible_tests accepts: a path inside the visible-test directory, with
    optional ::node parts (tests/visible gives the TeamTrack pattern)."""
    if visible_tests_dir == ".":
        return re.compile(r"^(?![/-])[\w.\-/]+" + _NODE_PARTS)
    return re.compile("^" + re.escape(visible_tests_dir) + r"(/[\w.\-/]*)?" + _NODE_PARTS)


_SUMMARY_COUNT = re.compile(r"(\d+) (passed|failed|errors?)\b")
_FAILURE_LINE = re.compile(r"^(FAILED|ERROR) (\S+)(?: - (.*))?$")


def _cap_line(line: str) -> str:
    if len(line) <= MAX_LINE_CHARS:
        return line
    return f"{line[:MAX_LINE_CHARS]} [line cut: {len(line) - MAX_LINE_CHARS} more chars]"


def truncate(text: str, limit: int = TOOL_OUTPUT_MAX_CHARS) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def patch_paths(patch: str) -> tuple[list[str], bool]:
    """Paths named in ---/+++ headers or anchored headers (`*** Update File: <path>` and the
    rest), in order, and whether the ---/+++ names carry git's a/ b/ prefixes."""
    paths: list[str] = []
    prefixed = True
    for line in patch.splitlines():
        anchored = patch_format.header_path(line)
        if anchored is not None:
            if anchored not in paths:
                paths.append(anchored)
            continue
        if not line.startswith(("--- ", "+++ ")):
            continue
        name = line[4:].split("\t", 1)[0].strip()
        if name == "/dev/null":
            continue
        if name.startswith(("a/", "b/")):
            name = name[2:]
        else:
            prefixed = False
        if name not in paths:
            paths.append(name)
    return paths, prefixed


class ToolBox:
    """Runs tool calls for one arm. Paths are checked on the host; commands run in the sandbox."""

    def __init__(
        self,
        workspace: Path,
        sandbox: Sandbox,
        bus: EventBus | None,
        run_id: str,
        arm: Arm,
        *,
        guard: Callable[[ToolCall], HarnessDecision] | None = None,
        tool_log_dir: Path | None = None,
        tool_timeout_s: int = 120,
        search_time_budget_s: float = SEARCH_TIME_BUDGET_S,
        visible_tests_dir: str = TEAMTRACK_VISIBLE_TESTS,
    ) -> None:
        self.workspace = Path(workspace)
        self.sandbox = sandbox
        self.bus = bus
        self.run_id = run_id
        self.arm = arm
        self.guard = guard
        self.tool_log_dir = (
            Path(tool_log_dir) if tool_log_dir else self.workspace.parent / "tool-logs"
        )
        root = self.workspace.resolve()
        log_dir = self.tool_log_dir.resolve()
        if log_dir == root or root in log_dir.parents:
            raise ValueError("tool_log_dir must be outside the workspace (the agent can edit it)")
        self.tool_timeout_s = tool_timeout_s
        self.search_time_budget_s = search_time_budget_s
        self.visible_tests_dir = checked_tests_dir(visible_tests_dir)
        self._selector = selector_pattern(self.visible_tests_dir)

    # -- public ------------------------------------------------------------------------------

    def execute(self, call: ToolCall) -> ToolResult:
        started = time.monotonic()
        model = ARG_MODELS.get(call.name)
        if model is None:
            return self._result(call, False, f"unknown tool: {call.name!r}", started)
        try:
            args = model.model_validate(call.arguments)
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
            )
            return self._result(
                call, False, f"invalid arguments for {call.name}: {problems}", started
            )
        if self.guard is not None and call.name != "finish":
            decision = self.guard(call)
            if decision.kind == "block":
                return self._result(call, False, f"BLOCKED: {decision.message}", started)
        try:
            handler = getattr(self, f"_tool_{call.name}")
            ok, output, exit_code, changed = handler(call, args)
        except PathOutsideWorkspace as exc:
            self._deny(call, str(exc))
            return self._result(call, False, str(exc), started)
        except Exception as exc:  # noqa: BLE001 - a tool failure is a result the agent sees
            return self._result(call, False, f"tool error: {type(exc).__name__}: {exc}", started)
        return self._result(call, ok, output, started, exit_code=exit_code, files_changed=changed)

    # -- tools --------------------------------------------------------------------------------

    def _tool_list_dir(self, _call: ToolCall, a: ListDirArgs) -> tuple[bool, str, None, list[str]]:
        root = resolve_in_workspace(self.workspace, a.path)
        if not root.is_dir():
            return False, f"not a directory: {a.path}", None, []
        depth = max(1, min(a.depth or 1, 3))
        base = self.workspace.resolve()
        entries: list[str] = []

        def walk(folder: Path, level: int) -> None:
            for item in sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name)):
                if item.name in SKIP_DIRS or len(entries) >= 500:
                    continue
                rel = item.relative_to(base).as_posix()
                if _is_link(item):
                    entries.append(f"{rel}@ (link, not followed)")
                    continue
                entries.append(rel + "/" if item.is_dir() else rel)
                if item.is_dir() and level < depth:
                    walk(item, level + 1)

        walk(root, 1)
        return True, "\n".join(entries) or "(empty)", None, []

    def _tool_read_file(
        self, _call: ToolCall, a: ReadFileArgs
    ) -> tuple[bool, str, None, list[str]]:
        path = resolve_in_workspace(self.workspace, a.path)
        if not path.is_file():
            return False, f"file not found: {a.path}", None, []
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            return (
                False,
                f"file too large to read: {a.path} is {size} bytes (limit {MAX_FILE_BYTES}); "
                "use run with grep, head, or tail to see the part you need",
                None,
                [],
            )
        lines = path.read_bytes().decode("utf-8", errors="replace").splitlines()
        start = max(1, a.start_line or 1)
        count = max(1, min(a.max_lines or 400, 2000))
        chosen = lines[start - 1 : start - 1 + count]
        end = start + len(chosen) - 1
        header = f"[lines {start}-{max(end, start)} of {len(lines)}] {a.path}"
        body = "\n".join(f"{n:>4}  {_cap_line(text)}" for n, text in enumerate(chosen, start=start))
        return True, header + ("\n" + body if body else ""), None, []

    def _tool_search(self, _call: ToolCall, a: SearchArgs) -> tuple[bool, str, None, list[str]]:
        try:
            regex = re.compile(a.pattern)
        except re.error as exc:
            return False, f"invalid pattern: {exc}", None, []
        root = resolve_in_workspace(self.workspace, a.path or ".")
        limit = max(1, min(a.max_results or 50, 200))
        base = self.workspace.resolve()
        rows: list[str] = []
        skipped = 0
        stopped = False
        started = time.monotonic()
        for file in iter_workspace_files(root):
            if time.monotonic() - started >= self.search_time_budget_s:
                stopped = True
                break
            if file.stat().st_size > MAX_FILE_BYTES:
                skipped += 1
                continue
            text = file.read_bytes().decode("utf-8", errors="ignore")
            for number, line in enumerate(text.splitlines(), start=1):
                if regex.search(line[:MAX_LINE_CHARS]):
                    rows.append(
                        f"{file.relative_to(base).as_posix()}:{number}: {line.strip()[:200]}"
                    )
                    if len(rows) >= limit:
                        return True, "\n".join(rows), None, []
        notes = []
        if skipped:
            notes.append(f"[skipped {skipped} file over {MAX_FILE_BYTES} bytes]")
        if stopped:
            notes.append(
                f"[search stopped: time budget of {self.search_time_budget_s:g} s reached; "
                "narrow the path or the pattern]"
            )
        return True, "\n".join([*rows, *notes]) or "(no matches)", None, []

    def _tool_apply_patch(
        self, call: ToolCall, a: ApplyPatchArgs
    ) -> tuple[bool, str, int | None, list[str]]:
        paths, prefixed = patch_paths(a.patch)
        if not paths:
            return (
                False,
                "patch names no files (expected '*** Update File: <path>' or ---/+++ headers)",
                None,
                [],
            )
        for rel in paths:
            resolve_in_workspace(self.workspace, rel)
        if workspace_git_dir(self.workspace) is None:
            return False, "the workspace .git is missing or is not a real directory", None, []
        text, strip = a.patch, "-p1" if prefixed else "-p0"
        if patch_format.needs_conversion(a.patch):
            try:
                text, strip = self._converted(a.patch), "-p1"
            except patch_format.PatchFormatError as exc:
                return False, f"patch not applied: {exc}", None, []
        before = self._snapshot()
        recount = False
        check = self._git_apply(text, strip, check=True)
        if check.exit_code != 0 and text is a.patch:
            # A unified diff with wrong line counts: let git recount them; failing that, locate
            # the hunks by their context lines.
            if self._git_apply(text, strip, check=True, recount=True).exit_code == 0:
                recount = True
            else:
                try:
                    text, strip = self._converted(a.patch), "-p1"
                except patch_format.PatchFormatError as exc:
                    output = f"patch does not apply:\n{check.output.strip()}\n{exc}"
                    return False, output, check.exit_code, []
            check = self._git_apply(text, strip, check=True, recount=recount)
        if check.exit_code != 0:
            return False, f"patch does not apply:\n{check.output.strip()}", check.exit_code, []
        applied = self._git_apply(text, strip, check=False, recount=recount)
        changed = self._changed_since(before)
        if applied.exit_code != 0:
            return (
                False,
                f"patch does not apply:\n{applied.output.strip()}",
                applied.exit_code,
                changed,
            )
        return True, "applied: " + ", ".join(changed or paths), 0, changed

    def _tool_run(self, _call: ToolCall, a: RunArgs) -> tuple[bool, str, int, list[str]]:
        timeout = max(1, min(a.timeout_s or self.tool_timeout_s, self.tool_timeout_s))
        before = self._snapshot()
        result = self.sandbox.exec(a.command, timeout)
        changed = self._changed_since(before)
        header = f"exit={result.exit_code}" + (" (timed out)" if result.timed_out else "")
        if result.denied is not None:
            header += f" DENIED {result.denied.reason_code}: {result.denied.detail}"
        return result.exit_code == 0, f"{header}\n{result.output}", result.exit_code, changed

    def _tool_run_visible_tests(
        self, _call: ToolCall, a: RunVisibleTestsArgs
    ) -> tuple[bool, str, int | None, list[str]]:
        where = self.visible_tests_dir
        if a.selector is not None and not self._selector.match(a.selector):
            return False, f"selector must be a pytest node inside {where}", None, []
        command = f"python -m pytest {where} -q -rfE --no-header -p no:cacheprovider"
        if a.selector:
            command += f" {a.selector}"
        result = self.sandbox.exec(command, self.tool_timeout_s)
        return result.exit_code == 0, summarise_pytest(result.output), result.exit_code, []

    def _tool_finish(self, _call: ToolCall, _a: FinishArgs) -> tuple[bool, str, None, list[str]]:
        return True, "accepted", None, []

    # -- helpers ------------------------------------------------------------------------------

    def _git_apply(self, text: str, strip: str, *, check: bool, recount: bool = False) -> Any:
        """`git apply` in the sandbox. `--recount` (hunk counts not trusted) is only for the
        agent's own unified diffs: git mishandles new and deleted files with it."""
        patch_file = self.workspace / PATCH_FILE
        patch_file.parent.mkdir(parents=True, exist_ok=True)
        patch_file.write_text(
            text if text.endswith("\n") else text + "\n", encoding="utf-8", newline="\n"
        )
        mode = ("--check " if check else "") + ("--recount " if recount else "")
        try:
            return self.sandbox.exec(
                f"git apply {mode}{strip} --whitespace=nowarn {PATCH_FILE}",
                self.tool_timeout_s,
            )
        finally:
            patch_file.unlink(missing_ok=True)

    def _converted(self, patch: str) -> str:
        return patch_format.to_unified(patch_format.parse(patch), self._read_text)

    def _read_text(self, rel: str) -> str | None:
        """A workspace file's text for patch conversion (host read, links refused)."""
        path = resolve_in_workspace(self.workspace, rel)
        if not path.exists():
            return None
        if not path.is_file():
            raise patch_format.PatchFormatError(f"{rel} is not a regular file")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise patch_format.PatchFormatError(f"{rel} is over {MAX_FILE_BYTES} bytes")
        try:
            return path.read_bytes().decode("utf-8")
        except UnicodeDecodeError as exc:
            raise patch_format.PatchFormatError(f"{rel} is not UTF-8 text") from exc

    def _snapshot(self) -> dict[str, str]:
        """Content hash of every workspace file. No git process: the agent controls .git/config,
        and host git would run commands configured there (core.fsmonitor, filters)."""
        snapshot: dict[str, str] = {}
        for path in iter_workspace_files(self.workspace):
            if path.suffix == ".pyc":
                continue
            rel = path.relative_to(self.workspace).as_posix()
            try:
                stat = path.stat()
                snapshot[rel] = (
                    f"size:{stat.st_size}:mtime:{stat.st_mtime_ns}"
                    if stat.st_size > 5_000_000
                    else hashlib.sha1(path.read_bytes()).hexdigest()
                )
            except OSError:
                snapshot[rel] = "unreadable"
        return snapshot

    def _changed_since(self, before: dict[str, str]) -> list[str]:
        after = self._snapshot()
        return sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))

    def _deny(self, call: ToolCall, detail: str) -> None:
        if self.bus is None:
            return
        self.bus.publish(
            "sandbox_denied",
            {
                "command": f"{call.name} {call.arguments.get('path', '')}"[:500],
                "reason_code": "path_outside_workspace",
                "detail": detail,
            },
            run_id=self.run_id,
            arm=self.arm,
        )

    def _result(
        self,
        call: ToolCall,
        ok: bool,
        output: str,
        started: float,
        *,
        exit_code: int | None = None,
        files_changed: list[str] | None = None,
    ) -> ToolResult:
        output = mask_keys(output)
        text, cut = truncate(output)
        full_path: str | None = None
        if cut:
            self.tool_log_dir.mkdir(parents=True, exist_ok=True)
            safe_id = _SAFE_ID.sub("_", call.call_id)[:80] or "call"
            full = self.tool_log_dir / f"{safe_id}.txt"
            full.write_text(output, encoding="utf-8")
            full_path = str(full)
            text += f"\n[truncated: {len(output) - len(text)} more chars; {TRUNCATION_ADVICE}]"
        return ToolResult(
            call_id=call.call_id,
            ok=ok,
            output=text,
            full_output_path=full_path,
            exit_code=exit_code,
            duration_ms=int((time.monotonic() - started) * 1000),
            files_changed=files_changed or [],
        )


def summarise_pytest(output: str) -> str:
    """First line `passed=x failed=y errors=z`, then one grep-friendly line per failure."""
    counts = {"passed": 0, "failed": 0, "errors": 0}
    failures: list[str] = []
    summary_found = False
    for line in output.splitlines():
        match = _FAILURE_LINE.match(line.strip())
        if match:
            kind, node, reason = match.groups()
            failures.append(f"{kind} {node}: {reason or 'no message'}")
        if re.search(r"\d+ (passed|failed|errors?)\b.* in [\d.]+s", line):
            summary_found = True
            for number, word in _SUMMARY_COUNT.findall(line):
                counts["errors" if word.startswith("error") else word] = int(number)
    head = f"passed={counts['passed']} failed={counts['failed']} errors={counts['errors']}"
    if not summary_found:
        return head + "\n(no pytest summary found; raw output follows)\n" + output
    return "\n".join([head, *failures])
