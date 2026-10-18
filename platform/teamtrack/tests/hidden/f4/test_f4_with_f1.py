"""F4 combined with F1 (org-wide search): search shows the version that the ETag names."""

from __future__ import annotations

from hidden_support import auth


def test_search_version_matches_the_etag_after_a_write(client, acme) -> None:
    client.patch(
        f"/issues/{acme.issues[0]}",
        json={"title": "Login page fixed"},
        headers={**auth(acme.member), "If-Match": '"1"'},
    )
    etag = client.get(f"/issues/{acme.issues[0]}", headers=auth(acme.member)).headers["ETag"]
    item = client.get("/issues?q=login page fixed", headers=auth(acme.member)).json()["items"][0]
    assert f'"{item["version"]}"' == etag == '"2"'


def test_stale_write_is_not_visible_in_search(client, acme) -> None:
    edit = {**auth(acme.member), "If-Match": '"1"'}
    client.patch(f"/issues/{acme.issues[0]}", json={"title": "Kept title"}, headers=edit)
    client.patch(f"/issues/{acme.issues[0]}", json={"title": "Lost title"}, headers=edit)
    assert client.get("/issues?q=lost title", headers=auth(acme.member)).json()["items"] == []
