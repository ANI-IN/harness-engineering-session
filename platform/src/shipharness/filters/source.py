"""Which workspace files are tests and which are source, and source fingerprints (filter 5)."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import Literal

from shipharness.filters.scratch import is_scratch
from shipharness.runner.tools import iter_workspace_files

SOURCE_SUFFIXES = frozenset(
    {".py", ".pyi", ".ini", ".toml", ".cfg", ".html", ".js", ".css", ".sql", ".mako"}
)
TEST_DIRS = frozenset({"tests", "test"})
ChangeKind = Literal["added", "modified", "deleted"]


def is_test_path(rel: str) -> bool:
    """Files that belong to the test suite: under a tests/ directory, test_*.py, *_test.py,
    or conftest.py."""
    path = PurePosixPath(rel)
    if TEST_DIRS & set(path.parts[:-1]):
        return True
    name = path.name
    return (
        name == "conftest.py"
        or (name.startswith("test_") and name.endswith(".py"))
        or name.endswith("_test.py")
    )


def is_source_path(rel: str) -> bool:
    return (
        PurePosixPath(rel).suffix in SOURCE_SUFFIXES
        and not is_test_path(rel)
        and not is_scratch(rel)
    )


def source_shas(workspace: Path) -> dict[str, str]:
    """sha256 of every source file in the workspace (links are never followed)."""
    root = Path(workspace)
    shas: dict[str, str] = {}
    for path in iter_workspace_files(root):
        rel = path.relative_to(root).as_posix()
        if is_source_path(rel):
            shas[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return shas


def changed_sources(before: dict[str, str], workspace: Path) -> list[tuple[str, ChangeKind]]:
    after = source_shas(workspace)
    changes: list[tuple[str, ChangeKind]] = []
    for rel in sorted(set(before) | set(after)):
        if rel not in after:
            changes.append((rel, "deleted"))
        elif rel not in before:
            changes.append((rel, "added"))
        elif before[rel] != after[rel]:
            changes.append((rel, "modified"))
    return changes
