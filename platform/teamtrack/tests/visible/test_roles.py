"""R2: viewers cannot write; admin-only endpoints reject members."""

from __future__ import annotations

import pytest

from conftest import auth, error_code


def own_writes(o):  # type: ignore[no-untyped-def]
    project, issue = o.projects[0], o.issues[0]
    return [
        ("POST", "/users", {"email": "new@x.test", "name": "New", "role": "member"}),
        ("PATCH", f"/users/{o.member}", {"name": "Renamed"}),
        ("POST", "/projects", {"name": "New", "key": "NEW"}),
        ("PATCH", f"/projects/{project}", {"name": "Renamed"}),
        ("DELETE", f"/projects/{project}", None),
        ("POST", f"/projects/{project}/members", {"user_id": o.member}),
        ("DELETE", f"/projects/{project}/members/{o.member}", None),
        ("POST", f"/projects/{project}/issues", {"title": "New issue"}),
        ("PATCH", f"/issues/{issue}", {"title": "Renamed"}),
        ("POST", f"/issues/{issue}/assign", {"assignee_id": o.member}),
        ("POST", f"/issues/{issue}/transition", {"status": "in_progress"}),
        ("DELETE", f"/issues/{issue}", None),
    ]


WRITE_COUNT = 12


@pytest.mark.parametrize("index", range(WRITE_COUNT))
def test_viewer_writes_are_403(client, acme, index: int) -> None:
    writes = own_writes(acme)
    assert len(writes) == WRITE_COUNT
    method, path, body = writes[index]
    response = client.request(method, path, json=body, headers=auth(acme.viewer))
    assert response.status_code == 403, (method, path, response.text)
    assert error_code(response) == "forbidden"


ADMIN_ONLY = [0, 1, 4, 5, 6]  # users create/update, project archive, member add/remove


@pytest.mark.parametrize("index", ADMIN_ONLY)
def test_member_cannot_call_admin_only_endpoints(client, acme, index: int) -> None:
    method, path, body = own_writes(acme)[index]
    response = client.request(method, path, json=body, headers=auth(acme.member))
    assert response.status_code == 403
    assert error_code(response) == "forbidden"


def test_member_cannot_read_audit_log(client, acme) -> None:
    response = client.get("/audit", headers=auth(acme.member))
    assert response.status_code == 403


@pytest.mark.parametrize("path", ["/users", "/projects", "/me", "/orgs/current"])
def test_viewer_can_read(client, acme, path: str) -> None:
    assert client.get(path, headers=auth(acme.viewer)).status_code == 200
