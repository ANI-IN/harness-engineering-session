"""F6: issue watchers."""

from __future__ import annotations

from conftest import auth, error_code


def watchers(client, user_id: int, issue_id: int) -> list[int]:  # type: ignore[no-untyped-def]
    response = client.get(f"/issues/{issue_id}/watchers?limit=100", headers=auth(user_id))
    assert response.status_code == 200, response.text
    return [w["user_id"] for w in response.json()["items"]]


def watching(client, user_id: int) -> list[int]:  # type: ignore[no-untyped-def]
    response = client.get("/me/watching?limit=100", headers=auth(user_id))
    assert response.status_code == 200, response.text
    return [i["id"] for i in response.json()["items"]]


def audit_actions(client, o) -> list[str]:  # type: ignore[no-untyped-def]
    items = client.get("/audit?limit=100", headers=auth(o.admin)).json()["items"]
    return [item["action"] for item in items]


def test_seeded_watchers(client, acme) -> None:
    assert watchers(client, acme.viewer, acme.issues[0]) == [acme.member]
    assert watching(client, acme.member) == [acme.issues[0], acme.issues[1]]


def test_watch_and_unwatch_myself(client, acme) -> None:
    issue = acme.issues[5]
    assert client.put(f"/issues/{issue}/watchers/me", headers=auth(acme.admin)).status_code == 204
    assert watchers(client, acme.admin, issue) == [acme.admin]
    assert issue in watching(client, acme.admin)
    response = client.delete(f"/issues/{issue}/watchers/me", headers=auth(acme.admin))
    assert response.status_code == 204
    assert watchers(client, acme.admin, issue) == []


def test_watching_twice_changes_nothing_and_adds_no_audit_row(client, acme) -> None:
    issue = acme.issues[5]
    client.put(f"/issues/{issue}/watchers/me", headers=auth(acme.member))
    before = audit_actions(client, acme)
    assert client.put(f"/issues/{issue}/watchers/me", headers=auth(acme.member)).status_code == 204
    assert audit_actions(client, acme) == before
    assert watchers(client, acme.member, issue) == [acme.member]


def test_watch_and_unwatch_each_add_one_audit_row(client, acme) -> None:
    issue = acme.issues[5]
    before = audit_actions(client, acme)
    client.put(f"/issues/{issue}/watchers/me", headers=auth(acme.member))
    client.delete(f"/issues/{issue}/watchers/me", headers=auth(acme.member))
    assert audit_actions(client, acme)[len(before) :] == ["watcher.add", "watcher.remove"]


def test_viewer_cannot_watch(client, acme) -> None:
    response = client.put(f"/issues/{acme.issues[0]}/watchers/me", headers=auth(acme.viewer))
    assert response.status_code == 403
    assert error_code(response) == "forbidden"


def test_other_orgs_issue_is_404(client, acme, globex) -> None:
    issue = globex.issues[0]
    assert client.put(f"/issues/{issue}/watchers/me", headers=auth(acme.member)).status_code == 404
    assert client.get(f"/issues/{issue}/watchers", headers=auth(acme.member)).status_code == 404


def test_deleted_issue_is_404_and_leaves_my_watching_list(client, acme) -> None:
    client.delete(f"/issues/{acme.issues[0]}", headers=auth(acme.member))
    response = client.get(f"/issues/{acme.issues[0]}/watchers", headers=auth(acme.member))
    assert response.status_code == 404
    assert watching(client, acme.member) == [acme.issues[1]]


def test_admin_adds_and_removes_a_user_of_the_org(client, acme) -> None:
    issue = acme.issues[6]
    path = f"/issues/{issue}/watchers/{acme.viewer}"
    assert client.put(path, headers=auth(acme.admin)).status_code == 204
    assert watching(client, acme.viewer) == [issue]
    assert client.delete(path, headers=auth(acme.admin)).status_code == 204
    assert watching(client, acme.viewer) == []


def test_admin_cannot_add_a_user_of_another_org(client, acme, globex) -> None:
    response = client.put(
        f"/issues/{acme.issues[0]}/watchers/{globex.member}", headers=auth(acme.admin)
    )
    assert response.status_code == 404
    assert error_code(response) == "not_found"


def test_member_cannot_manage_other_watchers(client, acme) -> None:
    response = client.put(
        f"/issues/{acme.issues[0]}/watchers/{acme.viewer}", headers=auth(acme.member)
    )
    assert response.status_code == 403


def test_watching_list_uses_the_envelope_and_cursor(client, acme) -> None:
    first = client.get("/me/watching?limit=1", headers=auth(acme.member)).json()
    assert set(first) == {"items", "next_cursor"}
    assert [i["id"] for i in first["items"]] == [acme.issues[0]]
    rest = client.get(
        f"/me/watching?limit=1&cursor={first['next_cursor']}", headers=auth(acme.member)
    ).json()
    assert [i["id"] for i in rest["items"]] == [acme.issues[1]]
