"""Visible tests for rule R8 (soft delete respected on every endpoint)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from a4_support import (
    CHECK_NAME,
    LEGACY,
    V_GET,
    V_GET_ENDPOINTS,
    V_LIST,
    counted_keys,
    make_build,
    new_keys,
    run_r8,
)

PROJECT_LIST = ("GET /projects/{project_id}/issues", "deleted_list")


@pytest.mark.criterion("R8-interface")
def test_check_is_registered_through_the_shipharness_registry(impl: object) -> None:
    from shipharness.checks import get_check, registered_checks

    assert CHECK_NAME in registered_checks()
    check = get_check(CHECK_NAME)
    assert check.name == CHECK_NAME
    assert getattr(check, "rule", None) == "R8"


@pytest.mark.criterion("R8-interface")
def test_result_has_probes_and_r8_findings_with_detail_keys(tmp_path: Path) -> None:
    result = run_r8(make_build(tmp_path))
    assert result.check == CHECK_NAME
    assert result.total_probes > 0
    assert result.findings, "the clean build still has the legacy /v1/issues finding"
    assert all(f.rule == "R8" for f in result.findings)
    assert all(f.detail_key for f in result.findings)


@pytest.mark.criterion("R8-interface")
def test_cli_wrapper_exit_codes_with_and_without_baseline(tmp_path: Path, impl_path: Path) -> None:
    build = make_build(tmp_path)
    extra = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(impl_path), *extra])}
    command = [
        sys.executable,
        "-m",
        "a4_verification.run_r8",
        "--build",
        str(build),
        "--checkpoint",
        "m1-base",
        "--feature",
        "A4",
    ]
    first = subprocess.run(command, capture_output=True, text=True, env=env, timeout=600)
    assert first.returncode == 3, first.stderr[-2000:]
    document = json.loads(first.stdout)
    assert [r["check"] for r in document["results"]] == [CHECK_NAME]
    baseline = tmp_path / "baseline.json"
    baseline.write_text(first.stdout, encoding="utf-8")
    second = subprocess.run(
        [*command, "--baseline", str(baseline)],
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )
    assert second.returncode == 0, second.stdout[-2000:] + second.stderr[-2000:]


@pytest.mark.criterion("R8-visible")
def test_finds_a_deleted_issue_that_resolves_by_id(tmp_path: Path) -> None:
    result = run_r8(make_build(tmp_path, [V_GET]))
    expected = {(endpoint, "deleted_path") for endpoint in V_GET_ENDPOINTS}
    missing = expected - counted_keys(result)
    assert not missing, f"not reported: {sorted(missing)}"


@pytest.mark.criterion("R8-visible")
def test_finds_a_deleted_issue_in_the_project_issue_list(tmp_path: Path) -> None:
    result = run_r8(make_build(tmp_path, [V_LIST]))
    assert PROJECT_LIST in counted_keys(result)


@pytest.mark.criterion("R8-no-false-positives")
def test_clean_build_reports_only_the_legacy_list(tmp_path: Path) -> None:
    result = run_r8(make_build(tmp_path))
    assert counted_keys(result) == {LEGACY}


@pytest.mark.criterion("R8-no-false-positives")
def test_lookup_violation_is_reported_only_on_issue_endpoints(tmp_path: Path) -> None:
    result = run_r8(make_build(tmp_path, [V_GET]))
    expected = {(endpoint, "deleted_path") for endpoint in V_GET_ENDPOINTS} | {LEGACY}
    assert counted_keys(result) == expected


@pytest.mark.criterion("R8-baseline")
def test_baseline_counts_only_new_findings(tmp_path: Path) -> None:
    from shipharness.checks import mark_baseline

    baseline = run_r8(make_build(tmp_path / "checkpoint"))
    current = run_r8(make_build(tmp_path / "arm", [V_LIST]))
    marked = mark_baseline(current, baseline)
    assert new_keys(marked) == {PROJECT_LIST}
    assert marked.new_violations == 1
    assert marked.baseline_violations == 1
    assert not marked.passed
