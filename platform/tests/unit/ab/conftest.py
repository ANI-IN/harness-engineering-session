from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
GIT_ID = ["-c", "user.name=t", "-c", "user.email=t@x", "-c", "core.autocrlf=false"]


def git(cwd: Path, *args: str) -> str:
    out = subprocess.run(["git", *GIT_ID, *args], cwd=cwd, check=True, capture_output=True, env=ENV)
    return out.stdout.decode().strip()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


@pytest.fixture
def course_repo(tmp_path: Path) -> Path:
    """A miniature course checkout with a tagged TeamTrack checkpoint."""
    repo = tmp_path / "course"
    tt = repo / "teamtrack"
    write(tt / "app" / "main.py", "def create_app():\n    return 'app'\n")
    write(tt / "app" / "api" / "issues.py", "def list_issues():\n    return []\n")
    write(tt / "docs" / "HANDBOOK.md", "# Handbook\nR1 tenant isolation\n")
    write(tt / "tests" / "visible" / "test_app.py", "def test_app():\n    assert True\n")
    write(tt / "tests" / "hidden" / "f1" / "test_secret.py", "def test_secret():\n    assert 1\n")
    write(tt / "harness" / "instructions" / "AGENTS.md", "# Map\n")
    write(tt / "mutants" / "issues.jsonl", "{}\n")
    write(tt / "reference" / "f1" / "issues.py", "SOLUTION = 1\n")
    write(tt / "app" / "__pycache__" / "main.cpython-312.pyc", "x")
    write(tt / "teamtrack.db", "sqlite")
    write(repo / "README.md", "course\n")
    git(repo, "init", "-q")
    git(repo, "add", "-A", "-f")
    git(repo, "commit", "-qm", "course")
    git(repo, "tag", "m1-s1-start")
    return repo
