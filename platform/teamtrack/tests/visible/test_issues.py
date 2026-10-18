from __future__ import annotations

import pytest

from conftest import auth, error_code


def create(client, o, **body):  # type: ignore[no-untyped-def]
    payload = {"title": "Login fails", **body}
    return client.post(f"/projects/{o.projects[0]}/issues", json=payload, headers=auth(o.member))


def test_create_issue_defaults(client, acme) -> None:
    response = create(client, acme)
    assert response.status_code == 201
    issue = response.json()
    assert issue["status"] == "open"
    assert issue["priority"] == "medium"
    assert issue["version"] == 1
    assert issue["project_id"] == acme.projects[0]
    assert issue["org_id"] == acme.org_id
    assert issue["created_by"] == acme.member


def test_get_issue(client, acme) -> None:
    response = client.get(f"/issues/{acme.issues[0]}", headers=auth(acme.viewer))
    assert response.status_code == 200
    assert response.json()["id"] == acme.issues[0]


def test_patch_updates_fields_and_increments_version(client, acme) -> None:
    issue_id = acme.issues[0]
    response = client.patch(
        f"/issues/{issue_id}", json={"title": "New", "priority": "high"}, headers=auth(acme.member)
    )
    assert response.status_code == 200
    assert response.json()["title"] == "New"
    assert response.json()["priority"] == "high"
    assert response.json()["version"] == 2


def test_patch_with_invalid_priority_is_422(client, acme) -> None:
    response = client.patch(
        f"/issues/{acme.issues[0]}", json={"priority": "urgent"}, headers=auth(acme.member)
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("path", "ok"),
    [
        (["in_progress"], True),
        (["in_progress", "done"], True),
        (["in_progress", "open"], True),
        (["done"], False),
        (["in_progress", "done", "in_progress"], False),
        (["in_progress", "done", "open"], True),
    ],
)
def test_transitions(client, acme, path: list[str], ok: bool) -> None:
    issue_id = acme.issues[2]
    last = None
    for status in path:
        last = client.post(
            f"/issues/{issue_id}/transition", json={"status": status}, headers=auth(acme.member)
        )
    assert last is not None
    if ok:
        assert last.status_code == 200
        assert last.json()["status"] == path[-1]
    else:
        assert last.status_code == 422
        assert error_code(last) == "invalid_transition"


def test_assign_and_unassign(client, acme) -> None:
    issue_id = acme.issues[3]
    response = client.post(
        f"/issues/{issue_id}/assign", json={"assignee_id": acme.viewer}, headers=auth(acme.member)
    )
    assert response.json()["assignee_id"] == acme.viewer
    response = client.post(
        f"/issues/{issue_id}/assign", json={"assignee_id": None}, headers=auth(acme.member)
    )
    assert response.json()["assignee_id"] is None


def test_soft_deleted_issue_disappears(client, acme) -> None:
    issue_id = acme.issues[4]
    assert client.delete(f"/issues/{issue_id}", headers=auth(acme.member)).status_code == 204
    assert client.get(f"/issues/{issue_id}", headers=auth(acme.member)).status_code == 404
    listed = client.get(
        f"/projects/{acme.projects[0]}/issues?limit=100", headers=auth(acme.member)
    ).json()["items"]
    assert issue_id not in {i["id"] for i in listed}


def test_soft_deleted_issue_cannot_be_updated(client, acme) -> None:
    issue_id = acme.issues[5]
    client.delete(f"/issues/{issue_id}", headers=auth(acme.member))
    response = client.patch(f"/issues/{issue_id}", json={"title": "x"}, headers=auth(acme.member))
    assert response.status_code == 404


def test_create_issue_in_archived_project_is_404(client, acme) -> None:
    client.delete(f"/projects/{acme.projects[1]}", headers=auth(acme.admin))
    response = client.post(
        f"/projects/{acme.projects[1]}/issues", json={"title": "x"}, headers=auth(acme.member)
    )
    assert response.status_code == 404


def test_title_is_required(client, acme) -> None:
    response = client.post(
        f"/projects/{acme.projects[0]}/issues", json={}, headers=auth(acme.member)
    )
    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_unknown_issue_is_404(client, acme) -> None:
    assert client.get("/issues/99999", headers=auth(acme.member)).status_code == 404
