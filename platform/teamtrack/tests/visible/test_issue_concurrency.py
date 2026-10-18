"""F4: ETag / If-Match on issue writes, issue history, and the board's edit conflict page."""

from __future__ import annotations

import re

import pytest

from conftest import auth, error_code

WRITES = [
    ("PATCH", "", {"title": "Renamed"}),
    ("POST", "/assign", {"assignee_id": None}),
    ("POST", "/transition", {"status": "in_progress"}),
]


def send(client, user_id: int, issue_id: int, index: int, if_match: str | None, body=None):  # type: ignore[no-untyped-def]
    method, suffix, default = WRITES[index]
    headers = {**auth(user_id), **({"If-Match": if_match} if if_match is not None else {})}
    return client.request(
        method, f"/issues/{issue_id}{suffix}", json=body or default, headers=headers
    )


def test_get_returns_the_version_as_etag(client, acme) -> None:
    response = client.get(f"/issues/{acme.issues[0]}", headers=auth(acme.viewer))
    assert response.headers["ETag"] == '"1"'


@pytest.mark.parametrize("index", range(3))
def test_write_without_if_match_works_and_returns_the_new_etag(client, acme, index: int) -> None:
    response = send(client, acme.member, acme.issues[0], index, None)
    assert response.status_code == 200
    assert response.json()["version"] == 2
    assert response.headers["ETag"] == '"2"'


@pytest.mark.parametrize("if_match", ['"1', "1", 'W/"1"', '"one"', ""])
def test_malformed_if_match_is_412(client, acme, if_match: str) -> None:
    response = send(client, acme.member, acme.issues[0], 0, if_match)
    assert response.status_code == 412
    assert error_code(response) == "precondition_failed"


@pytest.mark.parametrize("index", range(3))
def test_stale_if_match_is_412_and_changes_nothing(client, acme, index: int) -> None:
    response = send(client, acme.member, acme.issues[0], index, '"7"')
    assert response.status_code == 412
    assert error_code(response) == "precondition_failed"
    issue = client.get(f"/issues/{acme.issues[0]}", headers=auth(acme.member)).json()
    assert issue["version"] == 1
    assert issue["title"] == "Login page times out"


@pytest.mark.parametrize("index", range(3))
def test_matching_if_match_succeeds_and_returns_the_new_etag(client, acme, index: int) -> None:
    response = send(client, acme.member, acme.issues[0], index, '"1"')
    assert response.status_code == 200
    assert response.json()["version"] == 2
    assert response.headers["ETag"] == '"2"'


def test_second_writer_with_the_old_version_gets_412(client, acme) -> None:
    assert send(client, acme.member, acme.issues[0], 0, '"1"').status_code == 200
    response = send(client, acme.admin, acme.issues[0], 0, '"1"', {"title": "Lost update"})
    assert response.status_code == 412
    title = client.get(f"/issues/{acme.issues[0]}", headers=auth(acme.member)).json()["title"]
    assert title == "Renamed"


def test_check_order_403_then_404_then_412_then_422(client, acme, globex) -> None:
    issue = acme.issues[0]
    assert send(client, acme.viewer, issue, 0, '"9"').status_code == 403
    assert send(client, acme.member, globex.issues[0], 0, '"9"').status_code == 404
    bad = {"priority": "urgent"}
    assert send(client, acme.member, issue, 0, '"9"', bad).status_code == 412
    assert send(client, acme.member, issue, 0, '"1"', bad).status_code == 422
    assert send(client, acme.member, issue, 0, None, bad).status_code == 422


def test_deleted_issue_is_404_before_the_precondition(client, acme) -> None:
    client.delete(f"/issues/{acme.issues[0]}", headers=auth(acme.member))
    assert send(client, acme.member, acme.issues[0], 0, '"9"').status_code == 404


def test_rejected_writes_add_no_audit_row(client, acme) -> None:
    before = len(client.get("/audit?limit=100", headers=auth(acme.admin)).json()["items"])
    send(client, acme.member, acme.issues[0], 0, "garbage")
    send(client, acme.member, acme.issues[0], 1, '"5"')
    after = len(client.get("/audit?limit=100", headers=auth(acme.admin)).json()["items"])
    assert after == before


def test_openapi_documents_412(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for path, method in [
        ("/issues/{issue_id}", "patch"),
        ("/issues/{issue_id}/assign", "post"),
        ("/issues/{issue_id}/transition", "post"),
    ]:
        assert "412" in paths[path][method]["responses"], path


def test_history_lists_the_issues_audit_entries_oldest_first(client, acme) -> None:
    issue = acme.issues[0]
    send(client, acme.member, issue, 0, '"1"')
    send(client, acme.admin, issue, 2, '"2"')
    send(client, acme.member, acme.issues[1], 0, '"1"')  # another issue: not in this history
    body = client.get(f"/issues/{issue}/history", headers=auth(acme.viewer)).json()
    assert set(body) == {"items", "next_cursor"}
    assert [(e["action"], e["actor_id"]) for e in body["items"]] == [
        ("issue.update", acme.member),
        ("issue.transition", acme.admin),
    ]
    assert all(e["entity"] == "issue" and e["entity_id"] == issue for e in body["items"])


def test_history_is_paginated(client, acme) -> None:
    issue = acme.issues[0]
    for version in (1, 2, 3):
        send(client, acme.member, issue, 0, f'"{version}"', {"title": f"Title {version}"})
    first = client.get(f"/issues/{issue}/history?limit=2", headers=auth(acme.member)).json()
    assert len(first["items"]) == 2
    rest = client.get(
        f"/issues/{issue}/history?limit=2&cursor={first['next_cursor']}", headers=auth(acme.member)
    ).json()
    assert len(rest["items"]) == 1
    assert rest["next_cursor"] is None


def test_history_of_another_orgs_or_a_deleted_issue_is_404(client, acme, globex) -> None:
    assert (
        client.get(f"/issues/{globex.issues[0]}/history", headers=auth(acme.admin)).status_code
        == 404
    )
    client.delete(f"/issues/{acme.issues[0]}", headers=auth(acme.member))
    response = client.get(f"/issues/{acme.issues[0]}/history", headers=auth(acme.admin))
    assert response.status_code == 404


def login(client, email: str) -> None:  # type: ignore[no-untyped-def]
    response = client.post("/board/login", data={"email": email}, follow_redirects=False)
    assert response.status_code == 303


def test_board_edit_form_carries_the_version(client, acme) -> None:
    login(client, "member@acme.test")
    html = client.get(f"/board/issues/{acme.issues[0]}").text
    assert re.search(r'<input type="hidden" name="version" value="1">', html)


def test_board_save_with_the_current_version_works(client, acme) -> None:
    login(client, "member@acme.test")
    response = client.post(
        f"/board/issues/{acme.issues[0]}/edit",
        data={"title": "Saved", "priority": "low", "version": "1"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    issue = client.get(f"/issues/{acme.issues[0]}", headers=auth(acme.member)).json()
    assert (issue["title"], issue["version"]) == ("Saved", 2)


def test_board_stale_save_returns_a_409_page(client, acme) -> None:
    login(client, "member@acme.test")
    path = f"/board/issues/{acme.issues[0]}/edit"
    client.post(path, data={"title": "Tab A", "priority": "low", "version": "1"})
    response = client.post(path, data={"title": "Tab B", "priority": "low", "version": "1"})
    assert response.status_code == 409
    assert "text/html" in response.headers["content-type"]
    assert 'class="conflict"' in response.text
    title = client.get(f"/issues/{acme.issues[0]}", headers=auth(acme.member)).json()["title"]
    assert title == "Tab A"
