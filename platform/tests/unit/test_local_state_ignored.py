"""Folders the tool writes in a learner's copy stay out of `git status`."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("path", ["exports/scores/r-1.json", ".shipharness/runs/ab-1/ab.json"])
def test_tool_output_is_git_ignored(path: str) -> None:
    found = subprocess.run(["git", "check-ignore", "-q", "--no-index", path], cwd=REPO, check=False)
    assert found.returncode == 0, f"{path} is not git-ignored"
