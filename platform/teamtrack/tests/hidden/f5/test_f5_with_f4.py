"""F5 combined with F4 (ETags) and F1 (search): bulk close is a real change to each issue."""

from __future__ import annotations

from hidden_support import auth


def start(client, o, issue_id: int) -> str:  # type: ignore[no-untyped-def]
    response = client.post(
        f"/issues/{issue_id}/transition",
        json={"status": "in_progress"},
        headers={**auth(o.member), "If-Match": '"1"'},
    )
    return response.headers["ETag"]


def close(client, o, issue_ids: list[int]):  # type: ignore[no-untyped-def]
    return client.post(
        f"/projects/{o.projects[0]}/issues/bulk-close",
        json={"issue_ids": issue_ids},
        headers=auth(o.member),
    )


def test_bulk_close_moves_the_etag(client, acme) -> None:
    start(client, acme, acme.issues[0])
    close(client, acme, [acme.issues[0]])
    assert client.get(f"/issues/{acme.issues[0]}", headers=auth(acme.member)).headers["ETag"] == (
        '"3"'
    )


def test_etag_from_before_the_bulk_close_is_stale(client, acme) -> None:
    etag = start(client, acme, acme.issues[0])
    close(client, acme, [acme.issues[0]])
    response = client.patch(
        f"/issues/{acme.issues[0]}",
        json={"title": "Late edit"},
        headers={**auth(acme.member), "If-Match": etag},
    )
    assert response.status_code == 412


def test_search_finds_closed_issues_as_done(client, acme) -> None:
    start(client, acme, acme.issues[0])
    start(client, acme, acme.issues[1])
    close(client, acme, [acme.issues[0], acme.issues[1]])
    items = client.get("/issues?status=done", headers=auth(acme.member)).json()["items"]
    assert [item["id"] for item in items] == [acme.issues[0], acme.issues[1]]
