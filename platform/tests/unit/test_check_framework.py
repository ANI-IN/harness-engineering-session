from __future__ import annotations

from pathlib import Path

import pytest

from shipharness.checks import (
    CheckContext,
    CheckResult,
    Finding,
    ProbeClient,
    discover_endpoints,
    get_check,
    load_app,
    mark_baseline,
    register_check,
)
from shipharness.layout import find_repo_root

TEAMTRACK = find_repo_root(Path(__file__)) / "platform" / "teamtrack"


@pytest.fixture(scope="module")
def app(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    return load_app(TEAMTRACK, tmp_path_factory.mktemp("db") / "probe.db")


def test_discovers_templated_paths_and_write_methods(app) -> None:  # type: ignore[no-untyped-def]
    endpoints = {(e.method, e.path): e for e in discover_endpoints(app)}
    issue_get = endpoints[("GET", "/issues/{issue_id}")]
    assert issue_get.path_params == ["issue_id"]
    assert issue_get.is_write is False
    for method in ("PATCH", "DELETE"):
        assert endpoints[(method, "/issues/{issue_id}")].is_write is True
    assert endpoints[("POST", "/projects")].is_write is True


def test_discovery_skips_public_endpoints_and_board(app) -> None:  # type: ignore[no-untyped-def]
    paths = {e.path for e in discover_endpoints(app)}
    assert "/health" not in paths
    assert "/auth/login" not in paths
    assert not any(p.startswith("/board") for p in paths)
    assert "/v1/issues" in paths


def test_discovery_can_include_public_endpoints(app) -> None:  # type: ignore[no-untyped-def]
    paths = {e.path for e in discover_endpoints(app, include_public=True)}
    assert {"/health", "/auth/login"} <= paths


def test_discovery_reports_idempotency_header(app) -> None:  # type: ignore[no-untyped-def]
    endpoints = {(e.method, e.path): e for e in discover_endpoints(app)}
    assert endpoints[("POST", "/projects")].accepts_idempotency_key is True
    assert endpoints[("POST", "/projects/{project_id}/issues")].accepts_idempotency_key is False


def test_probe_client_authenticates_as_seeded_user(app) -> None:  # type: ignore[no-untyped-def]
    response = ProbeClient(app, user_id=1).request("GET", "/me")
    assert response.status_code == 200
    assert response.json()["id"] == 1


def finding(endpoint: str, rule: str = "R1") -> Finding:
    return Finding(
        rule=rule, severity="violation", endpoint=endpoint, detail="status 200", baseline=False
    )


def result(*findings: Finding) -> CheckResult:
    return CheckResult(
        check="r1_tenant",
        passed=not findings,
        new_violations=len(findings),
        baseline_violations=0,
        total_probes=10,
        findings=list(findings),
        duration_ms=1,
    )


def test_mark_baseline_counts_only_new_violations() -> None:
    baseline = result(finding("GET /v1/issues"))
    current = result(finding("GET /v1/issues"), finding("GET /issues"))
    marked = mark_baseline(current, baseline)
    assert marked.new_violations == 1
    assert marked.baseline_violations == 1
    assert marked.passed is False
    assert [f.endpoint for f in marked.findings if not f.baseline] == ["GET /issues"]
    assert marked.findings[0].baseline is False  # new findings first


def test_mark_baseline_passes_when_only_baseline_findings() -> None:
    marked = mark_baseline(result(finding("GET /v1/issues")), result(finding("GET /v1/issues")))
    assert marked.passed is True
    assert marked.new_violations == 0


def test_mark_baseline_without_baseline_treats_all_as_new() -> None:
    marked = mark_baseline(result(finding("GET /x")), None)
    assert marked.new_violations == 1


def test_registry_rejects_duplicate_names() -> None:
    @register_check
    class Dummy:
        name = "dummy_check_for_test"

        def run(self, build_dir: Path, ctx: CheckContext) -> CheckResult:
            return result()

    assert get_check("dummy_check_for_test").name == "dummy_check_for_test"
    with pytest.raises(ValueError, match="already registered"):

        @register_check
        class Again:
            name = "dummy_check_for_test"

            def run(self, build_dir: Path, ctx: CheckContext) -> CheckResult:
                return result()


def test_check_context_progress_callback_is_called() -> None:
    calls: list[tuple[int, int, str]] = []
    ctx = CheckContext(
        checkpoint="m1-base",
        feature_id="F1",
        seed=7,
        progress=lambda done, total, label: calls.append((done, total, label)),
    )
    ctx.progress(3, 10, "R1 probes 3/10")
    assert calls == [(3, 10, "R1 probes 3/10")]


def test_unauthenticated_endpoints_added_by_an_agent_are_discovered(tmp_path: Path) -> None:
    leaky = load_app(TEAMTRACK, tmp_path / "leaky.db")

    def leaky_issue(issue_id: int) -> dict[str, int]:
        return {"id": issue_id}

    leaky.add_api_route("/issues/{issue_id}/raw", leaky_issue, methods=["GET"])
    leaky.openapi_schema = None
    found = {(e.method, e.path): e for e in discover_endpoints(leaky)}
    assert ("GET", "/issues/{issue_id}/raw") in found
    assert found[("GET", "/issues/{issue_id}/raw")].requires_auth is False
    assert ("GET", "/health") not in found
