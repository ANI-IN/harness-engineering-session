"""Console readability rules checked on the stylesheet and the rendered screens."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from shipharness.console.report import load_report
from shipharness.console.screens import STATUS, ScreenContext, ScreenRenderer, status
from shipharness.console.state import ConsoleState
from shipharness.events import read_events
from shipharness.layout import find_repo_root
from tests.unit.console.fixture_log import build_fixture_exports, build_fixture_run

STATIC = find_repo_root(Path(__file__)) / "platform" / "src" / "shipharness" / "console" / "static"
TEMPLATES = (
    find_repo_root(Path(__file__)) / "platform" / "src" / "shipharness" / "console" / "templates"
)
CSS = (STATIC / "console.css").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def screens(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    root = tmp_path_factory.mktemp("read")
    log = build_fixture_run(root / "runs", recorded=True)
    exports = build_fixture_exports(root / "exports")
    ctx = ScreenContext(
        "ab-fixture", ConsoleState.from_events(read_events(log)), load_report(exports), str(exports)
    )
    return ScreenRenderer().render_all(ctx)


def css_vars() -> dict[str, str]:
    root = re.search(r":root\s*\{([^}]*)\}", CSS)
    assert root
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", root.group(1)))


def luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_every_font_size_is_at_least_the_root_size() -> None:
    # Owner, 2026-10-18: fluid at any size. Text sizes are rem (1 rem or more) on a root size that
    # grows with the window: 16 px on a phone, 20 px (projector) from about 1300 CSS px up.
    assert "html { font-size: clamp(16px, 0.75rem + 0.6vw, 20px); }" in CSS
    body = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S).split("html {", 1)[1].split("}", 1)[1]
    sizes = re.findall(r"font(?:-size)?:\s*([^;]+);", body)
    assert sizes
    for value in sizes:
        if value.strip() == "inherit":
            continue
        rem = re.findall(r"(\d+(?:\.\d+)?)rem", value)
        assert rem, f"font size must be in rem: {value!r}"
        assert float(rem[0]) >= 1, value
    assert not re.search(r"font(?:-size)?:[^;]*\d+px", body)


def test_templates_carry_no_inline_styles() -> None:
    for path in TEMPLATES.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        assert "style=" not in text, path.name
        assert "<script>" not in text and "<style" not in text, path.name


def test_text_and_status_colours_have_high_contrast() -> None:
    colours = css_vars()
    for background in ("bg", "panel", "panel-2"):
        assert contrast(colours["text"], colours[background]) >= 12, background
        assert contrast(colours["muted"], colours[background]) >= 7, background
        for tone in ("good", "bad", "warn", "wait", "info", "bare", "harness"):
            assert contrast(colours[tone], colours[background]) >= 7, (tone, background)
    assert contrast(colours["recording-text"], colours["recording"]) >= 3.5


def test_the_frame_fills_the_window() -> None:
    # Owner, 2026-10-18: fit the screen at 100% zoom from 1366x768 up (was a fixed 1920x1080 frame).
    frame = re.search(r"\.frame\s*\{([^}]*)\}", CSS)
    assert frame and "width: 100%" in frame.group(1) and "min-height: 100vh" in frame.group(1)


def test_no_panel_has_a_fixed_height_or_clips() -> None:
    # Owner, 2026-10-18: the page scrolls naturally; panels grow with their content. Only the two
    # long lists (.scroll-list) scroll inside, and the ablation bar track clips its own fill.
    plain = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)  # comments out
    for rule in re.finditer(r"([^{}]+)\{([^}]*)\}", plain):
        selector, body = rule.group(1).strip(), rule.group(2)
        if "overflow: hidden" in body or "overflow-y: hidden" in body:
            assert selector == ".track", selector
        if re.search(r"(?<![-\w])height:\s*\d+vh", body):
            raise AssertionError(f"fixed viewport height: {selector}")
        if selector in (".panel", ".grid", ".screen"):
            assert "max-height" not in body and "overflow-y" not in body, selector
    assert ".scroll-list {" in CSS and "overflow-y: scroll" in CSS


def test_at_most_three_panels_per_screen(screens: dict[str, str]) -> None:
    assert sorted(screens) == ["1", "2", "3", "4", "5"]
    for key, html in screens.items():
        count = len(re.findall(r'class="panel[ "]', html))
        assert 1 <= count <= 3, (key, count)


class StatusParser(HTMLParser):
    """Collect (symbol, label) for each .status element."""

    def __init__(self) -> None:
        super().__init__()
        self.found: list[list[str]] = []
        self._stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = (dict(attrs).get("class") or "").split()
        role = (
            "status"
            if "status" in classes
            else "sym"
            if "sym" in classes
            else ("label" if "label" in classes else "")
        )
        if role == "status":
            self.found.append(["", ""])
        self._stack.append(role)

    def handle_endtag(self, tag: str) -> None:
        if self._stack:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        if not self._stack or not self.found or "status" not in self._stack:
            return
        if self._stack[-1] == "sym":
            self.found[-1][0] += data.strip()
        elif self._stack[-1] == "label":
            self.found[-1][1] += data.strip()


def test_every_status_has_a_symbol_and_a_label(screens: dict[str, str]) -> None:
    total = 0
    for key, html in screens.items():
        parser = StatusParser()
        parser.feed(html)
        for symbol, label in parser.found:
            assert symbol and label, (key, symbol, label)
        total += len(parser.found)
    assert total > 40


def test_status_vocabulary_never_relies_on_colour_alone() -> None:
    for key, (symbol, label, tone) in STATUS.items():
        assert symbol and label and tone, key
    rendered = status("pass", "R1")
    assert '<span class="sym" aria-hidden="true">✓</span>' in rendered
    assert '<span class="label">R1</span>' in rendered
    assert "&lt;b&gt;" in status("fail", "<b>x</b>")  # labels are escaped
    # Pass and fail differ in symbol, not only in colour.
    assert STATUS["pass"][0] != STATUS["fail"][0]
    assert STATUS["killed"][0] != STATUS["survived"][0]


def test_report_dots_differ_in_shape(screens: dict[str, str]) -> None:
    report = screens["4"]
    assert re.search(r'class="dot pass"[^>]*>●<', report)
    assert re.search(r'class="dot fail"[^>]*>○<', report)


def test_client_script_handles_keys_and_full_screen() -> None:
    js = (STATIC / "stream.js").read_text(encoding="utf-8")
    assert 'e.key >= "1" && e.key <= "5"' in js
    assert 'e.key === "f" || e.key === "F"' in js
    assert "new EventSource(" in js
    assert "http://" not in js and "https://" not in js  # nothing loads from a CDN
