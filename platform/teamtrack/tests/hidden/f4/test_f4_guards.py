"""F4 guards: behaviour that must not break while adding optimistic concurrency."""

from __future__ import annotations

from hidden_support import auth


def test_viewer_still_cannot_patch(client, acme) -> None:
    response = client.patch(
        f"/issues/{acme.issues[0]}",
        json={"title": "x"},
        headers={**auth(acme.viewer), "If-Match": '"1"'},
    )
    assert response.status_code == 403


def test_issue_creation_does_not_need_if_match(client, acme) -> None:
    response = client.post(
        f"/projects/{acme.projects[0]}/issues", json={"title": "New"}, headers=auth(acme.member)
    )
    assert response.status_code == 201
    assert response.json()["version"] == 1


def test_deleting_an_issue_does_not_need_if_match(client, acme) -> None:
    assert client.delete(f"/issues/{acme.issues[0]}", headers=auth(acme.member)).status_code == 204
