"""Patch shapes the apply_patch tool accepts, turned into exact unified diffs.

Models write two shapes: git's unified diff, and the context-anchored format OpenAI documents for
its models (`*** Begin Patch`, `*** Add File:`, `*** Update File:`, `*** Delete File:`,
`*** Move to:`, with `@@` hunks located by their context lines instead of line numbers). Hunks
without line numbers, or with wrong counts, are common in both (M6 pilot: about 80% of patches
failed under a strict `git apply`).

`to_unified` locates every hunk by its context in the current file and writes an exact unified
diff, which the tool then applies with `git apply` inside the sandbox as before. This module only
reads workspace files, through the caller's `read` function.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

BEGIN = "*** Begin Patch"
END = "*** End Patch"
UPDATE = "*** Update File: "
ADD = "*** Add File: "
DELETE = "*** Delete File: "
MOVE = "*** Move to: "
END_OF_FILE = "*** End of File"
HEADERS = (UPDATE, ADD, DELETE, MOVE)
_RANGE = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")
_GIT_META = ("diff --git ", "index ", "new file mode ", "deleted file mode ", "similarity ")
NO_NEWLINE = "\\ No newline at end of file"


class PatchFormatError(ValueError):
    """The patch cannot be read, or a hunk does not match the file."""


@dataclass
class Hunk:
    anchor: str = ""
    ops: list[tuple[str, str]] = field(default_factory=list)  # (" " | "-" | "+", line text)
    at_eof: bool = False

    def old(self) -> list[str]:
        return [text for op, text in self.ops if op != "+"]

    def new(self) -> list[str]:
        return [text for op, text in self.ops if op != "-"]

    def trimmed(self) -> Hunk:
        """The hunk without blank context lines at either end (models add or drop them)."""
        ops = list(self.ops)
        while ops and ops[0] == (" ", ""):
            ops.pop(0)
        while ops and ops[-1] == (" ", ""):
            ops.pop()
        return Hunk(self.anchor, ops, self.at_eof)


@dataclass
class FileChange:
    kind: Literal["add", "delete", "update"]
    path: str
    move_to: str | None = None
    hunks: list[Hunk] = field(default_factory=list)
    added: list[str] = field(default_factory=list)


def header_path(line: str) -> str | None:
    """The path an anchored header line names, or None for any other line."""
    for header in HEADERS:
        if line.startswith(header):
            return line[len(header) :].strip() or None
    return None


def needs_conversion(patch: str) -> bool:
    """True for the anchored format and for unified hunks without line numbers."""
    for line in patch.splitlines():
        if line.strip() == BEGIN or line.startswith(HEADERS):
            return True
        if line.startswith("@@") and not _RANGE.match(line):
            return True
    return False


def _strip_prefix(name: str) -> str:
    name = name.split("\t", 1)[0].strip()
    return name[2:] if name.startswith(("a/", "b/")) else name


def parse(patch: str) -> list[FileChange]:
    lines = patch.splitlines()
    changes: list[FileChange] = []
    current: FileChange | None = None
    hunk: Hunk | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        stripped = line.strip()
        if stripped in (BEGIN, END):
            hunk = None
            continue
        if line.startswith((UPDATE, ADD, DELETE)):
            name = line.split(": ", 1)[1].strip()
            kind: Literal["add", "delete", "update"] = (
                "update" if line.startswith(UPDATE) else "add" if line.startswith(ADD) else "delete"
            )
            current, hunk = FileChange(kind, name), None
            changes.append(current)
            continue
        if line.startswith(MOVE):
            if current is None or current.kind != "update":
                raise PatchFormatError("'*** Move to:' must follow '*** Update File:'")
            current.move_to = line[len(MOVE) :].strip()
            continue
        if line.startswith("--- ") and i < len(lines) and lines[i].startswith("+++ "):
            old_name, new_name = _strip_prefix(line[4:]), _strip_prefix(lines[i][4:])
            i += 1
            hunk = None
            if old_name == "/dev/null":
                current = FileChange("add", new_name)
            elif new_name == "/dev/null":
                current = FileChange("delete", old_name)
            elif current is not None and current.path == new_name and not current.hunks:
                continue  # unified headers repeated under an anchored header
            else:
                current = FileChange("update", new_name)
            changes.append(current)
            continue
        if line.startswith(_GIT_META):
            continue
        if line.startswith(END_OF_FILE):
            if hunk is not None:
                hunk.at_eof = True
            continue
        if current is None:
            if stripped:
                raise PatchFormatError(
                    f"line {i} is outside a file section: {line[:80]!r}; start each file with "
                    "'*** Update File: <path>' (or ---/+++ headers)"
                )
            continue
        if line.startswith("\\"):
            continue  # NO_NEWLINE: the file keeps its own ending
        if line.startswith("@@"):
            anchor = "" if _RANGE.match(line) else line[2:].strip()
            if anchor.endswith("@@"):
                anchor = anchor[:-2].strip()
            hunk = Hunk(anchor=anchor)
            current.hunks.append(hunk)
            continue
        if current.kind == "add":
            if line.startswith("+"):
                current.added.append(line[1:])
            elif stripped:
                raise PatchFormatError(f"{current.path}: lines of a new file start with '+'")
            continue
        if current.kind == "delete":
            continue  # a deleted file's old lines are not needed
        if hunk is None:
            hunk = Hunk()
            current.hunks.append(hunk)
        if line == "":
            hunk.ops.append((" ", ""))
        elif line[0] in " -+":
            hunk.ops.append((line[0], line[1:]))
        else:
            raise PatchFormatError(
                f"{current.path}: unexpected line {line[:80]!r}; hunk lines start with ' ', '-' "
                "or '+'"
            )
    if not changes:
        raise PatchFormatError("patch names no files")
    return changes


_LEVELS: tuple[Callable[[str], str], ...] = (lambda s: s, str.rstrip, str.strip)


def _find(lines: list[str], block: list[str], start: int, at_eof: bool) -> int | None:
    """First index at or after `start` where `block` matches: exactly, then ignoring trailing
    whitespace, then ignoring surrounding whitespace. `at_eof` tries the end of the file first."""
    last = len(lines) - len(block)
    if not block or last < 0:
        return None
    for norm in _LEVELS:
        wanted = [norm(b) for b in block]
        candidates = ([last] if at_eof else []) + list(range(max(start, 0), last + 1))
        for idx in candidates:
            if [norm(x) for x in lines[idx : idx + len(block)]] == wanted:
                return idx
    return None


def _find_anchor(lines: list[str], anchor: str, start: int) -> int | None:
    for idx in range(start, len(lines)):
        if lines[idx].strip() == anchor.strip():
            return idx
    return None


def apply_hunks(path: str, text: str, hunks: list[Hunk]) -> str:
    ends_with_newline = text.endswith("\n")
    lines = text.split("\n") if text else []
    if ends_with_newline:
        lines.pop()
    pos = 0
    for number, original in enumerate(hunks, 1):
        start, anchored = pos, False
        if original.anchor:
            found = _find_anchor(lines, original.anchor, pos)
            if found is None:
                found = _find_anchor(lines, original.anchor, 0)
            if found is not None:
                start, anchored = found, True
        if not original.trimmed().old():
            # Pure insertion: after the anchor line when there is one, else at the end.
            new = original.trimmed().new()
            idx = start + 1 if anchored else len(lines)
            lines[idx:idx] = new
            pos = idx + len(new)
            continue
        idx: int | None = None
        hunk = original
        for candidate in (original, original.trimmed()):
            idx = _find(lines, candidate.old(), start, candidate.at_eof)
            if idx is None and start > 0:
                idx = _find(lines, candidate.old(), 0, candidate.at_eof)
            if idx is not None:
                hunk = candidate
                break
        if idx is None:
            shown = "\n".join(original.trimmed().old()[:6])
            raise PatchFormatError(
                f"{path}: hunk {number} not found in the file; these lines were not found:\n"
                f"{shown}\nRead the file again and copy the unchanged lines exactly."
            )
        lines[idx : idx + len(hunk.old())] = hunk.new()
        pos = idx + len(hunk.new())
    if not lines:
        return ""
    return "\n".join(lines) + ("\n" if ends_with_newline or not text else "")


def _unified(path: str, old: str | None, new: str | None) -> str:
    """Traditional ---/+++ diff; only an empty file being added or deleted needs git's extended
    header."""
    if old is None and not new:
        return f"diff --git a/{path} b/{path}\nnew file mode 100644\n"
    if new is None and not old:
        return f"diff --git a/{path} b/{path}\ndeleted file mode 100644\n"
    body = difflib.unified_diff(
        (old or "").splitlines(keepends=True),
        (new or "").splitlines(keepends=True),
        "/dev/null" if old is None else f"a/{path}",
        "/dev/null" if new is None else f"b/{path}",
    )
    return "".join(line if line.endswith("\n") else f"{line}\n{NO_NEWLINE}\n" for line in body)


def to_unified(changes: list[FileChange], read: Callable[[str], str | None]) -> str:
    """An exact unified diff (git a/ b/ prefixes) for `changes` against the current files.
    `read(path)` returns the file's text, or None when it does not exist."""
    parts: list[str] = []
    for change in changes:
        current = read(change.path)
        if change.kind == "add":
            if current is not None:
                raise PatchFormatError(
                    f"{change.path} already exists; use '*** Update File:' to change it"
                )
            text = "\n".join(change.added) + "\n" if change.added else ""
            parts.append(_unified(change.path, None, text))
            continue
        if current is None:
            raise PatchFormatError(
                f"{change.path} does not exist; use '*** Add File:' to create a file"
            )
        if change.kind == "delete":
            parts.append(_unified(change.path, current, None))
            continue
        updated = apply_hunks(change.path, current, change.hunks)
        if change.move_to and change.move_to != change.path:
            if read(change.move_to) is not None:
                raise PatchFormatError(f"cannot move {change.path}: {change.move_to} exists")
            parts.append(_unified(change.path, current, None))
            parts.append(_unified(change.move_to, None, updated))
            continue
        if updated == current:
            raise PatchFormatError(f"the patch makes no change to {change.path}")
        parts.append(_unified(change.path, current, updated))
    return "".join(parts)
