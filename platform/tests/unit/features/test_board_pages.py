"""Board pages of the reference features, at HTML level: F2's comments panel, F4's 409 page.

The checkpoint builds are loaded in process (like the checks do), so these run without a browser.
The S4 conflict screen (`console.board_capture.capture_conflict`) accepts 409, 412, or 428 for the
stale save; the reference answers 409 with an HTML page.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from shipharness.ab import checkpoints as cp
from shipharness.checks.probe import load_app
from shipharness.config.prices import REPO_ROOT


@pytest.fixture(autouse=True)
def _restore_app_modules() -> Iterator[None]:
    saved = {k: v for k, v in sys.modules.items() if k == "app" or k.startswith("app.")}
    path = list(sys.path)
    yield
    for name in [k for k in sys.modules if k == "app" or k.startswith("app.")]:
        del sys.modules[name]
    sys.modules.update(saved)
    sys.path[:] = path


def board(checkpoint: str, tmp_path: Path, email: str) -> TestClient:
    build = cp.materialize(REPO_ROOT, checkpoint, tmp_path / "build")
    app: Any = load_app(build, tmp_path / "board.db")
    client = TestClient(app)
    response = client.post("/board/login", data={"email": email}, follow_redirects=False)
    assert response.status_code == 303
    return client


# -- F2 comments panel (checkpoints that contain F2) --------------------------------------------


def test_f2_panel_lists_comments_with_ids_and_a_form(tmp_path: Path) -> None:
    client = board("m1-s3-start", tmp_path, "member@acme.test")
    html = client.get("/board/issues/1").text
    panel = re.search(r'<section class="comments".*?</section>', html, re.S)
    assert panel is not None
    assert re.findall(r'class="comment" data-comment-id="(\d+)"', panel.group(0)) == ["1", "2"]
    assert 'action="/board/issues/1/comments"' in panel.group(0)


def test_f2_panel_has_no_form_for_viewers(tmp_path: Path) -> None:
    client = board("m1-complete", tmp_path, "viewer@acme.test")
    html = client.get("/board/issues/1").text
    assert 'class="comment" data-comment-id="1"' in html
    assert 'class="add-comment"' not in html


def test_f2_panel_is_absent_before_f2(tmp_path: Path) -> None:
    client = board("m1-s2-start", tmp_path, "member@acme.test")
    assert 'class="comments"' not in client.get("/board/issues/1").text


# -- F4 conflict page -------------------------------------------------------------------------


def _version(html: str) -> str:
    match = re.search(r'<input type="hidden" name="version" value="(\d+)">', html)
    assert match is not None, "edit form has no version field"
    return match.group(1)


def test_f4_two_tab_edit_gives_a_409_page(tmp_path: Path) -> None:
    client = board("m1-final-start", tmp_path, "admin@acme.test")
    tab_a = _version(client.get("/board/issues/1").text)
    tab_b = _version(client.get("/board/issues/1").text)
    saved = client.post(
        "/board/issues/1/edit",
        data={"title": "Edited in tab A", "priority": "low", "version": tab_a},
        follow_redirects=False,
    )
    assert saved.status_code == 303
    stale = client.post(
        "/board/issues/1/edit",
        data={"title": "Edited in tab B", "priority": "low", "version": tab_b},
        follow_redirects=False,
    )
    assert stale.status_code == 409  # board_capture marks 409/412/428 as conflict_detected
    assert stale.headers["content-type"].startswith("text/html")
    assert 'class="conflict"' in stale.text
    assert 'href="/board/issues/1"' in stale.text
    assert "Edited in tab A" in client.get("/board/issues/1").text


def test_f4_board_before_f4_overwrites_silently(tmp_path: Path) -> None:
    client = board("m1-s4-start", tmp_path, "admin@acme.test")
    for title in ("Edited in tab A", "Edited in tab B"):
        response = client.post(
            "/board/issues/1/edit",
            data={"title": title, "priority": "low"},
            follow_redirects=False,
        )
        assert response.status_code == 303
    assert "Edited in tab B" in client.get("/board/issues/1").text
