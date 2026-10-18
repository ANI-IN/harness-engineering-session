from __future__ import annotations

import json
from pathlib import Path

from shipharness.ab.report import build_report, render_dot_plot, write_report
from shipharness.tracing import write_export

from .score_fixtures import record


def fixture_exports(tmp_path: Path) -> Path:
    exports = tmp_path / "exports"
    runs = [
        ("bare", 2, False),
        ("bare", 1, False),
        ("bare", 0, True),
        ("harness", 0, True),
        ("harness", 0, True),
        ("harness", 1, False),
    ]
    for i, (arm, r1, passed) in enumerate(runs):
        rec = record(
            run_id=f"r-20261016-10000{i}-aaaaa{i}",
            arm=arm,
            r1_new_violations=r1,
            primary={"r1_new_violations": r1},
            passed_primary=passed,
        )
        write_export("scores", rec.run_id, rec, exports)
    s4 = record(
        run_id="r-20261016-110000-cccccc",
        arm="harness",
        feature_id="F4",
        primary={"hidden_passed": 9, "mutants_killed": 3},
        hidden_passed=9,
        hidden_total=12,
        mutants_killed=3,
        mutants_total=8,
    )
    write_export("scores", s4.run_id, s4, exports)
    replay = record(run_id="r-20261016-120000-dddddd-replay", recorded=True, passed_primary=False)
    write_export("scores", replay.run_id, replay, exports)
    write_export(
        "experiments",
        "shipharness-batch-1-harness-2026-10-16-0001",
        {"name": "x", "arm": "harness", "comparison_url": "https://smith.example/compare/1"},
        exports,
    )
    return exports


def test_report_counts_runs_failing_out_of_k_per_arm(tmp_path: Path) -> None:
    report = build_report(fixture_exports(tmp_path))
    f1 = next(g for g in report["groups"] if g["feature_id"] == "F1")
    assert f1["measure"] == "r1_new_violations"
    assert f1["arms"]["bare"]["failing"] == "2/3"
    assert f1["arms"]["harness"]["failing"] == "1/3"
    assert sorted(d["value"] for d in f1["arms"]["bare"]["dots"]) == [0, 1, 2]


def test_report_excludes_recorded_runs_unless_asked(tmp_path: Path) -> None:
    exports = fixture_exports(tmp_path)
    live = build_report(exports)
    assert live["runs"] == 7
    assert build_report(exports, include_recorded=True)["runs"] == 8


def test_co_primary_counts_get_one_group_per_measure_with_totals(tmp_path: Path) -> None:
    report = build_report(fixture_exports(tmp_path))
    f4 = [g for g in report["groups"] if g["feature_id"] == "F4"]
    assert {g["measure"] for g in f4} == {"hidden_passed", "mutants_killed"}
    hidden = next(g for g in f4 if g["measure"] == "hidden_passed")
    assert hidden["arms"]["harness"]["dots"][0] == {
        "value": 9,
        "total": 12,
        "run_id": "r-20261016-110000-cccccc",
        "passed": True,
        "status": "completed",
    }


def test_report_reads_comparison_links_from_experiment_exports(tmp_path: Path) -> None:
    report = build_report(fixture_exports(tmp_path))
    assert report["comparison_urls"] == ["https://smith.example/compare/1"]


def test_dot_plot_svg_has_one_dot_per_run_and_a_legend(tmp_path: Path) -> None:
    report = build_report(fixture_exports(tmp_path))
    f1 = next(g for g in report["groups"] if g["feature_id"] == "F1")
    svg = render_dot_plot(f1)
    assert svg.startswith("<svg") and svg.count("<circle") == 6
    assert "bare" in svg and "harness" in svg
    assert "2/3" in svg  # counts, not percentages
    assert "%" not in svg


def test_write_report_produces_static_html_and_json(tmp_path: Path) -> None:
    exports = fixture_exports(tmp_path)
    html_path = write_report(exports, tmp_path / "out")
    html = html_path.read_text(encoding="utf-8")
    assert "<table" in html and "<svg" in html
    # Headings name the feature and the measure; report.json keeps the machine ids.
    assert (
        "<h2>Feature 1: Org-wide issue search · House rule 1: Tenant isolation, new violations"
        in (html)
    )
    assert 'aria-label="Feature 1: Org-wide issue search · House rule 1' in html
    assert "prefers-color-scheme: dark" in html
    data = json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))
    assert data["runs"] == 7


def test_empty_exports_give_an_empty_report(tmp_path: Path) -> None:
    report = build_report(tmp_path / "nothing")
    assert report["groups"] == [] and report["runs"] == 0
    assert "No runs" in write_report(tmp_path / "nothing", tmp_path / "o").read_text()
