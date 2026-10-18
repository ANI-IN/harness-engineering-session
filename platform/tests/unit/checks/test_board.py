"""board: sign in as the home org, load the board, see only own-org cards and no duplicates."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from shipharness.checks import CheckContext, CheckResult, get_check
from shipharness.checks.board import cards_in_html
from shipharness.checks.builtin import load_builtin_checks
from tests.unit.checks import seeds
from tests.unit.checks.conftest import chromium_available

load_builtin_checks()


def run(build: Path, mode: str, tmp_path: Path) -> CheckResult:
    params = {"board_mode": mode, "artifacts_dir": str(tmp_path / "artifacts")}
    ctx = CheckContext(checkpoint="m1-base", feature_id="F1", params=params)
    return get_check("board").run(build, ctx)


def keys(result: CheckResult) -> set[str]:
    return {f.detail_key for f in result.findings if f.counted}


def test_cards_in_html_reads_data_attributes_in_any_order() -> None:
    html = (
        '<article class="card" data-issue-id="3" data-org="acme">'
        '<article data-org="globex" class="card" data-issue-id="21">'
    )
    assert cards_in_html(html) == [("3", "acme"), ("21", "globex")]


def test_board_html_mode_base_passes(base_build: Path, tmp_path: Path) -> None:
    result = run(base_build, "html", tmp_path)
    assert result.passed is True, result.findings
    assert result.total_probes == 10


def test_board_html_mode_catches_other_org_and_duplicate_cards(
    make_build: Callable[[], Path], tmp_path: Path
) -> None:
    result = run(seeds.board_shows_other_orgs(make_build()), "html", tmp_path)
    assert keys(result) == {"foreign_cards", "duplicate_cards"}


@pytest.mark.browser
def test_board_browser_mode_base_and_seeded(
    base_build: Path, make_build: Callable[[], Path], tmp_path: Path
) -> None:
    if not chromium_available():
        pytest.skip("Playwright Chromium is not installed (uv run playwright install chromium)")
    base = run(base_build, "browser", tmp_path)
    assert base.passed is True, base.findings
    assert base.artifacts and Path(base.artifacts[0]).exists()
    seeded = run(seeds.board_shows_other_orgs(make_build()), "browser", tmp_path / "seeded")
    assert keys(seeded) == {"foreign_cards", "duplicate_cards"}
