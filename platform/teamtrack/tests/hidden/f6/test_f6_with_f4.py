"""F6 combined with F4 (history, ETags): watching is recorded on the issue, not as an edit."""

from __future__ import annotations

from hidden_support import auth


def test_watch_appears_in_the_issue_history(client, acme) -> None:
    client.put(f"/issues/{acme.issues[4]}/watchers/me", headers=auth(acme.admin))
    items = client.get(f"/issues/{acme.issues[4]}/history", headers=auth(acme.member)).json()
    assert [entry["action"] for entry in items["items"]] == ["watcher.add"]


def test_watched_issue_in_my_list_shows_the_current_version(client, acme) -> None:
    client.patch(
        f"/issues/{acme.issues[0]}",
        json={"title": "Edited while watched"},
        headers={**auth(acme.admin), "If-Match": '"1"'},
    )
    items = client.get("/me/watching", headers=auth(acme.member)).json()["items"]
    first = next(item for item in items if item["id"] == acme.issues[0])
    assert (first["title"], first["version"]) == ("Edited while watched", 2)
