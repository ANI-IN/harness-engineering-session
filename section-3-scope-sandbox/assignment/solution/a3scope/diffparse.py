"""Part A1 (reference solution): parse a diff into file changes.

Two section shapes are read:
- git sections, from one `diff --git` line to the next, with paths taken (in this order) from
  `rename/copy from/to`, the `---`/`+++` lines, and finally the header itself;
- plain unified sections: a `---` line followed by a `+++` line, outside any hunk.
Hunks are skipped by counting their lines (`@@ -a,b +c,d @@`), so content lines that look
like `---`/`+++` headers are never read as headers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Status = Literal["added", "deleted", "modified", "renamed", "copied"]

DEV_NULL = "/dev/null"
_HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")
_ESCAPES = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13, '"': 34, "\\": 92}


class DiffParseError(ValueError):
    """The diff has content but no file whose paths can be determined."""


@dataclass(frozen=True)
class FileChange:
    old_path: str | None  # None for an added file
    new_path: str | None  # None for a deleted file
    status: Status
    binary: bool = False


def _unquote(token: str) -> str:
    """Undo git's C-style quoting: "a/caf\\303\\251.md" -> a/café.md (octal escapes are bytes)."""
    body, out, i = token[1:-1], bytearray(), 0
    while i < len(body):
        char = body[i]
        if char != "\\":
            out += char.encode("utf-8")
            i += 1
            continue
        nxt = body[i + 1 : i + 2]
        if nxt in _ESCAPES:
            out.append(_ESCAPES[nxt])
            i += 2
        elif re.fullmatch(r"[0-7]", nxt):
            digits = re.match(r"[0-7]{1,3}", body[i + 1 :])
            assert digits is not None
            out.append(int(digits.group(0), 8) & 0xFF)
            i += 1 + len(digits.group(0))
        else:
            raise DiffParseError(f"bad escape in quoted name {token!r}")
    return out.decode("utf-8", errors="replace")


def _quoted_end(text: str, start: int) -> int:
    """Index just past the closing quote of the quoted token starting at `start`."""
    i = start + 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == '"':
            return i + 1
        i += 1
    raise DiffParseError(f"unterminated quoted name in {text!r}")


def _normalise(path: str) -> str:
    while path.startswith("./"):
        path = path[2:]
    return path


def _name(raw: str) -> str:
    """A name from a ---/+++/rename/copy line: quoted, or up to the first tab."""
    if raw.startswith('"'):
        return _unquote(raw[: _quoted_end(raw, 0)])
    return raw.split("\t", 1)[0]


def _header_names(rest: str) -> tuple[str, str] | None:
    """The two names on a `diff --git` line (still prefixed), or None if ambiguous.

    Git quotes names with special characters but not names with spaces, so an unquoted
    `a/X b/X` is split where both halves are equal, or at the only " b/" if there is one.
    """
    if rest.startswith('"'):
        end = _quoted_end(rest, 0)
        first, second = _unquote(rest[:end]), rest[end + 1 :]
        return first, _unquote(second) if second.startswith('"') else second
    if rest.endswith('"'):
        start = rest.rfind(' "')
        if start < 0:
            return None
        return rest[:start], _unquote(rest[start + 1 :])
    candidates = [m.start() for m in re.finditer(r" (?=b/)", rest)]
    for index in candidates:
        if rest[:index][2:] == rest[index + 1 :][2:]:
            return rest[:index], rest[index + 1 :]
    if len(candidates) == 1:
        return rest[: candidates[0]], rest[candidates[0] + 1 :]
    return None


def _strip(name: str, prefix: str, prefixed: bool) -> str:
    if name == DEV_NULL:
        return name
    if prefixed and name.startswith(prefix):
        name = name[len(prefix) :]
    return _normalise(name)


def _skip_hunk(lines: list[str], i: int) -> int:
    """Index of the first line after the hunk whose header is lines[i]."""
    match = _HUNK.match(lines[i])
    if match is None:
        raise DiffParseError(f"bad hunk header {lines[i]!r}")
    old_left = int(match.group(1)) if match.group(1) is not None else 1
    new_left = int(match.group(2)) if match.group(2) is not None else 1
    i += 1
    while i < len(lines) and (old_left > 0 or new_left > 0):
        line = lines[i]
        tag = line[:1]
        if tag == "\\":
            pass  # "\ No newline at end of file"
        elif tag == " " or line == "":
            old_left, new_left = old_left - 1, new_left - 1
        elif tag == "-":
            old_left -= 1
        elif tag == "+":
            new_left -= 1
        else:
            break  # a short hunk: stop at the first line that cannot belong to it
        i += 1
    while i < len(lines) and lines[i].startswith("\\"):
        i += 1
    return i


def _change(old: str, new: str, binary: bool, copied: bool = False) -> FileChange:
    if old == DEV_NULL and new == DEV_NULL:
        raise DiffParseError("a file section with /dev/null on both sides")
    if old == DEV_NULL:
        return FileChange(None, new, "added", binary)
    if new == DEV_NULL:
        return FileChange(old, None, "deleted", binary)
    if copied:
        return FileChange(old, new, "copied", binary)
    return FileChange(old, new, "modified" if old == new else "renamed", binary)


def _git_section(lines: list[str], i: int) -> tuple[FileChange, int]:
    header = _header_names(lines[i][len("diff --git ") :])
    prefixed = header is not None and header[0].startswith("a/") and header[1].startswith("b/")
    found: dict[str, str] = {}
    added = deleted = binary = False
    i += 1
    while i < len(lines) and not lines[i].startswith("diff --git "):
        line = lines[i]
        if binary and found.get("binary_patch"):
            i += 1  # base85 data of a GIT binary patch
            continue
        if line.startswith("@@"):
            i = _skip_hunk(lines, i)
            continue
        for key in ("rename from ", "rename to ", "copy from ", "copy to "):
            if line.startswith(key):
                found[key.strip()] = _normalise(_name(line[len(key) :]))
        if line.startswith("--- "):
            found["old"] = _strip(_name(line[4:]), "a/", prefixed)
        elif line.startswith("+++ "):
            found["new"] = _strip(_name(line[4:]), "b/", prefixed)
        elif line.startswith("new file mode"):
            added = True
        elif line.startswith("deleted file mode"):
            deleted = True
        elif line.startswith("Binary files "):
            binary = True
        elif line == "GIT binary patch":
            binary = True
            found["binary_patch"] = "1"
        i += 1
    if "rename from" in found and "rename to" in found:
        return FileChange(found["rename from"], found["rename to"], "renamed", binary), i
    if "copy from" in found and "copy to" in found:
        return _change(found["copy from"], found["copy to"], binary, copied=True), i
    if "old" in found and "new" in found:
        return _change(found["old"], found["new"], binary), i
    if header is None:
        raise DiffParseError(f"cannot read the paths of {lines[i - 1]!r}")
    old, new = _strip(header[0], "a/", prefixed), _strip(header[1], "b/", prefixed)
    if added:
        old = DEV_NULL
    elif deleted:
        new = DEV_NULL
    return _change(old, new, binary), i


def _plain_section(lines: list[str], i: int) -> tuple[FileChange, int]:
    old, new = _name(lines[i][4:]), _name(lines[i + 1][4:])
    prefixed = (old == DEV_NULL or old.startswith("a/")) and (
        new == DEV_NULL or new.startswith("b/")
    )
    i += 2
    while i < len(lines) and lines[i].startswith(("@@", "\\")):
        i = _skip_hunk(lines, i) if lines[i].startswith("@@") else i + 1
    return _change(_strip(old, "a/", prefixed), _strip(new, "b/", prefixed), False), i


def parse_diff(diff: str | bytes) -> list[FileChange]:
    """One FileChange per file section, in diff order. An empty diff gives []."""
    text = diff.decode("utf-8", errors="replace") if isinstance(diff, bytes) else diff
    if not text.strip():
        return []
    lines = re.split(r"\r?\n", text)  # not splitlines(): \x0c and friends are content
    changes: list[FileChange] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("diff --git "):
            change, i = _git_section(lines, i)
            changes.append(change)
        elif line.startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
            change, i = _plain_section(lines, i)
            changes.append(change)
        else:
            i += 1  # preamble (commit message, stat lines) or a stray line
    if not changes:
        raise DiffParseError("no file section found")
    return changes


def changed_paths(changes: list[FileChange]) -> list[str]:
    """Paths whose content or existence the diff changes, in diff order, without duplicates."""
    out: list[str] = []
    for change in changes:
        if change.status == "renamed":
            paths = [change.old_path, change.new_path]
        elif change.status == "deleted":
            paths = [change.old_path]
        else:  # added, modified, copied: the new side
            paths = [change.new_path]
        for path in paths:
            if path is not None and path not in out:
                out.append(path)
    return out
