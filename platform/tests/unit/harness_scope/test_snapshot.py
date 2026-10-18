"""Byte snapshots used to revert out-of-scope changes without git (contract I-7)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from shipharness.harness.scope import snapshot


def tree(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / "app").mkdir(parents=True)
    (ws / "app" / "a.py").write_bytes(b"a = 1\r\n")
    (ws / "app" / "b.py").write_bytes(b"b = 2\n")
    (ws / ".git").mkdir()
    (ws / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    return ws


def test_changed_lists_modified_new_and_deleted_files(tmp_path: Path) -> None:
    ws = tree(tmp_path)
    before = snapshot.take(ws)
    (ws / "app" / "a.py").write_bytes(b"a = 9\r\n")
    (ws / "app" / "b.py").unlink()
    (ws / "app" / "c.py").write_bytes(b"c = 3\n")
    (ws / ".git" / "HEAD").write_text("changed\n", encoding="utf-8")  # .git is not tracked
    assert snapshot.changed(before, snapshot.take(ws)) == ["app/a.py", "app/b.py", "app/c.py"]


def test_restore_puts_back_exact_bytes_and_deletes_new_files(tmp_path: Path) -> None:
    ws = tree(tmp_path)
    before = snapshot.take(ws)
    (ws / "app" / "a.py").write_bytes(b"a = 9\n")
    (ws / "app" / "b.py").unlink()
    (ws / "new").mkdir()
    (ws / "new" / "c.py").write_bytes(b"c = 3\n")
    problems = snapshot.restore(ws, before, ["app/a.py", "app/b.py", "new/c.py"])
    assert problems == []
    assert (ws / "app" / "a.py").read_bytes() == b"a = 1\r\n"
    assert (ws / "app" / "b.py").read_bytes() == b"b = 2\n"
    assert not (ws / "new" / "c.py").exists()
    assert snapshot.changed(before, snapshot.take(ws)) == []


def test_restore_refuses_paths_outside_the_workspace(tmp_path: Path) -> None:
    ws = tree(tmp_path)
    before = snapshot.take(ws)
    problems = snapshot.restore(ws, before, ["../outside.txt"])
    assert problems and "outside" in problems[0]


def test_large_files_are_tracked_by_digest_but_not_restorable(tmp_path: Path) -> None:
    ws = tree(tmp_path)
    (ws / "big.bin").write_bytes(b"x" * 200)
    before = snapshot.take(ws, max_restore_bytes=100)
    (ws / "big.bin").write_bytes(b"y" * 200)
    assert snapshot.changed(before, snapshot.take(ws, max_restore_bytes=100)) == ["big.bin"]
    problems = snapshot.restore(ws, before, ["big.bin"])
    assert problems and "big.bin" in problems[0]


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs privileges on Windows")
def test_new_links_are_seen_and_removed_without_following(tmp_path: Path) -> None:
    ws = tree(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("keep me\n", encoding="utf-8")
    before = snapshot.take(ws)
    (ws / "app" / "link").symlink_to(outside, target_is_directory=True)
    assert snapshot.changed(before, snapshot.take(ws)) == ["app/link"]
    assert snapshot.restore(ws, before, ["app/link"]) == []
    assert not (ws / "app" / "link").exists()
    assert (outside / "secret.txt").exists()
