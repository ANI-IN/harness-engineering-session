"""F1 guards: behaviour that must not break while adding GET /issues (pass before and after)."""

from __future__ import annotations

from hidden_support import auth


def test_project_issue_list_still_works(client, acme) -> None:
    response = client.get(
        f"/projects/{acme.projects[0]}/issues?limit=100", headers=auth(acme.member)
    )
    assert [item["id"] for item in response.json()["items"]] == list(acme.issues[:10])


def test_single_issue_still_works(client, acme) -> None:
    response = client.get(f"/issues/{acme.issues[0]}", headers=auth(acme.viewer))
    assert response.status_code == 200
    assert response.json()["id"] == acme.issues[0]


def test_single_issue_of_another_org_is_still_404(client, acme, globex) -> None:
    assert client.get(f"/issues/{globex.issues[0]}", headers=auth(acme.admin)).status_code == 404
