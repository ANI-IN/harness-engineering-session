"""Board capture in a real Chromium against the TeamTrack base app (trusted base code, served on
the host only in tests). Marked `browser`; skips cleanly when Chromium is not installed."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from shipharness.console.board_capture import (
    VIEWPORT,
    capture_board,
    capture_conflict,
    mark_board,
    prepare_database,
)
from shipharness.console.preview import BoardPreview, parse_capture_output
from shipharness.events import EventBus, read_events
from shipharness.layout import find_repo_root
from shipharness.sandbox import ExecResult

pytestmark = pytest.mark.browser

TEAMTRACK = find_repo_root(Path(__file__)) / "platform" / "teamtrack"
FIXTURE_BOARD = """<!doctype html><html><head><title>b</title></head><body>
<article class="card" data-issue-id="1" data-org="acme"><a class="title">Login bug</a></article>
<article class="card" data-issue-id="21" data-org="globex"><a class="title">Globex x</a></article>
<article class="card" data-issue-id="7" data-org="acme"><a class="title">Add labels</a></article>
<article class="card" data-issue-id="8" data-org="acme"><a class="title">add labels</a></article>
</body></html>"""


@pytest.fixture
def page(chromium: Any) -> Any:
    context = chromium.new_context(viewport=VIEWPORT)
    yield context.new_page()
    context.close()


@pytest.fixture
def teamtrack_url(tmp_path: Path, live_server: Callable[[Any], Any]) -> str:
    from app.main import create_app
    from app.settings import TeamTrackSettings

    url = prepare_database(TEAMTRACK, tmp_path / "preview.db")
    return live_server(create_app(TeamTrackSettings(database_url=url))).url


def test_marks_are_computed_and_drawn_from_data_attributes(
    page: Any, tmp_path: Path, evidence_dir: Callable[[Path], Path]
) -> None:
    page.set_content(FIXTURE_BOARD)
    overlays = mark_board(page, "acme")
    assert [(o["issue_id"], o["mark"]) for o in overlays] == [(21, "other_org"), (8, "duplicate")]
    badges = page.locator(".sh-badge").all_text_contents()
    assert badges == ["⚠ OTHER ORG: globex", "⧉ DUPLICATE of #7"]
    shot = tmp_path / "board-capture-marks.png"
    page.screenshot(path=str(shot))
    evidence_dir(shot)


def test_capture_board_as_acme_on_the_base_app(
    page: Any, teamtrack_url: str, tmp_path: Path, evidence_dir: Callable[[Path], Path]
) -> None:
    overlays, png = capture_board(page, teamtrack_url, "admin@acme.test", "acme")
    assert overlays == []  # the base board shows only the viewer's org
    assert png.startswith(b"\x89PNG") and len(png) > 10_000
    orgs = set(
        page.eval_on_selector_all(".card[data-issue-id]", "els => els.map(e => e.dataset.org)")
    )
    assert orgs == {"acme"}
    shot = tmp_path / "board-capture-base.png"
    shot.write_bytes(png)
    evidence_dir(shot)


def test_two_tab_conflict_on_the_base_app_is_a_lost_update(
    page: Any, teamtrack_url: str, tmp_path: Path, evidence_dir: Callable[[Path], Path]
) -> None:
    overlays, png = capture_conflict(page, teamtrack_url, "admin@acme.test")
    [overlay] = overlays
    assert overlay["mark"] == "lost_update"
    assert "LOST UPDATE" in page.locator("#sh-result").text_content()
    issue = overlay["issue_id"]
    page.goto(f"{teamtrack_url}/board/issues/{issue}")
    assert page.input_value("form.edit-issue input[name=title]") not in (
        "Edited in tab A",
        "Edited in tab B",
    )  # original title restored
    shot = tmp_path / "board-capture-conflict.png"
    shot.write_bytes(png)
    evidence_dir(shot)


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONUTF8": "1"}
    return subprocess.run(
        [sys.executable, "-m", "shipharness.console.board_capture", *args],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        check=False,
    )


@pytest.mark.usefixtures("chromium")  # skip when Chromium is not installed
def test_cli_once_prints_a_valid_capture_line(teamtrack_url: str) -> None:
    result = run_cli("once", "--base-url", teamtrack_url)
    assert result.returncode == 0, result.stderr[-2000:]
    shot = parse_capture_output(result.stdout)
    assert shot.view == "board" and shot.overlays == []


def test_cli_wait_reports_readiness(teamtrack_url: str) -> None:
    assert run_cli("wait", "--base-url", teamtrack_url, "--timeout", "10").returncode == 0
    assert run_cli("wait", "--base-url", "http://127.0.0.1:9", "--timeout", "1").returncode == 1


class SubprocessSandbox:
    """Test double for the preview container: runs the module commands as host subprocesses
    (the capture script is trusted; the app is the TeamTrack base)."""

    def __init__(self) -> None:
        self.commands: list[str] = []

    def start(self) -> str:
        return "host-test"

    def exec(self, command: str, timeout_s: int) -> ExecResult:
        self.commands.append(command)
        argv = shlex.split(command.removeprefix("env HOME=/tmp "))
        if argv and argv[0] == "python":
            argv[0] = sys.executable
        started = time.monotonic()
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        return ExecResult(
            exit_code=proc.returncode,
            output=proc.stdout + proc.stderr,
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    def usage(self) -> dict[str, float]:
        return {}

    def stop(self) -> None:
        pass


@pytest.mark.usefixtures("chromium")  # skip when Chromium is not installed
def test_orchestrator_end_to_end_emits_a_screenshot_event(
    teamtrack_url: str, tmp_path: Path
) -> None:
    run_dir = tmp_path / "runs" / "ab-e2e"
    with EventBus(run_dir / "events.jsonl", ab_id="ab-e2e") as bus:
        preview = BoardPreview(
            SubprocessSandbox(), bus, run_dir, run_id="run-h", arm="harness", base_url=teamtrack_url
        )
        event = preview.capture()
    assert event is not None, preview.last_error
    [logged] = list(read_events(run_dir / "events.jsonl"))
    assert (
        logged.type == "screenshot" and logged.data["path"] == "screenshots/harness/board-0001.png"
    )
    assert (run_dir / logged.data["path"]).read_bytes().startswith(b"\x89PNG")
