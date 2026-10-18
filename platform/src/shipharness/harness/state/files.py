"""Host-side writes of harness files into the untrusted workspace: never through a link."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from shipharness.runner.tools import _is_link


class UnsafeWorkspacePath(OSError):
    """A harness file path runs through a link, a file, or out of the workspace."""


def _checked(workspace: Path, rel: str) -> Path:
    parts = PurePosixPath(rel).parts
    if not parts or ".." in parts or PurePosixPath(rel).is_absolute():
        raise UnsafeWorkspacePath(f"bad harness path: {rel!r}")
    current = Path(workspace)
    for part in parts[:-1]:
        current = current / part
        if _is_link(current) or (current.exists() and not current.is_dir()):
            raise UnsafeWorkspacePath(f"{rel}: {current.name} is a link or a file")
        current.mkdir(exist_ok=True)
    target = current / parts[-1]
    if _is_link(target):
        target.unlink()  # replace a planted link instead of writing through it
    elif target.is_dir():
        raise UnsafeWorkspacePath(f"{rel} is a directory")
    return target


def write_file(workspace: Path, rel: str, data: bytes) -> None:
    _checked(workspace, rel).write_bytes(data)


def read_text(workspace: Path, rel: str, limit: int = 200_000) -> str | None:
    """Text of a workspace file, or None if it is missing, a link, or too large."""
    path = Path(workspace) / rel
    if _is_link(path) or not path.is_file() or path.stat().st_size > limit:
        return None
    return path.read_bytes().decode("utf-8", errors="replace")


def move_file(workspace: Path, src: str, dst: str) -> bool:
    """Move a regular file; False if `src` is missing or is a link."""
    source = Path(workspace) / src
    if _is_link(source) or not source.is_file():
        return False
    data = source.read_bytes()
    write_file(workspace, dst, data)
    source.unlink()
    return True
