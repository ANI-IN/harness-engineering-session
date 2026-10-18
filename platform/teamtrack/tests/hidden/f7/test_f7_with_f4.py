"""F7 combined with F4 (issue history): label changes are audit entries of the issue."""

from __future__ import annotations

from hidden_support import auth

BUG, DOCS = 1, 3


def history(client, user_id: int, issue_id: int) -> list[str]:  # type: ignore[no-untyped-def]
    items = client.get(f"/issues/{issue_id}/history", headers=auth(user_id)).json()["items"]
    return [entry["action"] for entry in items]


def test_label_change_is_in_the_issue_history(client, acme) -> None:
    client.post(
        f"/issues/{acme.issues[0]}/labels", json={"label_id": DOCS}, headers=auth(acme.member)
    )
    assert history(client, acme.member, acme.issues[0]) == ["issue.label_add"]


def test_label_removal_is_in_the_issue_history(client, acme) -> None:
    client.delete(f"/issues/{acme.issues[1]}/labels/{BUG}", headers=auth(acme.member))
    assert history(client, acme.member, acme.issues[1]) == ["issue.label_remove"]
