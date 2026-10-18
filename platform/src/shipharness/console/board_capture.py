"""Board capture: runs INSIDE the preview container (network none), never on the host.

The preview container runs the arm's TeamTrack (agent-written code) and headless Chromium. This
trusted script signs in as an Acme user, screenshots the board, and marks cards whose `data-org`
is not the viewer's org and duplicate cards (same `data-issue-id` twice, or the same title twice
in one org: the visible result of a non-idempotent create). It can also capture the two-tab edit
conflict (S4): two tabs edit the same issue; a silent overwrite is a lost update.

Output protocol: one line `SHIPHARNESS-CAPTURE <json>` on stdout with `view`, `as_user`,
`overlays` (list of `{issue_id, mark}`) and `png_b64`. The host orchestrator
(`shipharness.console.preview`) reads it through `Sandbox.exec`, so no container needs a
published port or a shared mount.

    python -m shipharness.console.board_capture serve --app-dir /work --db /tmp/preview.db
    python -m shipharness.console.board_capture wait
    python -m shipharness.console.board_capture once [--view board|conflict]
    python -m shipharness.console.board_capture loop --interval 5 --out-dir /tmp/shots
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

MARKER = "SHIPHARNESS-CAPTURE "
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_USER = "admin@acme.test"
DEFAULT_ORG = "acme"
VIEWPORT = {"width": 1280, "height": 800}
MARKS = ("other_org", "duplicate", "lost_update", "conflict_detected", "error")

# Collect every card on the page, in document order.
COLLECT_JS = """() => [...document.querySelectorAll('.card[data-issue-id]')].map((el, index) => ({
  index,
  issue_id: el.dataset.issueId || '',
  org: el.dataset.org || '',
  title: ((el.querySelector('.title') || el).textContent || '').trim(),
}))"""

# Draw the marks: outline plus a label badge (symbol + text). Built with DOM APIs and textContent.
MARK_JS = """(overlays) => {
  const cards = [...document.querySelectorAll('.card[data-issue-id]')];
  const style = document.createElement('style');
  style.textContent = `
    .sh-mark-other_org { outline: 6px solid #d00000 !important; outline-offset: 2px; }
    .sh-mark-duplicate { outline: 6px dashed #b45309 !important; outline-offset: 2px; }
    .sh-badge { display: inline-block; margin: 0 6px 6px 0; padding: 2px 10px; border-radius: 6px;
      font: 700 18px/1.3 system-ui, sans-serif; color: #fff; }
    .sh-badge-other_org { background: #d00000; }
    .sh-badge-duplicate { background: #b45309; }`;
  document.head.appendChild(style);
  const symbols = { other_org: '\\u26a0', duplicate: '\\u29c9' };
  for (const o of overlays) {
    const el = cards[o.index];
    if (!el) continue;
    el.classList.add('sh-mark-' + o.mark);
    const badge = document.createElement('div');
    badge.className = 'sh-badge sh-badge-' + o.mark;
    badge.textContent = (symbols[o.mark] || '!') + ' ' + o.label;
    el.prepend(badge);
  }
  return overlays.length;
}"""

TABS_JS = """(url) => {
  document.body.textContent = '';
  const style = document.createElement('style');
  style.textContent = `
    body { margin: 0; font: 18px/1.4 system-ui, sans-serif; background: #f6f7f9; }
    .sh-row { display: flex; gap: 12px; padding: 12px; }
    .sh-tab { flex: 1; border: 3px solid #1b1f24; border-radius: 8px; background: #fff; }
    .sh-tab h2 { margin: 0; padding: 6px 12px; font-size: 20px; background: #1b1f24; color: #fff; }
    .sh-tab iframe { width: 100%; height: 560px; border: 0; }
    .sh-result { margin: 0 12px; padding: 10px 14px; font-size: 22px; font-weight: 700;
      border-radius: 8px; color: #fff; background: #57606a; }
    .sh-result.lost_update { background: #d00000; }
    .sh-result.conflict_detected { background: #1a7f37; }`;
  document.head.appendChild(style);
  const result = document.createElement('div');
  result.className = 'sh-result';
  result.id = 'sh-result';
  result.textContent = 'Two tabs edit the same issue';
  const row = document.createElement('div');
  row.className = 'sh-row';
  for (const name of ['tab-a', 'tab-b']) {
    const box = document.createElement('section');
    box.className = 'sh-tab';
    const title = document.createElement('h2');
    title.textContent = name === 'tab-a' ? 'Tab A' : 'Tab B';
    const frame = document.createElement('iframe');
    frame.name = name;
    frame.src = url;
    box.append(title, frame);
    row.append(box);
  }
  document.body.append(result, row);
}"""

RESULT_JS = """([mark, text]) => {
  const el = document.getElementById('sh-result');
  el.className = 'sh-result ' + mark;
  el.textContent = text;
}"""


def _norm(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip().casefold()


def _issue_id(value: object) -> int | str:
    text = str(value).strip()
    return int(text) if text.isdigit() else text


def compute_overlays(cards: list[dict[str, Any]], viewer_org: str) -> list[dict[str, Any]]:
    """Marks per card: `other_org` when `data-org` differs from the viewer's org; `duplicate` on
    a later card that repeats an earlier card's id, or its title within the same org."""
    overlays: list[dict[str, Any]] = []
    seen_ids: dict[int | str, int | str] = {}
    seen_titles: dict[tuple[str, str], int | str] = {}
    for card in cards:
        issue_id = _issue_id(card.get("issue_id", ""))
        org = str(card.get("org") or "")
        index = int(card.get("index", 0))
        if org != viewer_org:
            overlays.append(
                {
                    "index": index,
                    "issue_id": issue_id,
                    "mark": "other_org",
                    "label": f"OTHER ORG: {org or 'unknown'}",
                }
            )
        title_key = (org, _norm(str(card.get("title", ""))))
        first = seen_ids.get(issue_id)
        if first is None and title_key[1]:
            first = seen_titles.get(title_key)
        if first is not None:
            overlays.append(
                {
                    "index": index,
                    "issue_id": issue_id,
                    "mark": "duplicate",
                    "label": f"DUPLICATE of #{first}",
                }
            )
        seen_ids.setdefault(issue_id, issue_id)
        if title_key[1]:
            seen_titles.setdefault(title_key, issue_id)
    return overlays


def capture_line(view: str, as_user: str, overlays: list[dict[str, Any]], png: bytes) -> str:
    payload = {
        "view": view,
        "as_user": as_user,
        "overlays": [{"issue_id": o["issue_id"], "mark": o["mark"]} for o in overlays],
        "png_b64": base64.b64encode(png).decode("ascii"),
    }
    return MARKER + json.dumps(payload, separators=(",", ":"))


# -- browser flows (Playwright, inside the container) ---------------------------------------------
def login(page: Any, base_url: str, user: str) -> None:
    page.goto(f"{base_url}/board/login")
    page.locator(f'form:has(input[name="email"][value="{user}"]) button').click()
    page.wait_for_load_state("load")


def mark_board(page: Any, viewer_org: str) -> list[dict[str, Any]]:
    """Collect cards on the current page, compute marks, draw them; return the overlays."""
    cards = page.evaluate(COLLECT_JS)
    overlays = compute_overlays(cards, viewer_org)
    page.evaluate(MARK_JS, overlays)
    return overlays


def capture_board(page: Any, base_url: str, user: str, org: str) -> tuple[list[dict], bytes]:
    login(page, base_url, user)
    page.goto(f"{base_url}/board")
    page.wait_for_load_state("load")
    overlays = mark_board(page, org)
    return overlays, page.screenshot(full_page=False)


def capture_conflict(page: Any, base_url: str, user: str) -> tuple[list[dict], bytes]:
    """Two tabs open the same issue; A saves, then B saves from its stale form. If B's save is
    accepted and A's edit is gone, that is a lost update; a 409/412/428 is a detected conflict.
    The original title is restored afterwards (best effort)."""
    login(page, base_url, user)
    page.goto(f"{base_url}/board")
    first = page.locator(".card[data-issue-id]").first
    issue_id = _issue_id(first.get_attribute("data-issue-id"))
    issue_url = f"{base_url}/board/issues/{issue_id}"
    page.evaluate(TABS_JS, issue_url)
    frames = {}
    for name in ("tab-a", "tab-b"):
        deadline = time.monotonic() + 15
        while page.frame(name=name) is None and time.monotonic() < deadline:
            page.wait_for_timeout(50)
        frame = page.frame(name=name)
        frame.wait_for_selector("form.edit-issue input[name=title]")
        frames[name] = frame
    original = frames["tab-a"].input_value("form.edit-issue input[name=title]")

    def save(frame: Any, title: str) -> int:
        frame.fill("form.edit-issue input[name=title]", title)
        with page.expect_response(
            lambda r: r.request.method == "POST" and r.url.endswith(f"/issues/{issue_id}/edit")
        ) as info:
            frame.click("form.edit-issue button[type=submit]")
        frame.wait_for_load_state("load")
        return int(info.value.status)

    save(frames["tab-a"], "Edited in tab A")
    status_b = save(frames["tab-b"], "Edited in tab B")
    frames["tab-a"].goto(issue_url)
    now = frames["tab-a"].input_value("form.edit-issue input[name=title]")
    if status_b in (409, 412, 428):
        mark, text = "conflict_detected", f"✓ CONFLICT DETECTED: tab B got HTTP {status_b}"
    elif status_b < 400 and now == "Edited in tab B":
        mark, text = "lost_update", "✗ LOST UPDATE: tab B overwrote tab A without a conflict"
    else:
        mark, text = "error", f"! tab B save returned HTTP {status_b}; title now {now!r}"
    page.evaluate(RESULT_JS, [mark, text])
    png = page.screenshot(full_page=False)
    with contextlib.suppress(Exception):  # restoring the title is best effort
        save(frames["tab-a"], original)
    return [{"issue_id": issue_id, "mark": mark}], png


def capture(base_url: str, user: str, org: str, view: str) -> tuple[list[dict], bytes]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_context(viewport=VIEWPORT).new_page()
            if view == "conflict":
                return capture_conflict(page, base_url, user)
            return capture_board(page, base_url, user, org)
        finally:
            browser.close()


# -- serving the arm's TeamTrack inside the container ----------------------------------------------
def prepare_database(app_dir: Path, db_path: Path) -> str:
    """`alembic upgrade head` + demo seed for the app at `app_dir`; returns the database URL."""
    import importlib

    from alembic import command
    from alembic.config import Config

    app_dir = Path(app_dir).resolve()
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))
    url = f"sqlite:///{Path(db_path).resolve().as_posix()}"
    config = Config(str(app_dir / "alembic.ini"))
    config.set_main_option("script_location", str(app_dir / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    session_module = importlib.import_module("app.db.session")
    seed_module = importlib.import_module("app.seed")
    engine = session_module.make_engine(url)
    with session_module.make_session_factory(engine)() as session:
        seed_module.seed(session)
    engine.dispose()
    return url


def serve(app_dir: Path, db_path: Path, port: int) -> None:
    import os

    import uvicorn

    url = prepare_database(app_dir, db_path)
    os.environ["TEAMTRACK_DATABASE_URL"] = url
    # The preview starts before the agent works; reload (uvicorn's polling reloader, no extra
    # package) makes every frame show the arm's current code. Migrations run once, at start.
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host="127.0.0.1",
        port=port,
        app_dir=str(app_dir),
        log_level="warning",
        reload=True,
        reload_dirs=[str(Path(app_dir) / "app")],
    )


def wait_ready(base_url: str, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.25)
    return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m shipharness.console.board_capture")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("once", "loop", "wait"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--base-url", default=DEFAULT_BASE_URL)
        if name == "wait":
            cmd.add_argument("--timeout", type=float, default=60.0)
            continue
        cmd.add_argument("--user", default=DEFAULT_USER)
        cmd.add_argument("--org", default=DEFAULT_ORG)
        cmd.add_argument("--view", choices=("board", "conflict"), default="board")
        if name == "loop":
            cmd.add_argument("--interval", type=float, default=5.0)
            cmd.add_argument("--out-dir", default="/tmp/shots")
            cmd.add_argument("--count", type=int, default=0, help="0 = until stopped")
    srv = sub.add_parser("serve")
    srv.add_argument("--app-dir", default="/work")
    srv.add_argument("--db", default="/tmp/preview.db")
    srv.add_argument("--port", type=int, default=8000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        serve(Path(args.app_dir), Path(args.db), args.port)
        return 0
    if args.command == "wait":
        return 0 if wait_ready(args.base_url, args.timeout) else 1
    if args.command == "once":
        overlays, png = capture(args.base_url, args.user, args.org, args.view)
        print(capture_line(args.view, args.user, overlays, png), flush=True)
        return 0
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    while args.count == 0 or n < args.count:
        n += 1
        started = time.monotonic()
        overlays, png = capture(args.base_url, args.user, args.org, args.view)
        path = out_dir / f"{args.view}-{n:04d}.png"
        path.write_bytes(png)
        record = {"path": str(path), "view": args.view, "as_user": args.user, "overlays": overlays}
        print(MARKER + json.dumps(record), flush=True)
        time.sleep(max(0.0, args.interval - (time.monotonic() - started)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
