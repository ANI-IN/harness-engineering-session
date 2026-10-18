"""R1, R2, R4, R5: in-process HTTP probes against the TeamTrack base and seeded violations."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from shipharness.checks import CheckContext, CheckResult, get_check
from shipharness.checks.adapter import TeamTrackAdapter
from shipharness.checks.builtin import load_builtin_checks
from tests.unit.checks import seeds

load_builtin_checks()
BASE_EXEMPTIONS = TeamTrackAdapter().exemptions("m1-base")


def run(
    name: str,
    build: Path,
    exemptions: dict[str, list[str]] | None = None,
    progress: Callable[[int, int, str], None] | None = None,
) -> CheckResult:
    ctx = CheckContext(
        checkpoint="m1-base",
        feature_id="F1",
        exemptions=BASE_EXEMPTIONS if exemptions is None else exemptions,
    )
    if progress is not None:
        ctx.progress = progress
    return get_check(name).run(build, ctx)


def counted(result: CheckResult) -> list[tuple[str | None, str, str]]:
    return [(f.endpoint, f.severity, f.detail_key) for f in result.findings if f.counted]


# R1 ------------------------------------------------------------------------------------------


def test_r1_base_has_only_the_documented_legacy_leak(base_build: Path) -> None:
    calls: list[tuple[int, int, str]] = []
    result = run("r1_tenant", base_build, progress=lambda d, t, label: calls.append((d, t, label)))
    assert counted(result) == [("GET /v1/issues", "leak", "no_path")]
    assert result.total_probes > 50
    assert calls[-1] == (result.total_probes, result.total_probes, calls[-1][2])
    assert calls[-1][2].startswith("House rule 1 probes ")


def test_r1_catches_an_unauthenticated_cross_tenant_endpoint(
    make_build: Callable[[], Path],
) -> None:
    result = run("r1_tenant", seeds.r1_unauthenticated_leak(make_build()))
    raw = [f for f in result.findings if f.endpoint == "GET /issues/{issue_id}/raw"]
    assert {(f.detail_key, f.severity) for f in raw} == {
        ("foreign_path", "leak"),
        ("anonymous", "leak"),
    }
    assert result.passed is False


def test_r1_exemption_turns_findings_into_info(base_build: Path) -> None:
    result = run("r1_tenant", base_build, exemptions={"R1": ["GET /v1/issues"]})
    assert result.passed is True
    assert [f.severity for f in result.findings] == ["info"]


# R2 ------------------------------------------------------------------------------------------


def test_r2_base_viewers_get_403_on_every_write(base_build: Path) -> None:
    result = run("r2_roles", base_build)
    assert counted(result) == []
    assert result.total_probes >= 12


def test_r2_catches_viewers_writing(make_build: Callable[[], Path]) -> None:
    result = run("r2_roles", seeds.r2_viewers_can_write(make_build()))
    endpoints = {f.endpoint for f in result.findings if f.counted}
    assert "POST /projects/{project_id}/issues" in endpoints
    assert "PATCH /issues/{issue_id}" in endpoints
    assert "POST /users" not in endpoints  # admin-only writes still refuse viewers


# R4 ------------------------------------------------------------------------------------------


def test_r4_base_only_issue_create_duplicates_and_it_is_exempt(base_build: Path) -> None:
    result = run("r4_idempotency", base_build)
    assert counted(result) == []
    info = [f for f in result.findings if not f.counted]
    assert [(f.endpoint, f.detail_key) for f in info] == [
        ("POST /projects/{project_id}/issues", "duplicate")
    ]


def test_r4_without_the_exemption_catches_duplicate_issues(base_build: Path) -> None:
    result = run("r4_idempotency", base_build, exemptions={})
    assert counted(result) == [("POST /projects/{project_id}/issues", "violation", "duplicate")]


def test_r4_catches_a_replay_that_ignores_the_key(make_build: Callable[[], Path]) -> None:
    result = run("r4_idempotency", seeds.r4_no_idempotency_on_projects(make_build()))
    assert ("POST /projects", "violation", "replay_mismatch") in counted(result)


# R5 ------------------------------------------------------------------------------------------


def test_r5_base_every_write_adds_one_audit_row(base_build: Path) -> None:
    result = run("r5_audit", base_build)
    assert counted(result) == []
    assert result.total_probes >= 12


def test_r5_catches_writes_without_audit_rows(make_build: Callable[[], Path]) -> None:
    result = run("r5_audit", seeds.r5_no_audit(make_build()))
    keys = {(f.endpoint, f.detail_key) for f in result.findings if f.counted}
    assert ("POST /projects", "missing") in keys
    assert ("DELETE /issues/{issue_id}", "missing") in keys


@pytest.mark.parametrize("name", ["r1_tenant", "r2_roles", "r4_idempotency", "r5_audit"])
def test_http_checks_are_deterministic(base_build: Path, name: str) -> None:
    first, second = run(name, base_build), run(name, base_build)
    assert [f.detail for f in first.findings] == [f.detail for f in second.findings]
