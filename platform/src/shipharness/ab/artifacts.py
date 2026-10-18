"""Harness-owned workspace files (contract I-6) and diff filtering.

The layers place these files in `prepare_workspace`, and the agent may update the state files
(progress.md, session-handoff.md, exec plans) while it works. They are never product changes: the
referee strips them before applying an arm's diff, the blinded reviewer never sees them, and the
diff-scope check does not count them as out-of-scope files. The same list applies to both arms.
"""

from __future__ import annotations

import fnmatch
import re
from typing import overload

HARNESS_ARTIFACT_PATTERNS: tuple[str, ...] = (
    # instructions layer
    "AGENTS.md",
    "ARCHITECTURE.md",
    "docs/SECURITY.md",
    "docs/RELIABILITY.md",
    "docs/QUALITY_SCORE.md",
    "docs/PLANS.md",
    "docs/design-docs/**",
    "docs/product-specs/**",
    "docs/references/**",
    ".agents/skills/**",
    # state layer
    "init.sh",
    "progress.md",
    "session-handoff.md",
    "docs/exec-plans/**",
    # scope layer
    "feature_list.json",
    "feature_list.schema.json",
)

_HEADER = re.compile(rb"^diff --git (\"(?:[^\"\\]|\\.)*\"|\S+) (\"(?:[^\"\\]|\\.)*\"|\S+)\s*$")


def glob_match(path: str, pattern: str) -> bool:
    """Segment-wise glob: `*` stays within one path segment; a trailing `**` matches the rest."""
    parts, pats = path.split("/"), pattern.split("/")
    if pats[-1] == "**":
        head = pats[:-1]
        return len(parts) > len(head) and all(
            fnmatch.fnmatchcase(p, q) for p, q in zip(parts, head, strict=False)
        )
    return len(parts) == len(pats) and all(
        fnmatch.fnmatchcase(p, q) for p, q in zip(parts, pats, strict=True)
    )


def is_harness_artifact(path: str) -> bool:
    clean = path.replace("\\", "/")
    while clean.startswith("./"):
        clean = clean[2:]
    return any(glob_match(clean, pattern) for pattern in HARNESS_ARTIFACT_PATTERNS)


def _unquote(token: bytes) -> str:
    text = token.decode("utf-8", errors="replace")
    if text.startswith('"') and text.endswith('"'):
        text = (
            text[1:-1]
            .encode("utf-8")
            .decode("unicode_escape")
            .encode("latin-1")
            .decode("utf-8", errors="replace")
        )
    return text[2:] if text[:2] in ("a/", "b/") else text


_GIT_HEADER = b"diff --git "
_BODY_PATHS = ((b"--- ", 0), (b"+++ ", 1), (b"rename from ", 0), (b"rename to ", 1))


def _header_paths(header: bytes) -> list[str]:
    """Paths from a `diff --git` line. Git quotes names with special characters but leaves
    spaces unquoted, so an unquoted `a/X b/X` header is split where both halves are equal."""
    match = _HEADER.match(header)
    if match:
        return [_unquote(match.group(1)), _unquote(match.group(2))]
    rest = header[len(_GIT_HEADER) :]
    if rest.startswith(b"a/"):
        for i in range(2, len(rest)):
            if rest[i : i + 3] == b" b/" and rest[2:i] == rest[i + 3 :]:
                name = rest[2:i].decode("utf-8", errors="replace")
                return [name, name]
    return []


def _body_paths(lines: list[bytes]) -> list[str]:
    """Old and new paths from the section's `---`/`+++` or `rename from/to` lines, if any."""
    found: list[str | None] = [None, None]
    for raw in lines[1:]:
        line = raw.rstrip(b"\r\n")
        if line.startswith((b"@@", b"GIT binary patch")):
            break
        for prefix, side in _BODY_PATHS:
            if line.startswith(prefix):
                token = line[len(prefix) :].rstrip(b"\t")  # git adds a tab after names with spaces
                if prefix.startswith(b"rename") and not token.startswith(b'"'):
                    found[side] = token.decode("utf-8", errors="replace")
                else:
                    found[side] = "/dev/null" if token == b"/dev/null" else _unquote(token)
    old, new = found
    if old is None or new is None:
        return []
    return [new if old == "/dev/null" else old, old if new == "/dev/null" else new]


def _sections(diff: bytes) -> list[tuple[list[str], bytes]]:
    """Split a git diff into (paths, section bytes). Text before the first header has no paths."""
    groups: list[tuple[bool, list[bytes]]] = []
    for line in diff.splitlines(keepends=True):
        if line.startswith(_GIT_HEADER):
            groups.append((True, [line]))
        elif groups:
            groups[-1][1].append(line)
        else:
            groups.append((False, [line]))
    out: list[tuple[list[str], bytes]] = []
    for is_section, lines in groups:
        paths: list[str] = []
        if is_section:
            paths = _body_paths(lines) or _header_paths(lines[0].rstrip(b"\r\n"))
        out.append((paths, b"".join(lines)))
    return out


@overload
def strip_harness_artifacts(diff: str) -> str: ...
@overload
def strip_harness_artifacts(diff: bytes) -> bytes: ...
def strip_harness_artifacts(diff: str | bytes) -> str | bytes:
    """Drop every file section whose old and new paths are both harness artifacts."""
    raw = diff.encode("utf-8") if isinstance(diff, str) else diff
    kept = [
        body
        for paths, body in _sections(raw)
        if not (paths and all(is_harness_artifact(p) for p in paths if p != "/dev/null"))
    ]
    joined = b"".join(kept)
    return joined.decode("utf-8") if isinstance(diff, str) else joined


def diff_paths(diff: str | bytes) -> list[str]:
    """The new-side path of every file section, in order."""
    raw = diff.encode("utf-8") if isinstance(diff, str) else diff
    return [paths[-1] for paths, _body in _sections(raw) if paths]
