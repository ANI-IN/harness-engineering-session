from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from shipharness.checks.adapter import TeamTrackAdapter, load_adapter
from shipharness.checks.discovery import discover_endpoints
from shipharness.checks.payloads import Payloads, fill_path


@pytest.fixture
def adapter() -> TeamTrackAdapter:
    return TeamTrackAdapter()


@pytest.fixture
def app(adapter: TeamTrackAdapter, base_build: Path, tmp_path: Path):  # type: ignore[no-untyped-def]
    return adapter.create_app(base_build, tmp_path / "a.db")


def test_teamtrack_ids_match_the_seed(adapter: TeamTrackAdapter) -> None:
    from app.seed import ACME, GLOBEX

    assert adapter.orgs() == ("acme", "globex")
    assert adapter.ids("acme")["issue_id"] == ACME.issues[0]
    assert adapter.ids("globex")["project_id"] == GLOBEX.projects[0]
    assert adapter.ids("globex")["user_id"] in (GLOBEX.admin, GLOBEX.member, GLOBEX.viewer)


def test_headers_authenticate_each_role(adapter: TeamTrackAdapter, app) -> None:  # type: ignore[no-untyped-def]
    client = TestClient(app)
    for org in adapter.orgs():
        for role in ("admin", "member", "viewer"):
            me = client.get("/me", headers=adapter.headers(org, role)).json()
            assert me["role"] == role


def test_audit_count_counts_rows_per_org(adapter: TeamTrackAdapter, app) -> None:  # type: ignore[no-untyped-def]
    before = adapter.audit_count(app, "acme")
    client = TestClient(app)
    response = client.patch(
        "/projects/1", json={"name": "Renamed"}, headers=adapter.headers("acme", "admin")
    )
    assert response.status_code == 200
    assert adapter.audit_count(app, "acme") == before + 1
    assert adapter.audit_count(app, "globex") == 0


def test_is_foreign_finds_other_org_data(adapter: TeamTrackAdapter) -> None:
    assert adapter.is_foreign([{"id": 21, "org_id": 2}], "globex")
    assert adapter.is_foreign({"items": [{"project_id": 3, "user_id": 4}]}, "globex")
    assert not adapter.is_foreign({"items": [{"id": 1, "org_id": 1}]}, "globex")
    assert not adapter.is_foreign({"error": {"code": "not_found", "message": "x"}}, "globex")


def test_issue_create_is_exempt_from_r4_until_f3(adapter: TeamTrackAdapter) -> None:
    assert "POST /projects/{project_id}/issues" in adapter.exemptions("m1-base")["R4"]
    assert "POST /projects/{project_id}/issues" in adapter.exemptions("m1-s3-start")["R4"]
    assert "R4" not in adapter.exemptions("m1-s4-start")
    assert "GET /v1/issues" in adapter.exemptions("m1-s4-start")["R3"]
    assert "R1" not in adapter.exemptions("m1-base")  # the legacy leak stays a baseline finding


def test_load_adapter_from_module_attr() -> None:
    loaded = load_adapter("shipharness.checks.adapter:TeamTrackAdapter")
    assert isinstance(loaded, TeamTrackAdapter)
    assert isinstance(load_adapter(None), TeamTrackAdapter)
    with pytest.raises(ValueError, match="module:attr"):
        load_adapter("no_colon_here")


def test_generated_bodies_are_accepted_for_every_write(adapter: TeamTrackAdapter, app) -> None:  # type: ignore[no-untyped-def]
    client = TestClient(app, raise_server_exceptions=False)
    payloads = Payloads(app.openapi())
    ids = adapter.ids("acme")
    writes = [e for e in discover_endpoints(app) if e.is_write and e.method != "DELETE"]
    assert len(writes) >= 9
    for endpoint in writes:
        body = payloads.body(endpoint, ids, adapter.body_overrides())
        response = client.request(
            endpoint.method,
            fill_path(endpoint.path, ids),
            json=body,
            headers=adapter.headers("acme", "admin"),
        )
        assert response.status_code != 422, (endpoint.label, body, response.text)


def test_generated_bodies_are_unique_per_call(app) -> None:  # type: ignore[no-untyped-def]
    payloads = Payloads(app.openapi())
    endpoint = next(e for e in discover_endpoints(app) if e.label == "POST /projects")
    first, second = payloads.body(endpoint, {}), payloads.body(endpoint, {})
    assert first["key"] != second["key"]


def test_fill_path_uses_names_then_the_resource_segment() -> None:
    ids = {"project_id": 3, "issue_id": 21, "user_id": 6}
    assert fill_path("/projects/{project_id}/members/{user_id}", ids) == "/projects/3/members/6"
    assert fill_path("/issues/{id}/comments", ids) == "/issues/21/comments"
    assert fill_path("/widgets/{widget_id}", ids) == "/widgets/3"


def test_issue_create_is_exempt_from_r4_at_the_alternate_checkpoints(
    adapter: TeamTrackAdapter,
) -> None:
    for checkpoint in ("m1-alt-a", "m1-alt-b"):
        assert "POST /projects/{project_id}/issues" in adapter.exemptions(checkpoint)["R4"]
    for checkpoint in ("m1-final-start", "m1-complete"):
        assert "R4" not in adapter.exemptions(checkpoint)


def test_r4_exemption_follows_the_checkpoint_definitions(adapter: TeamTrackAdapter) -> None:
    from shipharness.ab.checkpoints import load_checkpoints

    for name, checkpoint in load_checkpoints().items():
        exempt = "R4" in adapter.exemptions(name)
        assert exempt == ("f3" not in checkpoint.tasks), name


def test_feature_path_parameters_name_seeded_rows(adapter: TeamTrackAdapter) -> None:
    # F2 seeds comments 1-2 (Acme) and 3-4 (Globex); F7 seeds labels 1-3 and 4-6.
    assert (adapter.ids("acme")["comment_id"], adapter.ids("globex")["comment_id"]) == (1, 3)
    assert (adapter.ids("acme")["label_id"], adapter.ids("globex")["label_id"]) == (1, 4)
    assert fill_path("/comments/{comment_id}", adapter.ids("globex")) == "/comments/3"
    path = fill_path("/issues/{issue_id}/labels/{label_id}", adapter.ids("acme"))
    assert path == "/issues/1/labels/1"
