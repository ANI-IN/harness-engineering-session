"""Helpers for the feature verification tests: builds per (task, checkpoint), hidden test ids."""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

from shipharness.ab import checkpoints as cp
from shipharness.config.prices import REPO_ROOT

TEAMTRACK = REPO_ROOT / "platform" / "teamtrack"
HIDDEN = TEAMTRACK / "tests" / "hidden"
FEATURES = [f"f{n}" for n in range(1, 8)]


def pairs() -> list[tuple[str, str]]:
    """Every (task, checkpoint) pair the F manifests run."""
    return [(t, c) for t in FEATURES for c in cp.load_task(t).hidden]


def build(task: str, checkpoint: str, dest: Path, *, reference: bool) -> Path:
    """The checkpoint as a TeamTrack tree, with the task's reference applied when asked."""
    cp.materialize(REPO_ROOT, checkpoint, dest)
    if reference:
        cp.apply_reference(task, checkpoint, dest)
    return dest


def install_hidden(build_dir: Path, files: list[str]) -> None:
    """Copy the hidden fixtures and the listed files into the build, as the referee mounts them."""
    target = build_dir / "tests" / "hidden"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("conftest.py", "hidden_support.py"):
        shutil.copy2(HIDDEN / name, target / name)
    for rel in files:
        source = TEAMTRACK / rel
        (build_dir / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, build_dir / rel)


def test_ids(files: list[str], root: Path = TEAMTRACK) -> list[str]:
    """`file::test_name` for every top-level test function in `files` (static, like the referee)."""
    found: list[str] = []
    for rel in files:
        tree = ast.parse((root / rel).read_text(encoding="utf-8"))
        found += [
            f"{rel}::{node.name}"
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test")
        ]
    return found


def visible_ids(build_dir: Path) -> list[str]:
    files = sorted(
        p.relative_to(build_dir).as_posix()
        for p in (build_dir / "tests" / "visible").glob("test*.py")
    )
    return test_ids(files, build_dir)


def reference_test_files(task: str, checkpoint: str) -> list[str]:
    """Visible test files the reference patch adds (the tests it ships)."""
    text = cp.patch_for(task, checkpoint).read_text(encoding="utf-8")
    added: list[str] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("--- /dev/null") and i + 1 < len(lines):
            path = lines[i + 1].removeprefix("+++ b/")
            if path.startswith("tests/visible/test"):
                added.append(path)
    return added
