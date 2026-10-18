"""The private graders' own tests, run from the suite (build repository only).

The graders, their hidden cases, and their tests stay out of the public release, so they are not
in pytest's testpaths (the public pyproject.toml would name private folders). Each grader's tests
run here in their own pytest process: their conftest and helper modules then never shadow
TeamTrack's `conftest` import. Without the graders (the public repository) the tests skip.

Assignment 1's grader tests are not run: their synthetic live fixtures lack a ScoreRecord field
added on 2026-10-17 (`constructed`), a known gap of the A1 grader.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from shipharness.layout import find_repo_root

REPO = find_repo_root(Path(__file__))
SECTIONS = ("section-2-state-lifecycle", "section-3-scope-sandbox", "section-4-verification")


@pytest.mark.slow
@pytest.mark.parametrize("section", SECTIONS)
def test_the_grader_tests_of_each_section_pass(section: str) -> None:
    tests = REPO / section / "assignment" / "solution" / "grader" / "tests"
    if not tests.is_dir():
        pytest.skip("the graders are private (build repository only)")
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-m",
            "not live and not docker",
            str(tests),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )
    assert done.returncode == 0, done.stdout[-4000:] + done.stderr[-2000:]
