"""F5: POST /projects/{project_id}/issues/bulk-close."""

from __future__ import annotations

from conftest import auth, error_code


def move(client, o, issue_id: int, status: str) -> None:  # type: ignore[no-untyped-def]
    version = client.get(f"/issues/{issue_id}", headers=auth(o.member)).json()["version"]
    response = client.post(
        f"/issues/{issue_id}/transition",
        json={"status": status},
        headers={**auth(o.member), "If-Match": f'"{version}"'},
    )
    assert response.status_code == 200, response.text


def bulk(client, user_id: int, project_id: int, issue_ids: list[int]):  # type: ignore[no-untyped-def]
    return client.post(
        f"/projects/{project_id}/issues/bulk-close",
        json={"issue_ids": issue_ids},
        headers=auth(user_id),
    )


def issue(client, o, issue_id: int) -> dict:  # type: ignore[no-untyped-def]
    return client.get(f"/issues/{issue_id}", headers=auth(o.member)).json()


def audit_actions(client, o) -> list[str]:  # type: ignore[no-untyped-def]
    items = client.get("/audit?limit=100", headers=auth(o.admin)).json()["items"]
    return [item["action"] for item in items]


def test_in_progress_issues_are_closed(client, acme) -> None:
    a, b = acme.issues[0], acme.issues[1]
    move(client, acme, a, "in_progress")
    move(client, acme, b, "in_progress")
    response = bulk(client, acme.member, acme.projects[0], [a, b])
    assert response.status_code == 200
    assert response.json() == {"closed": [a, b], "skipped": []}
    assert issue(client, acme, a)["status"] == "done"


def test_open_and_done_issues_are_skipped_with_reasons(client, acme) -> None:
    started, done, still_open = acme.issues[0], acme.issues[1], acme.issues[2]
    move(client, acme, started, "in_progress")
    move(client, acme, done, "in_progress")
    move(client, acme, done, "done")
    body = bulk(client, acme.member, acme.projects[0], [still_open, done, started]).json()
    assert body["closed"] == [started]
    assert body["skipped"] == [
        {"id": still_open, "reason": "invalid_transition"},
        {"id": done, "reason": "already_done"},
    ]
    assert issue(client, acme, still_open)["status"] == "open"


def test_closing_increments_the_version(client, acme) -> None:
    move(client, acme, acme.issues[0], "in_progress")
    before = issue(client, acme, acme.issues[0])["version"]
    bulk(client, acme.member, acme.projects[0], [acme.issues[0]])
    assert issue(client, acme, acme.issues[0])["version"] == before + 1


def test_an_issue_of_another_project_rejects_the_whole_request(client, acme) -> None:
    move(client, acme, acme.issues[0], "in_progress")
    response = bulk(client, acme.member, acme.projects[0], [acme.issues[0], acme.issues[10]])
    assert response.status_code == 404
    assert error_code(response) == "not_found"
    assert issue(client, acme, acme.issues[0])["status"] == "in_progress"


def test_an_issue_of_another_org_rejects_the_whole_request(client, acme, globex) -> None:
    move(client, acme, acme.issues[0], "in_progress")
    response = bulk(client, acme.member, acme.projects[0], [acme.issues[0], globex.issues[0]])
    assert response.status_code == 404
    assert issue(client, acme, acme.issues[0])["status"] == "in_progress"


def test_deleted_issue_rejects_the_whole_request(client, acme) -> None:
    client.delete(f"/issues/{acme.issues[1]}", headers=auth(acme.member))
    response = bulk(client, acme.member, acme.projects[0], [acme.issues[0], acme.issues[1]])
    assert response.status_code == 404


def test_project_of_another_org_or_archived_is_404(client, acme, globex) -> None:
    assert bulk(client, acme.admin, globex.projects[0], [globex.issues[0]]).status_code == 404
    client.delete(f"/projects/{acme.projects[1]}", headers=auth(acme.admin))
    assert bulk(client, acme.admin, acme.projects[1], [acme.issues[10]]).status_code == 404


def test_viewer_is_403(client, acme) -> None:
    response = bulk(client, acme.viewer, acme.projects[0], [acme.issues[0]])
    assert response.status_code == 403
    assert error_code(response) == "forbidden"


def test_invalid_id_lists_are_422(client, acme) -> None:
    for ids in ([], [acme.issues[0], acme.issues[0]], list(range(1, 102))):
        response = bulk(client, acme.member, acme.projects[0], ids)
        assert response.status_code == 422, ids
        assert error_code(response) == "validation_error"


def test_one_audit_row_per_request(client, acme) -> None:
    move(client, acme, acme.issues[0], "in_progress")
    move(client, acme, acme.issues[1], "in_progress")
    before = audit_actions(client, acme)
    bulk(client, acme.member, acme.projects[0], [acme.issues[0], acme.issues[1]])
    assert audit_actions(client, acme)[len(before) :] == ["issue.bulk_close"]
    items = client.get("/audit?limit=100", headers=auth(acme.admin)).json()["items"]
    assert (items[-1]["entity"], items[-1]["entity_id"]) == ("project", acme.projects[0])


def test_a_rejected_request_adds_no_audit_row(client, acme, globex) -> None:
    before = audit_actions(client, acme)
    bulk(client, acme.member, acme.projects[0], [globex.issues[0]])
    bulk(client, acme.viewer, acme.projects[0], [acme.issues[0]])
    assert audit_actions(client, acme) == before
