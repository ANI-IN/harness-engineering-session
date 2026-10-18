"""Visible tests for the live evidence in `live/` (criterion `live-evidence`).

The files are validated, never re-run: no model call, no key, no network. What each file holds
and how it is checked is in `a4_live.py`.
"""

from __future__ import annotations

from pathlib import Path

import a4_live as live  # a module import: pytest must not collect `testgen_*` names as tests
import pytest
from a4_support import REPO


def _check(problems: list[str]) -> None:
    assert not problems, "\n".join(problems)


@pytest.mark.criterion("live-evidence")
def test_live_testgen_run(impl_path: Path) -> None:
    _check(live.testgen_run_problems(impl_path))


@pytest.mark.criterion("live-evidence")
def test_live_testgen_report_shows_filter_6(impl_path: Path) -> None:
    _check(live.filter6_problems(impl_path))


@pytest.mark.criterion("live-evidence")
def test_live_ab_command_and_cost(impl_path: Path) -> None:
    _check(live.ab_run_problems(impl_path))


@pytest.mark.criterion("live-evidence")
def test_live_ab_score_records(impl_path: Path) -> None:
    sha = live.course_checkpoint_sha(REPO)
    missing = [] if sha else [f"the course repo has no {live.AB_CHECKPOINT} tag: git fetch --tags"]
    _check(missing + live.score_record_problems(impl_path, sha))
