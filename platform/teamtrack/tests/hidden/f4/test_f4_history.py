"""F4 hidden tests: GET /issues/{issue_id}/history (spec: docs/features/f4.md)."""

from __future__ import annotations

from hidden_support import auth, error_code


def history(client, user_id: int, issue_id: int, query: str = "?limit=100"):  # type: ignore[no-untyped-def]
    return client.get(f"/issues/{issue_id}/history{query}", headers=auth(user_id))


def actions(client, user_id: int, issue_id: int) -> list[str]:  # type: ignore[no-untyped-def]
    response = history(client, user_id, issue_id)
    assert response.status_code == 200, response.text
    return [entry["action"] for entry in response.json()["items"]]


def write(client, user_id: int, issue_id: int, method: str, suffix: str, body: dict):  # type: ignore[no-untyped-def]
    etag = client.get(f"/issues/{issue_id}", headers=auth(user_id)).headers.get("ETag", '"1"')
    response = client.request(
        method,
        f"/issues/{issue_id}{suffix}",
        json=body,
        headers={**auth(user_id), "If-Match": etag},
    )
    assert response.status_code == 200, response.text


def new_issue(client, o) -> int:  # type: ignore[no-untyped-def]
    response = client.post(
        f"/projects/{o.projects[0]}/issues", json={"title": "Tracked"}, headers=auth(o.member)
    )
    return response.json()["id"]


def test_seeded_issue_has_an_empty_history(client, acme) -> None:
    assert history(client, acme.member, acme.issues[0]).json() == {"items": [], "next_cursor": None}


def test_new_issue_history_starts_with_its_creation(client, acme) -> None:
    assert actions(client, acme.member, new_issue(client, acme)) == ["issue.create"]


def test_history_lists_changes_oldest_first(client, acme) -> None:
    issue = acme.issues[0]
    write(client, acme.member, issue, "PATCH", "", {"title": "One"})
    write(client, acme.member, issue, "POST", "/assign", {"assignee_id": None})
    write(client, acme.member, issue, "POST", "/transition", {"status": "in_progress"})
    assert actions(client, acme.member, issue) == [
        "issue.update",
        "issue.assign",
        "issue.transition",
    ]


def test_history_entries_are_audit_out_items(client, acme) -> None:
    write(client, acme.admin, acme.issues[0], "PATCH", "", {"title": "One"})
    entry = history(client, acme.member, acme.issues[0]).json()["items"][0]
    assert set(entry) == {"id", "org_id", "actor_id", "action", "entity", "entity_id", "at"}
    assert (entry["entity"], entry["entity_id"], entry["actor_id"]) == (
        "issue",
        acme.issues[0],
        acme.admin,
    )


def test_history_holds_only_that_issue(client, acme) -> None:
    write(client, acme.member, acme.issues[1], "PATCH", "", {"title": "Other"})
    write(client, acme.member, acme.issues[0], "PATCH", "", {"title": "Mine"})
    entries = history(client, acme.member, acme.issues[0]).json()["items"]
    assert [e["entity_id"] for e in entries] == [acme.issues[0]]


def test_history_ignores_other_entities(client, acme) -> None:
    client.patch(f"/projects/{acme.projects[0]}", json={"name": "X"}, headers=auth(acme.admin))
    assert actions(client, acme.member, acme.issues[0]) == []


def test_viewer_can_read_history(client, acme) -> None:
    write(client, acme.member, acme.issues[0], "PATCH", "", {"title": "Seen"})
    assert actions(client, acme.viewer, acme.issues[0]) == ["issue.update"]


def test_history_uses_the_list_envelope(client, acme) -> None:
    body = history(client, acme.member, acme.issues[0], "").json()
    assert set(body) == {"items", "next_cursor"}


def test_history_paginates(client, acme) -> None:
    for n in range(3):
        write(client, acme.member, acme.issues[0], "PATCH", "", {"title": f"T{n}"})
    first = history(client, acme.member, acme.issues[0], "?limit=2").json()
    assert len(first["items"]) == 2
    rest = history(client, acme.member, acme.issues[0], f"?limit=2&cursor={first['next_cursor']}")
    assert len(rest.json()["items"]) == 1
    ids = [e["id"] for e in first["items"] + rest.json()["items"]]
    assert ids == sorted(ids)


def test_history_of_another_orgs_issue_is_404(client, acme, globex) -> None:
    response = history(client, acme.admin, globex.issues[0])
    assert response.status_code == 404
    assert error_code(response) == "not_found"
    assert actions(client, acme.admin, acme.issues[0]) == []


def test_history_of_a_deleted_issue_is_404(client, acme) -> None:
    assert actions(client, acme.admin, acme.issues[2]) == []
    client.delete(f"/issues/{acme.issues[2]}", headers=auth(acme.member))
    assert history(client, acme.admin, acme.issues[2]).status_code == 404


def test_refused_writes_do_not_appear_in_history(client, acme) -> None:
    for if_match in ("1", '"9"'):  # malformed, then stale: both 412
        client.patch(
            f"/issues/{acme.issues[0]}",
            json={"title": "x"},
            headers={**auth(acme.member), "If-Match": if_match},
        )
    assert actions(client, acme.member, acme.issues[0]) == []


def test_reading_history_adds_no_audit_row(client, acme) -> None:
    before = client.get("/audit?limit=100", headers=auth(acme.admin)).json()["items"]
    assert actions(client, acme.member, acme.issues[0]) == []
    after = client.get("/audit?limit=100", headers=auth(acme.admin)).json()["items"]
    assert after == before
