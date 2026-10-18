"""The console at 100% zoom at 1366x768, 1440x900, and 1920x1080: the page scrolls naturally, no
element clips its content, nothing scrolls sideways, and panels stack on a narrow window. The two
long lists scroll inside at least 15 lines, with an Expand toggle and keyboard scrolling. Every run
page has an "All runs" link, and H or Esc goes back to the run list (not while typing in a field).

Marked `browser`; skips cleanly when Chromium is not installed. The same checks run on recorded
runs with `platform/scripts/check_console_layout.py`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from shipharness.console.app import create_console_app
from shipharness.console.layout_check import (
    SIZES,
    VIEWPORTS,
    runlist_problems,
    screen_problems,
    sweep,
)
from tests.unit.console.fixture_log import AB_ID, build_fixture_exports, build_fixture_run
from tests.unit.console.run_logs import multi_session_run, show_4_run, single_arm_run

pytestmark = pytest.mark.browser

SINGLE = "ab-20261018-045459-aaaaaa"
LONG = "ab-20261018-040749-bbbbbb"
SHOW_4 = "ab-20261018-040352-dddddd"  # long test and mutant names


@pytest.fixture
def base(tmp_path: Path, live_server: Callable[[Any], Any]) -> str:
    runs = tmp_path / "runs"
    build_fixture_run(runs)
    single_arm_run(runs, SINGLE)
    multi_session_run(runs, LONG, extra_turns=40)
    show_4_run(runs, SHOW_4)
    exports = build_fixture_exports(tmp_path / "exports")
    return str(live_server(create_console_app(runs, exports_dir=exports)).url)


def _page(chromium: Any, width: int, height: int) -> Any:
    context = chromium.new_context(
        viewport={"width": width, "height": height}, device_scale_factor=1, bypass_csp=True
    )
    return context, context.new_page()


@pytest.mark.parametrize(("width", "height"), SIZES)
@pytest.mark.parametrize("run", [AB_ID, SINGLE, LONG, SHOW_4])
def test_every_screen_fits_and_clips_nothing(
    chromium: Any, base: str, run: str, width: int, height: int
) -> None:
    context, page = _page(chromium, width, height)
    try:
        page.goto(f"{base}/run/{run}")
        for key in "12345":
            assert screen_problems(page, key) == [], (key, width)
    finally:
        context.close()


def test_the_page_grows_with_its_content_and_scrolls(chromium: Any, base: str) -> None:
    context, page = _page(chromium, 1366, 768)
    try:
        page.goto(f"{base}/run/{AB_ID}")
        page.keyboard.press("3")
        height = page.evaluate("document.documentElement.scrollHeight")
        assert height > 768  # the evidence screen is taller than the window: the page scrolls
    finally:
        context.close()


def test_the_long_lists_scroll_inside_15_lines_and_expand(chromium: Any, base: str) -> None:
    context, page = _page(chromium, 1440, 900)
    try:
        page.goto(f"{base}/run/{LONG}")
        page.wait_for_function(
            "/^(live|finished)/.test(document.getElementById('conn').textContent)"
        )
        page.keyboard.press("1")
        lst = page.locator("#turns-harness")
        line = page.evaluate("parseFloat(getComputedStyle(document.body).lineHeight)")
        box = lst.bounding_box()
        assert box["height"] >= 15 * line - 2  # at least 15 lines tall
        scroll = page.evaluate(
            "(() => { const l = document.getElementById('turns-harness');"
            " return [l.scrollHeight, l.clientHeight, getComputedStyle(l).overflowY]; })()"
        )
        assert scroll[0] > scroll[1] and scroll[2] == "scroll"  # a visible scrollbar
        lst.focus()
        page.keyboard.press("PageDown")  # keyboard scrolling (smooth: wait for it)
        page.wait_for_function(
            "document.getElementById('turns-harness').scrollTop > 0", timeout=3000
        )
        page.evaluate("document.getElementById('turns-harness').scrollTop = 0")
        page.mouse.move(box["x"] + 20, box["y"] + 20)
        page.mouse.wheel(0, 300)  # mouse-wheel scrolling
        page.wait_for_function(
            "document.getElementById('turns-harness').scrollTop > 0", timeout=3000
        )
        toggle = page.locator('.expand-toggle[data-expand="turns-harness"]')
        assert toggle.text_content() == "Expand"
        toggle.click()
        assert toggle.text_content() == "Collapse"
        expanded = page.evaluate(
            "(() => { const l = document.getElementById('turns-harness');"
            " return l.scrollHeight <= l.clientHeight + 2; })()"
        )
        assert expanded  # the whole list shows in the page
    finally:
        context.close()


def test_panels_stack_on_a_narrow_window(chromium: Any, base: str) -> None:
    context, page = _page(chromium, 600, 1000)  # no room for two 20 rem columns
    try:
        page.goto(f"{base}/run/{AB_ID}")
        page.keyboard.press("3")
        lefts = page.evaluate(
            "[...document.querySelectorAll('#screen-3 .panel')].map(p => "
            "Math.round(p.getBoundingClientRect().left))"
        )
        assert len(lefts) == 3 and len(set(lefts)) == 1  # one column
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    finally:
        context.close()


def test_body_text_stays_projector_readable_at_1366(chromium: Any, base: str) -> None:
    context, page = _page(chromium, 1366, 768)
    try:
        page.goto(f"{base}/run/{AB_ID}")
        size = page.evaluate("parseFloat(getComputedStyle(document.body).fontSize)")
        assert size >= 20
    finally:
        context.close()


@pytest.mark.parametrize("key", ["h", "H", "Escape", "click"])
def test_back_to_the_run_list(chromium: Any, base: str, key: str) -> None:
    context, page = _page(chromium, 1440, 900)
    try:
        page.goto(f"{base}/run/{SINGLE}")
        link = page.locator("a.all-runs")
        assert link.is_visible() and link.text_content().strip() == "← All runs"
        box = link.bounding_box()
        assert box["x"] < 100 and box["y"] < 80  # top left
        if key == "click":
            link.click()
        else:
            page.keyboard.press(key)
        page.wait_for_url(f"{base}/")
        assert "Runs" in page.content()
    finally:
        context.close()


def test_h_typed_in_a_field_and_screen_keys_do_not_navigate(chromium: Any, base: str) -> None:
    context, page = _page(chromium, 1440, 900)
    try:
        url = f"{base}/run/{SINGLE}"
        page.goto(url)
        for key in ["1", "2", "3", "4", "5", "f", "F"]:
            page.keyboard.press(key)
        assert page.url.startswith(url)
        page.evaluate(
            "() => { const i = document.createElement('input'); i.id = 'probe';"
            " document.body.appendChild(i); i.focus(); }"
        )
        page.keyboard.press("h")
        page.keyboard.press("Escape")
        assert page.url.startswith(url)
        page.keyboard.press("Control+h")
        assert page.url.startswith(url)
    finally:
        context.close()


# The CI sweep: every 160 CSS px from 320 to 2560 at heights 600 and 1000, the pixel-ratio set, and
# the named viewports (display scaling, zoom, phone). `check_console_layout.py --step 40` runs the
# full sweep on recorded runs.
CI_SWEEP = [*sweep(160), *VIEWPORTS]


def test_the_sweep_holds_on_every_screen_and_the_run_list(
    chromium: Any, base: str, tmp_path: Path, live_server: Callable[[Any], Any]
) -> None:
    empty = str(live_server(create_console_app(tmp_path / "none", exports_dir=tmp_path / "x")).url)
    failures: list[str] = []
    passed = 0
    for vp in CI_SWEEP:
        context = chromium.new_context(
            viewport={"width": vp.width, "height": vp.height}, device_scale_factor=vp.dpr
        )
        page = context.new_page()
        for url in (f"{base}/", f"{empty}/"):
            page.goto(url)
            problems = runlist_problems(page)
            failures += [f"{vp.name} {url}: {p}" for p in problems]
            passed += not problems
        for run in (AB_ID, SINGLE, SHOW_4):
            page.goto(f"{base}/run/{run}")
            for key in "134":
                problems = screen_problems(page, key)
                failures += [f"{vp.name} {run} {key}: {p}" for p in problems]
                passed += not problems
        context.close()
    assert failures == [], failures[:10]
    assert passed == len(CI_SWEEP) * 11
