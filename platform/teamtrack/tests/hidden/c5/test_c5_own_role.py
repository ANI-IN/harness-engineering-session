"""C5 hidden tests: admins cannot change their own role (spec: docs/features/c5.md)."""

from __future__ import annotations

from hidden_support import auth, error_code


def audit_count(client, admin: int) -> int:  # type: ignore[no-untyped-def]
    count, cursor = 0, None
    while True:
        url = "/audit?limit=100" + (f"&cursor={cursor}" if cursor else "")
        body = client.get(url, headers=auth(admin)).json()
        count += len(body["items"])
        cursor = body["next_cursor"]
        if cursor is None:
            return count


def test_admin_cannot_demote_themselves(client, acme) -> None:
    response = client.patch(
        f"/users/{acme.admin}", json={"role": "viewer"}, headers=auth(acme.admin)
    )
    assert response.status_code == 422
    assert error_code(response) == "cannot_change_own_role"


def test_rejected_change_leaves_the_role_unchanged(client, acme) -> None:
    client.patch(f"/users/{acme.admin}", json={"role": "member"}, headers=auth(acme.admin))
    assert client.get(f"/users/{acme.admin}", headers=auth(acme.admin)).json()["role"] == "admin"


def test_rejected_change_adds_no_audit_row(client, acme) -> None:
    before = audit_count(client, acme.admin)
    client.patch(f"/users/{acme.admin}", json={"role": "member"}, headers=auth(acme.admin))
    assert audit_count(client, acme.admin) == before


def test_rule_applies_in_every_org(client, globex) -> None:
    response = client.patch(
        f"/users/{globex.admin}", json={"role": "member"}, headers=auth(globex.admin)
    )
    assert response.status_code == 422
    assert error_code(response) == "cannot_change_own_role"


def test_name_and_role_together_change_nothing(client, acme) -> None:
    response = client.patch(
        f"/users/{acme.admin}",
        json={"name": "Someone Else", "role": "viewer"},
        headers=auth(acme.admin),
    )
    assert response.status_code == 422
    user = client.get(f"/users/{acme.admin}", headers=auth(acme.admin)).json()
    assert user["name"] != "Someone Else"
    assert user["role"] == "admin"


def test_own_name_still_changes_but_own_role_does_not(client, acme) -> None:
    renamed = client.patch(
        f"/users/{acme.admin}", json={"name": "Ada Admin"}, headers=auth(acme.admin)
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Ada Admin"
    demoted = client.patch(
        f"/users/{acme.admin}", json={"role": "viewer"}, headers=auth(acme.admin)
    )
    assert demoted.status_code == 422
