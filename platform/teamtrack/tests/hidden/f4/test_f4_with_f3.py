"""F4 combined with F3 (idempotent create): a replayed create is version 1 with one ETag."""

from __future__ import annotations

from hidden_support import auth


def test_replayed_create_is_edited_once_with_its_etag(client, acme) -> None:
    headers = {**auth(acme.member), "Idempotency-Key": "f4-f3"}
    path = f"/projects/{acme.projects[0]}/issues"
    issue = client.post(path, json={"title": "Keyed"}, headers=headers).json()
    client.post(path, json={"title": "Keyed"}, headers=headers)
    etag = client.get(f"/issues/{issue['id']}", headers=auth(acme.member)).headers["ETag"]
    assert etag == '"1"'
    edit = {**auth(acme.member), "If-Match": etag}
    assert (
        client.patch(f"/issues/{issue['id']}", json={"title": "A"}, headers=edit).status_code == 200
    )
    assert (
        client.patch(f"/issues/{issue['id']}", json={"title": "B"}, headers=edit).status_code == 412
    )


def test_replayed_create_has_one_creation_in_history(client, acme) -> None:
    headers = {**auth(acme.member), "Idempotency-Key": "f4-f3-h"}
    path = f"/projects/{acme.projects[0]}/issues"
    issue = client.post(path, json={"title": "Keyed"}, headers=headers).json()
    client.post(path, json={"title": "Keyed"}, headers=headers)
    items = client.get(f"/issues/{issue['id']}/history", headers=auth(acme.member)).json()["items"]
    assert [entry["action"] for entry in items] == ["issue.create"]
