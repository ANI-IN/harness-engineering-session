"""F7 guards: issue lists and issue creation keep working while labels are added."""

from __future__ import annotations

from hidden_support import auth


def test_project_issue_list_without_a_label_filter(client, acme) -> None:
    response = client.get(
        f"/projects/{acme.projects[0]}/issues?limit=100", headers=auth(acme.member)
    )
    assert len(response.json()["items"]) == 10


def test_issue_creation_still_works(client, acme) -> None:
    response = client.post(
        f"/projects/{acme.projects[0]}/issues", json={"title": "Plain"}, headers=auth(acme.member)
    )
    assert response.status_code == 201


def test_other_orgs_issue_is_still_404(client, acme, globex) -> None:
    assert client.get(f"/issues/{globex.issues[0]}", headers=auth(acme.member)).status_code == 404
