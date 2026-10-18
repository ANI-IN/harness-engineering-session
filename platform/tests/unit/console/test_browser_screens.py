"""Playwright evidence: each screen rendered in Chromium from the fixture run log at 1920x1080.

Marked `browser`; skips cleanly when Chromium is not installed.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from shipharness.console.app import create_console_app
from shipharness.events import EventBus
from tests.unit.console.fixture_log import AB_ID, build_fixture_exports, build_fixture_run

pytestmark = pytest.mark.browser

VIEWPORT = {"width": 1920, "height": 1080}
# The page is connected: "live · event N" while a run goes on, "finished" once it is complete.
CONNECTED = "/^(live|finished)/.test(document.getElementById('conn').textContent)"
SCREEN_NAMES = {"1": "live", "2": "boards", "3": "evidence", "4": "report", "5": "traces"}


@pytest.fixture
def console(tmp_path: Path, live_server: Callable[[Any], Any]) -> tuple[str, Path]:
    runs = tmp_path / "runs"
    log = build_fixture_run(runs, recorded=True)
    exports = build_fixture_exports(tmp_path / "exports")
    server = live_server(create_console_app(runs, exports_dir=exports))
    return f"{server.url}/run/{AB_ID}", log


@pytest.fixture
def page(chromium: Any) -> Any:
    # bypass_csp lets Playwright evaluate test predicates; the page itself runs under the CSP.
    context = chromium.new_context(viewport=VIEWPORT, device_scale_factor=1, bypass_csp=True)
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.errors = errors
    yield page
    context.close()


def visible_screen(page: Any) -> str:
    return page.evaluate(
        "[...document.querySelectorAll('.screen')].filter(s => s.offsetParent !== null)"
        ".map(s => s.dataset.screen).join(',')"
    )


def test_each_screen_renders_and_is_saved_as_evidence(
    page: Any, console: tuple[str, Path], tmp_path: Path, evidence_dir: Callable[[Path], Path]
) -> None:
    url, _ = console
    page.goto(url)
    page.wait_for_function(CONNECTED)
    for key, name in SCREEN_NAMES.items():
        page.keyboard.press(key)
        assert visible_screen(page) == key
        screen = page.locator(f"#screen-{key}")
        assert screen.locator(".badge.recording").is_visible(), name
        assert screen.locator(".panel").count() <= 3
        shot = tmp_path / f"console-screen-{key}-{name}.png"
        page.screenshot(path=str(shot))
        assert shot.stat().st_size > 10_000
        evidence_dir(shot)
    assert page.errors == []


def test_all_visible_text_is_at_least_20px(page: Any, console: tuple[str, Path]) -> None:
    page.goto(console[0])
    for key in SCREEN_NAMES:
        page.keyboard.press(key)
        small = page.evaluate(
            """() => {
              const out = [];
              const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
              while (walker.nextNode()) {
                const node = walker.currentNode;
                if (!node.textContent.trim()) continue;
                const el = node.parentElement;
                if (!el || el.offsetParent === null) continue;
                const size = parseFloat(getComputedStyle(el).fontSize);
                const text = node.textContent.trim().slice(0, 30);
                if (size < 20) out.push(el.tagName + ':' + size + ':' + text);
              }
              return out;
            }"""
        )
        assert small == [], (key, small[:5])


def test_layout_fills_1920_wide_and_never_scrolls_sideways(
    page: Any, console: tuple[str, Path]
) -> None:
    # Owner, 2026-10-18: the page grows with its content and scrolls down; never sideways.
    page.goto(console[0])
    for key in SCREEN_NAMES:
        page.keyboard.press(key)
        box = page.evaluate(
            "(() => { const r = document.querySelector('.frame').getBoundingClientRect();"
            " return [r.width, r.height, document.documentElement.scrollWidth]; })()"
        )
        assert box[0] == 1920 and box[2] == 1920 and box[1] >= 1080, key


def test_no_panel_clips_its_content_on_the_fixture(page: Any, console: tuple[str, Path]) -> None:
    page.goto(console[0])
    for key in SCREEN_NAMES:
        page.keyboard.press(key)
        clipped = page.evaluate(
            f"[...document.querySelectorAll('#screen-{key} .panel')]"
            ".filter(p => p.scrollHeight > p.clientHeight + 2 || p.scrollWidth > p.clientWidth + 2)"
            ".map(p => (p.querySelector('h2') || p).textContent.trim().slice(0, 40)"
            " + ' ' + p.scrollHeight + 'x' + p.scrollWidth"
            " + ' client ' + p.clientHeight + 'x' + p.clientWidth)"
        )
        assert clipped == [], (key, clipped)


def test_f_cycles_full_screen_for_one_arm(page: Any, console: tuple[str, Path]) -> None:
    page.goto(console[0])
    bare = page.locator('#screen-1 .arm-panel[data-arm="bare"]')
    harness = page.locator('#screen-1 .arm-panel[data-arm="harness"]')
    assert bare.is_visible() and harness.is_visible()
    page.keyboard.press("f")
    assert bare.is_visible() and not harness.is_visible()
    assert bare.bounding_box()["width"] > 1500
    assert page.locator("#full-label").text_content() == "bare"
    page.keyboard.press("F")
    assert harness.is_visible() and not bare.is_visible()
    page.keyboard.press("f")
    assert bare.is_visible() and harness.is_visible()


def test_new_events_update_the_open_page(page: Any, console: tuple[str, Path]) -> None:
    url, log = console
    page.goto(url)
    page.wait_for_function(CONNECTED)
    with EventBus(log, ab_id=AB_ID) as bus:
        bus.publish(
            "sandbox_usage",
            {
                "cpu_pct": 77.0,
                "mem_mb": 640.0,
                "mem_limit_mb": 1024.0,
                "pids": 40,
                "time_left_s": 59,
            },
            run_id="run-bare",
            arm="bare",
            recorded=True,
        )
    page.wait_for_function(
        "document.querySelector('#screen-1').textContent.includes('CPU 77%')", timeout=10_000
    )
    assert "00:59 left" in page.locator("#screen-1").text_content()


def test_board_screenshot_images_load(page: Any, console: tuple[str, Path]) -> None:
    page.goto(console[0])
    page.keyboard.press("2")
    loaded = page.evaluate(
        "[...document.querySelectorAll('#screen-2 img.shot')]"
        ".map(i => i.complete && i.naturalWidth > 0)"
    )
    assert loaded and all(loaded)
