"""R3 conventions (Schemathesis), R6 layering (import-linter), R7 migrations (Alembic)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from shipharness.checks import CheckContext, CheckResult, get_check
from shipharness.checks.adapter import TeamTrackAdapter
from shipharness.checks.builtin import load_builtin_checks
from tests.unit.checks import seeds

load_builtin_checks()


def run(name: str, build: Path, seed: int = 7, **params: object) -> CheckResult:
    ctx = CheckContext(
        checkpoint="m1-base",
        feature_id="F1",
        seed=seed,
        exemptions=TeamTrackAdapter().exemptions("m1-base"),
        params=dict(params),
    )
    return get_check(name).run(build, ctx)


def keys(result: CheckResult) -> set[tuple[str | None, str]]:
    return {(f.endpoint, f.detail_key) for f in result.findings if f.counted}


# R3 ------------------------------------------------------------------------------------------


def test_r3_base_passes_and_records_the_seed(base_build: Path) -> None:
    result = run("r3_conventions", base_build, seed=11)
    assert keys(result) == set()
    assert result.seed == 11
    assert result.total_probes > 100
    exempt = {(f.endpoint, f.detail_key) for f in result.findings if not f.counted}
    assert ("GET /v1/issues", "bare_array") in exempt
    assert ("GET /v1/issues", "offset_pagination") in exempt


def test_r3_catches_a_broken_error_envelope(make_build: Callable[[], Path]) -> None:
    result = run("r3_conventions", seeds.r3_bad_error_envelope(make_build()), r3_max_examples=5)
    assert ("GET /issues/{issue_id}", "error_envelope") in keys(result)
    assert result.passed is False


def test_r3_catches_a_new_list_copying_the_legacy_pattern(
    make_build: Callable[[], Path],
) -> None:
    result = run("r3_conventions", seeds.r3_bare_list(make_build()), r3_max_examples=5)
    assert {
        ("GET /projects-archive", "bare_array"),
        ("GET /projects-archive", "offset_pagination"),
    } <= keys(result)


def test_r3_is_deterministic_for_a_seed(base_build: Path) -> None:
    first = run("r3_conventions", base_build, seed=3, r3_max_examples=5)
    second = run("r3_conventions", base_build, seed=3, r3_max_examples=5)
    assert first.total_probes == second.total_probes


# R6 ------------------------------------------------------------------------------------------


def test_r6_base_keeps_the_layering_contract(base_build: Path) -> None:
    result = run("r6_layering", base_build)
    assert result.passed is True
    assert result.findings == []


def test_r6_catches_api_importing_db(make_build: Callable[[], Path]) -> None:
    result = run("r6_layering", seeds.r6_api_imports_db(make_build()))
    assert result.passed is False
    assert any("app.api.health -> app.db" in f.detail_key for f in result.findings)


def test_r6_ignores_a_weakened_contract_in_the_build(make_build: Callable[[], Path]) -> None:
    build = seeds.r6_api_imports_db(make_build())
    (build / ".importlinter").write_text("[importlinter]\nroot_package = app\n", encoding="utf-8")
    assert run("r6_layering", build).passed is False


# R7 ------------------------------------------------------------------------------------------


def test_r7_base_has_one_head_and_upgrades(base_build: Path) -> None:
    result = run("r7_migrations", base_build)
    assert result.passed is True, result.findings
    assert result.total_probes == 2


def test_r7_catches_two_heads(make_build: Callable[[], Path]) -> None:
    result = run("r7_migrations", seeds.r7_two_heads(make_build()))
    assert "heads" in {f.detail_key for f in result.findings if f.counted}
    assert "2 heads" in next(f.detail for f in result.findings if f.detail_key == "heads")


def test_r7_catches_a_failing_upgrade(make_build: Callable[[], Path]) -> None:
    result = run("r7_migrations", seeds.r7_broken_upgrade(make_build()))
    assert {f.detail_key for f in result.findings if f.counted} == {"upgrade"}
