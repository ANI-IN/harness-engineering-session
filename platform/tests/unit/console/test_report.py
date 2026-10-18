"""Screen 4 reads ScoreRecords and experiments from exports/."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shipharness.console.report import exports_signature, load_report, safe_url
from tests.unit.console.fixture_log import build_fixture_exports


@pytest.fixture
def exports(tmp_path: Path) -> Path:
    return build_fixture_exports(tmp_path / "exports")


def test_dot_groups_per_feature_variant_and_arm_with_counts(exports: Path) -> None:
    # Screen 4 groups by feature; records scored before the current referee
    # version are left out (and counted).
    report = load_report(exports)
    rows = [(g.feature, g.variant, g.arm, g.count_label) for g in report.groups]
    assert rows == [
        ("F1", "s1", "bare", "3/10"),
        ("F1", "s1", "harness", "9/10"),
        ("F3", "s3", "bare", "2/10"),
        ("F3", "s3", "harness", "8/10"),
    ]
    assert report.older == 1
    s1_harness = report.groups[1]
    assert len(s1_harness.dots) == 10
    assert sum(d.passed for d in s1_harness.dots) == 9


def test_ablation_bars_come_only_from_ablation_experiments(exports: Path) -> None:
    bars = {b.label: b.count_label for b in load_report(exports).ablation}
    assert bars == {"instructions + state": "4/4"}


def test_cost_per_verified_feature_and_reviewer_agreement(exports: Path) -> None:
    report = load_report(exports)
    cost = {c.arm: c for c in report.costs}
    # 20 runs x ($0.10 + $0.01 review) = $2.20 spent per arm
    assert cost["harness"].verified == 17
    assert cost["harness"].per_verified_usd == pytest.approx(2.20 / 17)
    assert cost["bare"].verified == 5
    agree = {r.arm: r.count_label for r in report.reviewer}
    assert agree == {"bare": "18/20", "harness": "18/20"}


def test_experiment_links_and_unreadable_files(exports: Path) -> None:
    report = load_report(exports)
    names = [e.name for e in report.experiments]
    assert names == ["teamtrack-ablation", "teamtrack-s1", "teamtrack-s3"]
    assert report.experiments[1].comparison_url.endswith("/compare/s1")
    assert report.skipped == 1  # broken.json


def test_missing_exports_dir_gives_an_empty_report(tmp_path: Path) -> None:
    report = load_report(tmp_path / "nope")
    assert report.groups == [] and report.experiments == [] and report.empty


def test_records_with_missing_fields_are_skipped_not_fatal(tmp_path: Path) -> None:
    scores = tmp_path / "scores"
    scores.mkdir(parents=True)
    (scores / "a.json").write_text(json.dumps({"run_id": "x"}), encoding="utf-8")
    (scores / "b.json").write_text(json.dumps([1, 2]), encoding="utf-8")
    report = load_report(tmp_path)
    assert report.groups == [] and report.skipped == 2


def test_only_http_links_are_kept() -> None:
    assert safe_url("https://smith.langchain.com/x") == "https://smith.langchain.com/x"
    assert safe_url("javascript:alert(1)") is None
    assert safe_url(None) is None


def test_signature_changes_when_a_score_is_added(exports: Path) -> None:
    before = exports_signature(exports)
    (exports / "scores" / "new.json").write_text("{}", encoding="utf-8")
    assert exports_signature(exports) != before
