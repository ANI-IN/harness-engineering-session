"""Workspace path safety: every agent-supplied path must stay inside the workspace."""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath


class PathOutsideWorkspace(ValueError):
    """Raised for absolute paths, `..` components, or symlinks that leave the workspace."""


def resolve_in_workspace(workspace: Path, rel: str) -> Path:
    raw = rel.strip()
    if raw.startswith(("/", "\\")) or PureWindowsPath(raw).drive:
        raise PathOutsideWorkspace(f"path_outside_workspace: absolute path {rel!r}")
    parts = PurePosixPath(raw.replace("\\", "/")).parts
    if ".." in parts:
        raise PathOutsideWorkspace(f"path_outside_workspace: '..' in {rel!r}")
    root = Path(workspace).resolve()
    candidate = (root / raw).resolve()
    if candidate != root and root not in candidate.parents:
        raise PathOutsideWorkspace(f"path_outside_workspace: {rel!r} resolves outside")
    return candidate


def to_workspace_rel(workspace: Path, path: Path) -> str:
    return Path(path).resolve().relative_to(Path(workspace).resolve()).as_posix()
