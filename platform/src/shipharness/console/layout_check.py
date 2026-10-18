"""Layout checks for the console in a real browser (Playwright), shared by the browser tests and
`platform/scripts/check_console_layout.py`.

The console has no layout tied to a screen size: it must hold at any width, height, display scaling,
or zoom. So the checks run as a sweep (`sweep()`: widths from 320 to 2560 CSS px, two heights, and
several device pixel ratios) plus named viewports (`VIEWPORTS`) for screenshots.

For the visible page (the header bar and the shown screen, or the whole run list): nothing scrolls
sideways (document scrollWidth <= window width); no element is wider than its own box (scrollWidth >
clientWidth), except the lists built to scroll (`data-scroll`); no text is cut by an ellipsis unless
the element carries the full text as a title; nothing reaches past the right edge of the window;
nothing clips its content vertically; the page scrolls to its bottom; no pill wraps onto a second
line; and no word of 8 or more letters or digits breaks across lines.
"""

from __future__ import annotations

from typing import Any, NamedTuple


class Viewport(NamedTuple):
    name: str  # the file-name part: width, then "x<dpr>" when the pixel ratio is not 1
    width: int
    height: int
    dpr: float = 1.0


def _vp(width: int, height: int, dpr: float = 1.0, suffix: str = "") -> Viewport:
    ratio = "" if dpr == 1 else f"x{dpr:g}"
    return Viewport(f"{width}{ratio}{suffix}", width, height, dpr)


# Named viewports for screenshots: a 1920x1080 laptop at 150% and 125% display scaling, a small
# laptop, the class screen sizes, a phone, and a 1920x1080 browser at 150% and 175% zoom.
VIEWPORTS: tuple[Viewport, ...] = (
    _vp(1280, 630, 1.5),
    _vp(1536, 730, 1.25),
    _vp(1024, 768),
    _vp(1366, 768),
    _vp(1440, 900),
    _vp(1920, 1080),
    _vp(390, 844, 3.0),
    _vp(1280, 720, 1.5, "-zoom150"),
    _vp(1097, 617, 1.75, "-zoom175"),
)
SIZES: tuple[tuple[int, int], ...] = ((1366, 768), (1440, 900), (1920, 1080))


def sweep(step: int = 40) -> list[Viewport]:
    """Every width from 320 to 2560 CSS px in `step`s at heights 600 and 1000 (pixel ratio 1), and
    pixel ratios 1.25, 1.5, and 2 at a few widths."""
    sizes = [_vp(w, h) for w in range(320, 2561, step) for h in (600, 1000)]
    sizes += [_vp(w, 700, dpr) for w in (360, 768, 1097, 1280, 1536) for dpr in (1.25, 1.5, 2.0)]
    return sizes


MEASURE_JS = r"""(rootSelector) => {
  const w = window.innerWidth;
  const roots = rootSelector.split(',').map(s => document.querySelector(s.trim())).filter(Boolean);
  const visible = roots.flatMap(r => [r, ...r.querySelectorAll('*')])
    .filter(e => e.offsetParent !== null || e.tagName === 'BODY');
  const name = e => e.tagName.toLowerCase() +
    (typeof e.className === 'string' && e.className.trim() ?
      '.' + e.className.trim().split(/\s+/).join('.') : '') +
    ' "' + (e.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 40) + '"';
  const wide = [], ellipsis = [], offscreen = [], clipped = [];
  for (const e of visible) {
    const r = e.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    const scrollList = e.closest('[data-scroll]');
    if (!scrollList && r.right > w + 1) offscreen.push(name(e) + ' right ' + Math.round(r.right));
    if (scrollList && scrollList !== e) continue;
    const cs = getComputedStyle(e);
    if (!scrollList && cs.display !== 'inline' && e.clientWidth > 0 &&
        e.scrollWidth > e.clientWidth + 1) {
      wide.push(name(e) + ' ' + e.scrollWidth + '>' + e.clientWidth);
    }
    if (cs.textOverflow === 'ellipsis' && e.scrollWidth > e.clientWidth + 1 && !e.title) {
      ellipsis.push(name(e));
    }
    const hidesY = cs.overflowY === 'hidden' || cs.overflowY === 'clip';
    if (!scrollList && hidesY && e.scrollHeight > e.clientHeight + 2) clipped.push(name(e));
  }
  const wrappedPills = visible.filter(e => e.classList && e.classList.contains('status'))
    .filter(e => {
      const cs = getComputedStyle(e);
      const line = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.35;
      return e.getBoundingClientRect().height > line * 1.6;
    }).map(name);
  const brokenWords = [];
  for (const root of roots) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    while (walker.nextNode() && brokenWords.length < 5) {
      const node = walker.currentNode;
      const parent = node.parentElement;
      if (!parent || parent.offsetParent === null || parent.closest('[data-scroll]')) continue;
      for (const m of node.textContent.matchAll(/[A-Za-z0-9]{8,}/g)) {
        const range = document.createRange();
        range.setStart(node, m.index);
        range.setEnd(node, m.index + m[0].length);
        const tops = new Set([...range.getClientRects()].map(x => Math.round(x.top)));
        if (tops.size > 1) { brokenWords.push(m[0]); break; }
      }
    }
  }
  const panels = visible.filter(e => e.classList && e.classList.contains('panel'));
  const bottom = Math.max(0, ...panels.map(p => p.getBoundingClientRect().bottom + window.scrollY));
  window.scrollTo(0, document.documentElement.scrollHeight);
  const reached = window.scrollY + window.innerHeight >= bottom - 2;
  window.scrollTo(0, 0);
  return {scrollWidth: document.documentElement.scrollWidth, width: w, panels: panels.length,
          wide: wide.slice(0, 5), ellipsis: ellipsis.slice(0, 5), offscreen: offscreen.slice(0, 5),
          clipped: clipped.slice(0, 5), wrappedPills: wrappedPills.slice(0, 5), brokenWords,
          reachedBottom: reached};
}"""


def _problems(m: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if m["panels"] < 1:
        problems.append("no panel shown")
    if m["scrollWidth"] > m["width"]:
        problems.append(f"scrolls sideways: {m['scrollWidth']} > {m['width']}")
    problems += [f"wider than its box: {x}" for x in m["wide"]]
    problems += [f"cut by an ellipsis without a title: {x}" for x in m["ellipsis"]]
    problems += [f"past the right edge: {x}" for x in m["offscreen"]]
    problems += [f"clipped: {x}" for x in m["clipped"]]
    problems += [f"pill on more than one line: {x}" for x in m["wrappedPills"]]
    problems += [f"word broken across lines: {x}" for x in m["brokenWords"]]
    if not m["reachedBottom"]:
        problems.append("the page does not scroll to its last panel")
    return problems


def screen_problems(page: Any, key: str) -> list[str]:
    """Every layout problem of screen `key` and the header bar on the open run page."""
    page.keyboard.press(key)
    return _problems(page.evaluate(MEASURE_JS, f".bar, #screen-{key}"))


def runlist_problems(page: Any) -> list[str]:
    """Every layout problem of the open run list (`/`)."""
    return _problems(page.evaluate(MEASURE_JS, "body"))
