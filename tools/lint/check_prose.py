#!/usr/bin/env python3
"""Prose checker: punctuation and roadmap language.

Two rules over markdown prose in every shipped .md file (mermaid node
labels included; fenced code, inline code, link targets, and anything
under fixtures/ or expected/ exempt):

1. No em-dashes (U+2014) or en-dashes (U+2013). Rewrite with a comma, a
   normal hyphen, a colon, or a full stop.
2. No roadmap language. Committed prose describes what exists; promises
   rot the moment priorities move, which is how the reference course
   accumulated announcements for content that never arrived, and this
   repository shipped the same phrasing twice before this became a gate.
   Banned (case-insensitive): "next release", "coming soon",
   "will be added", "in a future", "not yet built". Name what exists and
   link to it, or say nothing.
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
# This repository is one module, not a course. A course is a sequence of
# modules, and calling this a course misstates its scope to an audience
# deciding how much time it needs. The only correct use of the word is a
# reference to the external reference course this module was modeled on,
# which is why the exception is a phrase rather than a file list.
COURSE_EXCEPTIONS = ("reference course",)
# The glossary entry that defines the distinction has to use both words.
COURSE_DEFINITION_FILE = "docs/glossary.md"
COURSE_DEFINITION_MARKER = "**Module**:"

ROADMAP_PHRASES = (
    "next release", "coming soon", "will be added", "in a future", "not yet built",
)
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
    in_module_definition = False
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
        rel = path.relative_to(root) if path.is_relative_to(root) else path
        for char, name in BANNED.items():
            column = candidate.find(char)
            if column != -1:
                errors.append(f"{rel}:{number}:{column + 1}: {name} in prose")
        if str(rel) == COURSE_DEFINITION_FILE:
            if candidate.startswith(COURSE_DEFINITION_MARKER):
                in_module_definition = True
            elif not candidate.strip():
                in_module_definition = False
        lowered = candidate.lower()
        scrubbed = lowered
        for allowed in COURSE_EXCEPTIONS:
            scrubbed = scrubbed.replace(allowed, "")
        column = scrubbed.find("course")
        if column != -1 and not in_module_definition:
            errors.append(
                f"{rel}:{number}:{column + 1}: this is a module, not a course; "
                f"a course is a sequence of modules"
            )
        for phrase in ROADMAP_PHRASES:
            column = lowered.find(phrase)
            if column != -1:
                errors.append(
                    f"{rel}:{number}:{column + 1}: roadmap language ({phrase!r}); "
                    "describe what exists instead of promising what might"
                )
    return errors


def check_tree(root: Path) -> list[str]:
    errors = []
    for path in markdown_files(root):
        errors.extend(check_file(path, root))
    return errors


def main() -> int:
    files = markdown_files(REPO_ROOT)
    errors = check_tree(REPO_ROOT)
    print(
        f"lint-prose: {len(files)} markdown files scanned for em/en dashes "
        "and roadmap language"
    )
    for error in errors:
        print(f"  FAIL {error}")
    if errors:
        print(f"lint-prose: {len(errors)} error(s)")
        return 1
    print("lint-prose: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
