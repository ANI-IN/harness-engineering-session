"""Harness commits run in the sandbox and name their paths; harness writes never follow links."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from shipharness.config import Settings
from shipharness.harness.state.commit import commit_command, commit_paths
from shipharness.harness.state.files import UnsafeWorkspacePath, move_file, write_file
from shipharness.sandbox import LocalSandbox, default_policy


def test_commit_command_names_paths_and_identity() -> None:
    command = commit_command(["progress.md", "docs/exec-plans"], "harness: session 1")
    assert command.startswith('git add -A -- "progress.md" "docs/exec-plans" && git ')
    assert "user.name=shipharness" in command and "--no-verify" in command
    assert command.endswith('-m "harness: session 1" -- "progress.md" "docs/exec-plans"')


@pytest.mark.parametrize("bad", ["../x", "-rf", "a b", "/etc/passwd", 'x"; rm -rf /'])
def test_commit_command_refuses_unsafe_paths(bad: str) -> None:
    with pytest.raises(ValueError):
        commit_command([bad], "m")


def test_commit_message_is_sanitised() -> None:
    command = commit_command(["progress.md"], 'harness "$(touch x)" `id`')
    assert "$(" not in command and "`" not in command
    assert command.count('"') == 4 + 2  # two quoted path pairs + the message quotes


def test_commit_paths_commits_only_the_named_paths(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@x"]
    subprocess.run([*git, "init", "-q"], cwd=ws, check=True)
    (ws / "a.txt").write_text("a\n", encoding="utf-8")
    subprocess.run([*git, "add", "."], cwd=ws, check=True)
    subprocess.run([*git, "commit", "-qm", "init"], cwd=ws, check=True)
    (ws / "agent.txt").write_text("staged by the agent\n", encoding="utf-8")
    subprocess.run([*git, "add", "agent.txt"], cwd=ws, check=True)
    (ws / "progress.md").write_text("# Progress\n", encoding="utf-8")
    sandbox = LocalSandbox(default_policy(Settings(_env_file=None)), ws, None, "r-1", "harness")
    result = commit_paths(sandbox, ["progress.md"], "harness: test")
    assert result.exit_code == 0, result.output
    files = subprocess.run(
        ["git", "show", "--name-only", "--format=%an", "HEAD"],
        cwd=ws,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert files == ["shipharness", "progress.md"]
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ws, check=True, capture_output=True, text=True
    ).stdout
    assert "A  agent.txt" in status  # the agent's staged file is untouched


def test_write_file_creates_parents(tmp_path: Path) -> None:
    write_file(tmp_path, "docs/exec-plans/active/F3.md", b"plan\n")
    assert (tmp_path / "docs/exec-plans/active/F3.md").read_bytes() == b"plan\n"


def test_write_file_refuses_a_file_as_parent(tmp_path: Path) -> None:
    (tmp_path / "docs").write_text("not a dir", encoding="utf-8")
    with pytest.raises(UnsafeWorkspacePath):
        write_file(tmp_path, "docs/x.md", b"x")


def test_write_file_refuses_dotdot(tmp_path: Path) -> None:
    with pytest.raises(UnsafeWorkspacePath):
        write_file(tmp_path, "../x.md", b"x")


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs privileges on Windows")
def test_write_file_never_writes_through_a_linked_parent(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "docs").symlink_to(outside, target_is_directory=True)
    with pytest.raises(UnsafeWorkspacePath):
        write_file(ws, "docs/x.md", b"x")
    assert list(outside.iterdir()) == []


def test_move_file(tmp_path: Path) -> None:
    write_file(tmp_path, "a/x.md", b"x")
    assert move_file(tmp_path, "a/x.md", "b/x.md") is True
    assert not (tmp_path / "a/x.md").exists() and (tmp_path / "b/x.md").read_bytes() == b"x"
    assert move_file(tmp_path, "a/x.md", "b/x.md") is False
