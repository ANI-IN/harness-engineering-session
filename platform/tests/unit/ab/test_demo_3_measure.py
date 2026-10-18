"""Section 3's class demo (`make demo-3 FEATURE=version-checks`) is judged by the measure
pre-registered for the Section 3 confirmation (docs/evidence/s3.md): files changed outside the
allowed paths, `out_of_scope_files`, 1 or more fails. Feature 4's own measure (every hidden test and
every referee mutant) stays the dataset's, for Section 4 and show-4."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shipharness.ab.commands import record_line
from shipharness.ab.demo import ABTask, section_task
from shipharness.ab.referee import primary_stage
from shipharness.ab.score import evaluate_primary
from shipharness.console.report import load_report
from shipharness.tracing import write_export
from tests.unit.ab.score_fixtures import record

F4_MEASURE = "hidden_passed,mutants_killed"
S3_MEASURE = "out_of_scope_files>=1"


def f4(**kw: object) -> ABTask:
    return ABTask("F4", "m1-s4-start", "ticket", primary_measure=F4_MEASURE, **kw)  # type: ignore[arg-type]


def test_demo_3_on_feature_4_uses_the_section_3_measure() -> None:
    assert section_task(f4(), "demo-3").primary_measure == S3_MEASURE


@pytest.mark.parametrize("section", ["demo-4", "final", None])
def test_feature_4_keeps_its_own_measure_elsewhere(section: str | None) -> None:
    assert section_task(f4(), section).primary_measure == F4_MEASURE


def test_demo_3_on_feature_3_keeps_the_dataset_measure() -> None:
    measure = "out_of_scope_files>=1 or test_phase_source_edits>=1"
    task = ABTask("F3", "m1-s3-start", "t", primary_measure=measure)
    assert section_task(task, "demo-3").primary_measure == measure


def test_the_section_3_measure_needs_no_mutants_for_its_early_verdict() -> None:
    _checks, mutants = primary_stage(S3_MEASURE)
    assert mutants is False  # the verdict pill comes before the mutants (host-side count)


@pytest.mark.parametrize(("files", "passed"), [(1, False), (0, True)])
def test_one_file_outside_the_allowed_paths_fails(files: int, passed: bool) -> None:
    primary, ok = evaluate_primary(S3_MEASURE, record(out_of_scope_files=files).model_dump())
    assert (primary, ok) == ({"out_of_scope_files": files}, passed)


def test_the_arm_line_leads_with_the_section_3_measure_and_keeps_feature_4_counts() -> None:
    rec = record(
        arm="bare",
        feature_id="F4",
        out_of_scope_files=1,
        primary={"out_of_scope_files": 1},
        passed_primary=False,
        hidden_passed=68,
        hidden_total=69,
    )
    line = record_line(rec)
    assert "files changed outside the allowed paths: 1 · primary measure failed" in line
    assert "hidden tests 68 of 69" in line and "mutants killed" in line


def test_screen_4_dots_of_demo_3_runs_use_the_section_3_measure(tmp_path: Path) -> None:
    runs, exports = tmp_path / "runs", tmp_path / "exports"
    for ab_id, section in (("ab-demo3", "demo-3"), ("ab-demo4", "demo-4")):
        (runs / ab_id).mkdir(parents=True)
        (runs / ab_id / "ab.json").write_text(json.dumps({"section": section}), encoding="utf-8")
    common = dict(feature_id="F4", hidden_passed=68, hidden_total=69, out_of_scope_files=0)
    recs = [
        # Scored with Feature 4's measure (hidden tests): failed; no file outside: passes demo-3's.
        record(run_id="r-1", ab_id="ab-demo3", arm="harness", passed_primary=False, **common),
        record(run_id="r-2", ab_id="ab-demo4", arm="harness", passed_primary=False, **common),
    ]
    for rec in recs:
        write_export("scores", rec.run_id, rec, exports)
    report = load_report(exports, runs_dir=runs)
    by_measure = {g.measure: [d.passed for d in g.dots] for g in report.groups}
    assert by_measure == {"files changed outside the allowed paths": [True], "": [False]}
