"""R1: no org sees another org's data. Acme users get 404 for every Globex resource."""

from __future__ import annotations

import pytest

from conftest import auth, error_code


def globex_targets(g):  # type: ignore[no-untyped-def]
    """(method, path, json body) for every endpoint that takes an ID, pointed at Globex data."""
    project, issue, user = g.projects[0], g.issues[0], g.member
    return [
        ("GET", f"/users/{user}", None),
        ("PATCH", f"/users/{user}", {"name": "x"}),
        ("GET", f"/projects/{project}", None),
        ("PATCH", f"/projects/{project}", {"name": "x"}),
        ("DELETE", f"/projects/{project}", None),
        ("GET", f"/projects/{project}/members", None),
        ("POST", f"/projects/{project}/members", {"user_id": g.member}),
        ("DELETE", f"/projects/{project}/members/{g.member}", None),
        ("GET", f"/projects/{project}/issues", None),
        ("POST", f"/projects/{project}/issues", {"title": "x"}),
        ("GET", f"/issues/{issue}", None),
        ("PATCH", f"/issues/{issue}", {"title": "x"}),
        ("POST", f"/issues/{issue}/assign", {"assignee_id": None}),
        ("POST", f"/issues/{issue}/transition", {"status": "in_progress"}),
        ("DELETE", f"/issues/{issue}", None),
    ]


TARGET_COUNT = 15


@pytest.mark.parametrize("index", range(TARGET_COUNT))
def test_acme_admin_gets_404_for_globex_resources(client, acme, globex, index: int) -> None:
    targets = globex_targets(globex)
    assert len(targets) == TARGET_COUNT
    method, path, body = targets[index]
    response = client.request(method, path, json=body, headers=auth(acme.admin))
    assert response.status_code == 404, (method, path, response.text)
    assert error_code(response) == "not_found"


@pytest.mark.parametrize(
    ("path", "field"),
    [("/users", "org_id"), ("/projects", "org_id"), ("/audit", "org_id")],
)
def test_lists_contain_only_own_org(client, acme, path: str, field: str) -> None:
    response = client.get(f"{path}?limit=100", headers=auth(acme.admin))
    assert response.status_code == 200
    assert {item[field] for item in response.json()["items"]} <= {acme.org_id}


def test_project_issue_list_contains_only_own_org(client, acme) -> None:
    response = client.get(
        f"/projects/{acme.projects[0]}/issues?limit=100", headers=auth(acme.admin)
    )
    assert {i["org_id"] for i in response.json()["items"]} == {acme.org_id}


def test_assigning_a_user_from_another_org_is_rejected(client, acme, globex) -> None:
    response = client.post(
        f"/issues/{acme.issues[0]}/assign",
        json={"assignee_id": globex.member},
        headers=auth(acme.member),
    )
    assert response.status_code == 422
    assert error_code(response) == "invalid_assignee"


def test_adding_a_member_from_another_org_is_rejected(client, acme, globex) -> None:
    response = client.post(
        f"/projects/{acme.projects[0]}/members",
        json={"user_id": globex.member},
        headers=auth(acme.admin),
    )
    assert response.status_code == 422
    assert error_code(response) == "invalid_user"
