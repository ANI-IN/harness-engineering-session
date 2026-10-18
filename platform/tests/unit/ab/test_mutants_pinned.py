"""Referee mutants come from the pinned checkpoint commit, not the working tree, so swap and replay
judge with the mutants the A/B used even after mutant files change."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from shipharness.ab.mutants import load_referee_mutants, referee_mutants


def _record(mutant_id: str, replacement: str) -> str:
    return json.dumps(
        {
            "id": mutant_id,
            "target": "app.m",
            "set": "referee",
            "file": "app/m.py",
            "line": 1,
            "original": "x = 1",
            "replacement": replacement,
            "rationale": "test",
        }
    )


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "course"
    mutants = repo / "teamtrack" / "mutants"
    mutants.mkdir(parents=True)
    (mutants / "app.m.jsonl").write_text(_record("app.m-m1", "x = 2") + "\n", encoding="utf-8")

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
            cwd=repo, capture_output=True, text=True, check=True,
        ).stdout.strip()  # fmt: skip

    git("init", "-q")
    git("add", "-A")
    git("commit", "-qm", "base")
    sha = git("rev-parse", "HEAD")
    # The working tree changes after the A/B started.
    (mutants / "app.m.jsonl").write_text(_record("app.m-m9", "x = 9") + "\n", encoding="utf-8")
    return repo, sha


def test_mutants_load_from_the_pinned_commit(tmp_path: Path) -> None:
    repo, sha = _repo(tmp_path)
    assert [m.id for m in load_referee_mutants("app.m", repo, ref=sha)] == ["app.m-m1"]
    assert [m.id for m in load_referee_mutants("app.m", repo)] == ["app.m-m9"]


def test_referee_mutants_passes_the_ref_through(tmp_path: Path) -> None:
    repo, sha = _repo(tmp_path)
    assert [m.id for m in referee_mutants("app.m", repo, None, ref=sha)] == ["app.m-m1"]


def test_unknown_set_at_the_pinned_commit_scores_zero(tmp_path: Path) -> None:
    repo, sha = _repo(tmp_path)
    assert referee_mutants("app.missing", repo, None, ref=sha) == []
