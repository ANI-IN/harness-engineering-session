"""F2 combined with F1 (org-wide search): issues found by search take comments."""

from __future__ import annotations

from hidden_support import auth


def test_comment_on_an_issue_found_by_search(client, acme) -> None:
    found = client.get("/issues?q=footer", headers=auth(acme.member)).json()["items"]
    issue_id = found[0]["id"]
    response = client.post(
        f"/issues/{issue_id}/comments",
        json={"body": "Footer link fixed"},
        headers=auth(acme.member),
    )
    assert response.status_code == 201
    assert response.json()["issue_id"] == issue_id


def test_search_and_comments_agree_on_deleted_issues(client, acme) -> None:
    before = client.get(f"/issues/{acme.issues[0]}/comments", headers=auth(acme.member))
    assert before.status_code == 200
    client.delete(f"/issues/{acme.issues[0]}", headers=auth(acme.member))
    found = client.get("/issues?q=login", headers=auth(acme.member)).json()["items"]
    assert acme.issues[0] not in [item["id"] for item in found]
    response = client.get(f"/issues/{acme.issues[0]}/comments", headers=auth(acme.member))
    assert response.status_code == 404
