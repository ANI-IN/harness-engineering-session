"""A/B report from `exports/` only: one dot per run per arm for each primary
measure, and counts ("2/3 runs failing"), never percentages. Replays
(`recorded=True`) are left out unless asked for, and single-arm runs (`ab --arms harness`, harness
in action) always are: they have no bare run to compare with. Constructed examples (`shipharness
example`, scripted steps) are never counted either. Output: report.json and a static report.html.
"""

from __future__ import annotations

import html
import json
from collections import defaultdict
from pathlib import Path
from string import Template
from typing import Any

from shipharness.console.labels import measure_label
from shipharness.datasets.names import feature_label
from shipharness.tracing import read_exports

ARM_ORDER = ("bare", "harness")
# Categorical slots 1 and 2 of the reference palette (light / dark steps).
ARM_COLORS = {"bare": ("#2a78d6", "#3987e5"), "harness": ("#eb6834", "#d95926")}
_TOTALS = {"hidden_passed": "hidden_total", "mutants_killed": "mutants_total"}


def group_title(group: dict[str, Any]) -> str:
    """'Feature 1: Org-wide issue search · House rule 1: Tenant isolation, new violations'."""
    return f"{feature_label(group['feature_id'])} · {measure_label(group['measure'])}"


def build_report(exports_dir: Path, include_recorded: bool = False) -> dict[str, Any]:
    scores = [
        s
        for s in read_exports("scores", exports_dir)
        if (include_recorded or not s.get("recorded"))
        and not s.get("single_arm")
        and not s.get("constructed")
    ]
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for s in sorted(scores, key=lambda s: (s["feature_id"], s["captured_at"], s["run_id"])):
        for measure, value in (s.get("primary") or {}).items():
            group = groups.setdefault(
                (s["feature_id"], measure),
                {"feature_id": s["feature_id"], "measure": measure, "arms": {}},
            )
            arm = group["arms"].setdefault(s["arm"], {"dots": []})
            total_key = _TOTALS.get(measure)
            arm["dots"].append(
                {
                    "value": value,
                    "total": s.get(total_key) if total_key else None,
                    "run_id": s["run_id"],
                    "passed": bool(s["passed_primary"]),
                    "status": s["status"],
                }
            )
    for group in groups.values():
        for arm in group["arms"].values():
            dots = arm["dots"]
            arm["failing"] = f"{sum(not d['passed'] for d in dots)}/{len(dots)}"
    experiments = read_exports("experiments", exports_dir)
    return {
        "runs": len(scores),
        "groups": [groups[k] for k in sorted(groups)],
        "comparison_urls": sorted(
            {e["comparison_url"] for e in experiments if e.get("comparison_url")}
        ),
        "cost_usd": round(sum(s["cost_usd"] + s.get("review_cost_usd", 0.0) for s in scores), 6),
    }


def _num(value: Any) -> float:
    return float(value) if not isinstance(value, bool) else float(int(value))


def _frame(label: str, width: int, height: int, left: int, right: int, top: float) -> list[str]:
    """SVG opening tag and a recessive x axis from 0 to `top`."""
    y = height - 28
    return [
        f'<svg class="dots" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{html.escape(label)}">',
        f'<line class="axis" x1="{left}" x2="{width - right}" y1="{y}" y2="{y}"/>',
        f'<text class="tick" x="{left}" y="{height - 10}">0</text>',
        f'<text class="tick" x="{width - right}" y="{height - 10}" text-anchor="end">'
        f"{top:g}</text>",
    ]


# [walkthrough:Final:dots] start
def render_dot_plot(group: dict[str, Any], width: int = 640) -> str:
    """One row per arm, one dot per run. Filled = passed the primary measure, hollow = failed,
    so pass/fail never depends on colour alone. The row label carries the count."""
    rows = [a for a in ARM_ORDER if a in group["arms"]]
    values = [_num(d["value"]) for a in rows for d in group["arms"][a]["dots"]]
    totals = [_num(d["total"]) for a in rows for d in group["arms"][a]["dots"] if d["total"]]
    top = max([1.0, *values, *totals])
    left, right, row_h = 150, 24, 56
    height = row_h * len(rows) + 40
    x = lambda v: left + (width - left - right) * (_num(v) / top)  # noqa: E731
    parts = _frame(group_title(group), width, height, left, right, top)
    for i, arm in enumerate(rows):
        y = row_h * i + 30
        info = group["arms"][arm]
        parts.append(
            f'<text class="label" x="0" y="{y + 5}">{arm} ({info["failing"]} failing)</text>'
        )
        seen: dict[float, int] = defaultdict(int)
        for dot in info["dots"]:
            stack = seen[_num(dot["value"])]
            seen[_num(dot["value"])] += 1
            fill = f"var(--{arm})" if dot["passed"] else "var(--surface)"
            tip = f"{dot['run_id']}: {dot['value']}" + (
                f" of {dot['total']}" if dot["total"] else ""
            )
            parts.append(
                f'<circle cx="{x(dot["value"]):.1f}" cy="{y - stack * 10}" r="5" '
                f'fill="{fill}" stroke="var(--{arm})" stroke-width="2">'
                f"<title>{html.escape(tip)} ({dot['status']})</title></circle>"
            )
    parts.append("</svg>")
    return "".join(parts)


# [walkthrough:Final:dots] end

_STYLE = Template(
    """
:root { --surface: #fcfcfb; --ink: #0b0b0b; --muted: #52514e;
  --bare: $bare_l; --harness: $harness_l; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { --surface: #1a1a19; --ink: #f0efec; --muted: #c3c2b7;
    --bare: $bare_d; --harness: $harness_d; }
}
:root[data-theme="dark"] { --surface: #1a1a19; --ink: #f0efec; --muted: #c3c2b7;
  --bare: $bare_d; --harness: $harness_d; }
body { background: var(--surface); color: var(--ink); font: 20px/1.4 system-ui, sans-serif;
  margin: 0 auto; max-width: 960px; padding: 16px; }
svg.dots { width: 100%; height: auto; } .axis { stroke: var(--muted); stroke-width: 1; }
.tick, .label { fill: var(--ink); font-size: 16px; } .tick { fill: var(--muted); }
table { border-collapse: collapse; width: 100%; } td, th { border-bottom: 1px solid var(--muted);
  padding: 4px 8px; text-align: left; }
"""
).substitute(
    bare_l=ARM_COLORS["bare"][0],
    harness_l=ARM_COLORS["harness"][0],
    bare_d=ARM_COLORS["bare"][1],
    harness_d=ARM_COLORS["harness"][1],
)


def render_html(report: dict[str, Any]) -> str:
    body = [
        f"<h1>A/B report</h1><p>{report['runs']} runs from exports/. One dot per run; filled "
        "dots passed the primary measure, hollow dots failed it.</p>"
    ]
    if not report["groups"]:
        body.append("<p>No runs in exports/scores yet.</p>")
    for group in report["groups"]:
        body.append(f"<h2>{html.escape(group_title(group))}</h2>{render_dot_plot(group)}")
        rows = "".join(
            f"<tr><td>{arm}</td><td>{info['failing']}</td><td>"
            + ", ".join(str(d["value"]) for d in info["dots"])
            + "</td></tr>"
            for arm, info in group["arms"].items()
        )
        body.append(
            "<table><tr><th>Arm</th><th>Runs failing</th><th>Values per run</th></tr>"
            f"{rows}</table>"
        )
    for url in report["comparison_urls"]:
        body.append(f'<p><a href="{html.escape(url)}">LangSmith comparison</a></p>')
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>A/B report</title><style>{_STYLE}</style></head><body>"
        + "".join(body)
        + "</body></html>"
    )


def write_report(exports_dir: Path, out_dir: Path, include_recorded: bool = False) -> Path:
    report = build_report(exports_dir, include_recorded)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    path = out_dir / "report.html"
    path.write_text(render_html(report), encoding="utf-8")
    return path
