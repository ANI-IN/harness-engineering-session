"""F5 guards: single-issue transitions and issue creation keep working."""

from __future__ import annotations

from hidden_support import auth


def test_single_transition_still_works(client, acme) -> None:
    etag = client.get(f"/issues/{acme.issues[0]}", headers=auth(acme.member)).headers["ETag"]
    response = client.post(
        f"/issues/{acme.issues[0]}/transition",
        json={"status": "in_progress"},
        headers={**auth(acme.member), "If-Match": etag},
    )
    assert response.status_code == 200


def test_open_to_done_is_still_refused(client, acme) -> None:
    response = client.post(
        f"/issues/{acme.issues[0]}/transition",
        json={"status": "done"},
        headers={**auth(acme.member), "If-Match": '"1"'},
    )
    assert response.status_code == 422


def test_creating_an_issue_still_works(client, acme) -> None:
    response = client.post(
        f"/projects/{acme.projects[0]}/issues", json={"title": "Plain"}, headers=auth(acme.member)
    )
    assert response.status_code == 201
