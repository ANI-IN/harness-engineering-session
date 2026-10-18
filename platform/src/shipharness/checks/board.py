"""board: the web board loads for the home org and shows only that org's cards, once each.

Cards carry `data-issue-id` and `data-org`, so the check does not depend on the
arm's markup beyond those attributes. Modes (`params.board_mode`):

- "browser": the build runs under uvicorn on 127.0.0.1 (loopback works with network none) and a
  headless Playwright Chromium signs in, loads the board, reads the cards, and saves a screenshot
  under `params.artifacts_dir` (default `<build>/.referee/`);
- "html": the same flow through an in-process client, reading the cards from the HTML;
- "auto" (default): browser if Chromium starts, otherwise html with an info finding.
"""

from __future__ import annotations

import re
import socket
import tempfile
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from shipharness.checks._http import adapter_for
from shipharness.checks.adapter import TenantAppAdapter
from shipharness.checks.base import CheckContext, CheckResult, Finding, make_result, register_check

_TAG = re.compile(r"<[^>]*\bdata-issue-id=[^>]*>")
_ATTR = re.compile(r'\b(data-issue-id|data-org)="([^"]*)"')


class BrowserUnavailable(RuntimeError):
    pass


def cards_in_html(html: str) -> list[tuple[str, str]]:
    cards = []
    for tag in _TAG.findall(html):
        attrs = dict(_ATTR.findall(tag))
        cards.append((attrs.get("data-issue-id", ""), attrs.get("data-org", "")))
    return cards


def judge(status: int, cards: list[tuple[str, str]], home: str) -> list[Finding]:
    def finding(key: str, detail: str) -> Finding:
        return Finding(rule="board", severity="violation", detail_key=key, detail=detail)

    if status != 200 or not cards:
        return [finding("board_load", f"board answered {status} with {len(cards)} cards")]
    findings = []
    foreign = sorted({issue for issue, org in cards if org != home})
    if foreign:
        findings.append(finding("foreign_cards", f"cards from another org: {foreign[:20]}"))
    dupes = sorted(issue for issue, n in Counter(i for i, _ in cards).items() if n > 1)
    if dupes:
        findings.append(finding("duplicate_cards", f"cards shown more than once: {dupes[:20]}"))
    return findings


def via_html(adapter: TenantAppAdapter, app: Any, home: str) -> tuple[int, list[tuple[str, str]]]:
    client = TestClient(app, raise_server_exceptions=False)
    path, form = adapter.board_login(home, "member")
    client.post(path, data=form, follow_redirects=False)
    response = client.get(adapter.board_path(home), follow_redirects=True)
    return response.status_code, cards_in_html(response.text)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def via_browser(
    adapter: TenantAppAdapter, app: Any, home: str, shot: Path
) -> tuple[int, list[tuple[str, str]]]:
    import uvicorn

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - playwright is a dev dependency
        raise BrowserUnavailable(str(exc)) from exc
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="warning", timeout_graceful_shutdown=1
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 20
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.05)
        base = f"http://127.0.0.1:{port}"
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as exc:
                raise BrowserUnavailable(str(exc).splitlines()[0]) from exc
            try:
                context = browser.new_context(viewport={"width": 1280, "height": 900})
                path, form = adapter.board_login(home, "member")
                context.request.post(base + path, form=form, max_redirects=0)
                page = context.new_page()
                response = page.goto(base + adapter.board_path(home), wait_until="load")
                status = response.status if response is not None else 0
                cards = [
                    (el.get_attribute("data-issue-id") or "", el.get_attribute("data-org") or "")
                    for el in page.query_selector_all("[data-issue-id]")
                ]
                shot.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(shot), full_page=True)
            finally:
                browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    return status, cards


@register_check
class BoardCheck:
    name = "board"
    rule = "board"

    def run(self, build_dir: Path, ctx: CheckContext) -> CheckResult:
        started = time.monotonic()
        adapter = adapter_for(ctx)
        home, _other = adapter.orgs()
        mode = str(ctx.params.get("board_mode", "auto"))
        artifacts_dir = Path(ctx.params.get("artifacts_dir") or build_dir / ".referee")
        shot = artifacts_dir / f"board-{home}.png"
        notes: list[Finding] = []
        artifacts: list[str] = []
        with tempfile.TemporaryDirectory(
            prefix="shipharness-board-", ignore_cleanup_errors=True
        ) as tmp:
            app = adapter.create_app(build_dir, Path(tmp) / "board.db")
            ctx.progress(0, 1, "board")
            status, cards = 0, []
            used_browser = False
            if mode in ("browser", "auto"):
                try:
                    status, cards = via_browser(adapter, app, home, shot)
                    used_browser = True
                    artifacts.append(str(shot))
                except BrowserUnavailable as exc:
                    if mode == "browser":
                        raise
                    notes.append(
                        Finding(
                            rule="board",
                            severity="info",
                            detail_key="html_fallback",
                            detail=f"browser unavailable, read the HTML instead: {exc}",
                        )
                    )
            if not used_browser:
                status, cards = via_html(adapter, app, home)
            ctx.progress(1, 1, "board")
        findings = judge(status, cards, home) + notes
        return make_result(
            self.name, findings, total_probes=len(cards), started=started, artifacts=artifacts
        )
