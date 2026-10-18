"""Byte snapshots of the workspace, used to revert out-of-scope changes without git (I-7).

The workspace is untrusted: links are recorded by their target text and never followed, `.git` and
cache directories are skipped (`iter_workspace_files`), and restores refuse any path that leaves
the workspace or runs through a link.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from shipharness.runner.paths import PathOutsideWorkspace, resolve_in_workspace
from shipharness.runner.tools import SKIP_DIRS, _is_link, iter_workspace_files

MAX_RESTORE_BYTES = 5_000_000  # larger files are tracked by digest only


@dataclass(frozen=True)
class Entry:
    digest: str
    data: bytes | None = None  # None: too large to keep, or a link
    link: str | None = None  # link target text (never followed)


Snapshot = dict[str, Entry]


def _links(root: Path) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        for name in [*dirnames, *filenames]:
            if name not in SKIP_DIRS and _is_link(current / name):
                found.append(current / name)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not _is_link(current / d)]
    return found


def take(root: Path, max_restore_bytes: int = MAX_RESTORE_BYTES) -> Snapshot:
    """Every regular file (bytes and digest) and every link (target text) under `root`."""
    root = Path(root)
    snap: Snapshot = {}
    for path in iter_workspace_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            data = path.read_bytes()
        except OSError:
            snap[rel] = Entry(digest="unreadable")
            continue
        digest = hashlib.sha256(data).hexdigest()
        snap[rel] = Entry(digest=digest, data=data if len(data) <= max_restore_bytes else None)
    for link in _links(root):
        try:
            target = os.readlink(link)
        except OSError:
            target = "?"
        snap[link.relative_to(root).as_posix()] = Entry(digest=f"link:{target}", link=target)
    return snap


def changed(before: Snapshot, after: Snapshot) -> list[str]:
    """Paths added, removed, or modified between two snapshots, sorted."""
    return sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))


def _remove(path: Path) -> None:
    if _is_link(path) or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _parents_are_real_dirs(root: Path, rel: str) -> bool:
    current = root
    for part in Path(rel).parts[:-1]:
        current = current / part
        if _is_link(current) or (current.exists() and not current.is_dir()):
            return False
    return True


def restore(root: Path, before: Snapshot, paths: list[str]) -> list[str]:
    """Put `paths` back to their state in `before` (delete those that did not exist).

    Returns one problem line per path that could not be restored.
    """
    root = Path(root)
    problems: list[str] = []
    for rel in sorted(paths, key=lambda p: (p.count("/"), p)):
        try:
            resolve_in_workspace(root, Path(rel).parent.as_posix() or ".")
            if ".." in Path(rel).parts or Path(rel).is_absolute():
                raise PathOutsideWorkspace(rel)
        except PathOutsideWorkspace:
            problems.append(f"{rel}: outside the workspace, not restored")
            continue
        if not _parents_are_real_dirs(root, rel):
            problems.append(f"{rel}: a parent directory is a link or a file, not restored")
            continue
        target = root / rel
        entry = before.get(rel)
        try:
            if _is_link(target) or target.exists():
                if entry is not None and entry.data is None and entry.link is None:
                    problems.append(f"{rel}: larger than {MAX_RESTORE_BYTES} bytes, not restored")
                    continue
                _remove(target)
            if entry is None:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if entry.link is not None:
                os.symlink(entry.link, target)
            elif entry.data is not None:
                target.write_bytes(entry.data)
            else:
                problems.append(f"{rel}: larger than {MAX_RESTORE_BYTES} bytes, not restored")
        except OSError as exc:
            problems.append(f"{rel}: restore failed ({type(exc).__name__})")
    return problems
