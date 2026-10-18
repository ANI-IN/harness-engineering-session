"""The CI workflow gives each job what its tests read."""

from __future__ import annotations

from pathlib import Path

from shipharness.layout import find_repo_root

REPO = find_repo_root(Path(__file__))


def _job(name: str) -> str:
    text = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    return text.split(f"\n  {name}:\n", 1)[1].split("\n\n  ", 1)[0]


def test_the_full_job_checks_out_the_checkpoint_tags() -> None:
    # The full suite reads the m1-* checkpoint tags (the A4 grader's live tests); a default
    # checkout has no tags (CI 2026-10-18: rev-parse m1-s4-start failed at collection).
    full = _job("full")
    assert "fetch-depth: 0" in full
