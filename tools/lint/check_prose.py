#!/usr/bin/env python3
"""Prose punctuation checker: no em-dashes (U+2014) or en-dashes (U+2013).

Applies to markdown prose in every shipped .md file, including the text of
mermaid node labels. Does NOT apply to: fenced code blocks (other than
mermaid), inline code spans, link targets/URLs, or anything under a
fixtures/ or expected/ directory (expected output is the grading authority
and is never edited for style).

Rewrite the sentence with a comma, a normal hyphen (hyphen-minus, ASCII 45),
a colon, or a full stop. A hyphen doing an em-dash's job usually reads worse
than a comma, so prefer restructuring.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {"node_modules", "_reference", ".git", ".venv", "__pycache__", "dist"}
SKIP_FILES = {"RESEARCH.md", "PROPOSAL.md", "BUILD_PROGRESS.md"}
EXEMPT_DIRS = {"fixtures", "expected"}

BANNED = {"—": "em-dash (U+2014)", "–": "en-dash (U+2013)"}
INLINE_CODE_RE = re.compile(r"`[^`]*`")
LINK_TARGET_RE = re.compile(r"\]\([^)]*\)")
FENCE_RE = re.compile(r"^\s*(```|~~~)\s*(\S*)")


def markdown_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*.md"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if any(part in EXEMPT_DIRS for part in path.parts):
            continue
        if path.name in SKIP_FILES and path.parent == root:
            continue
        files.append(path)
    return sorted(files)


def check_file(path: Path, root: Path) -> list[str]:
    errors = []
    in_fence = False
    fence_is_mermaid = False
    for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        fence = FENCE_RE.match(line)
        if fence:
            if not in_fence:
                in_fence = True
                fence_is_mermaid = fence.group(2) == "mermaid"
            else:
                in_fence = False
                fence_is_mermaid = False
            continue
        if in_fence and not fence_is_mermaid:
            continue  # code fences are exempt; mermaid labels are prose

        candidate = line
        if not in_fence:
            candidate = INLINE_CODE_RE.sub("", candidate)
            candidate = LINK_TARGET_RE.sub("]", candidate)
        for char, name in BANNED.items():
            column = candidate.find(char)
            if column != -1:
                rel = path.relative_to(root) if path.is_relative_to(root) else path
                errors.append(f"{rel}:{number}:{column + 1}: {name} in prose")
    return errors


def check_tree(root: Path) -> list[str]:
    errors = []
    for path in markdown_files(root):
        errors.extend(check_file(path, root))
    return errors


def main() -> int:
    files = markdown_files(REPO_ROOT)
    errors = check_tree(REPO_ROOT)
    print(f"lint-prose: {len(files)} markdown files scanned for em/en dashes")
    for error in errors:
        print(f"  FAIL {error}")
    if errors:
        print(f"lint-prose: {len(errors)} error(s)")
        return 1
    print("lint-prose: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
