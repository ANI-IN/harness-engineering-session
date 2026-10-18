"""F5 hidden tests: POST /projects/{project_id}/issues/bulk-close (spec: docs/features/f5.md)."""

from __future__ import annotations

from hidden_support import auth, error_code


def move(client, user_id: int, issue_id: int, *statuses: str) -> None:  # type: ignore[no-untyped-def]
    for status in statuses:
        etag = client.get(f"/issues/{issue_id}", headers=auth(user_id)).headers.get("ETag", '"1"')
        response = client.post(
            f"/issues/{issue_id}/transition",
            json={"status": status},
            headers={**auth(user_id), "If-Match": etag},
        )
        assert response.status_code == 200, response.text


def bulk(client, user_id: int, project_id: int, issue_ids: object):  # type: ignore[no-untyped-def]
    return client.post(
        f"/projects/{project_id}/issues/bulk-close",
        json={"issue_ids": issue_ids},
        headers=auth(user_id),
    )


def issue(client, user_id: int, issue_id: int) -> dict:  # type: ignore[no-untyped-def]
    return client.get(f"/issues/{issue_id}", headers=auth(user_id)).json()


def status(client, user_id: int, issue_id: int) -> str:  # type: ignore[no-untyped-def]
    return issue(client, user_id, issue_id)["status"]


def audit(client, o) -> list[dict]:  # type: ignore[no-untyped-def]
    return client.get("/audit?limit=100", headers=auth(o.admin)).json()["items"]


# -- closing --------------------------------------------------------------------------------------


def test_one_in_progress_issue_is_closed(client, acme) -> None:
    move(client, acme.member, acme.issues[0], "in_progress")
    response = bulk(client, acme.member, acme.projects[0], [acme.issues[0]])
    assert response.status_code == 200
    assert response.json() == {"closed": [acme.issues[0]], "skipped": []}


def test_closed_issue_is_done(client, acme) -> None:
    move(client, acme.member, acme.issues[0], "in_progress")
    bulk(client, acme.member, acme.projects[0], [acme.issues[0]])
    assert status(client, acme.member, acme.issues[0]) == "done"


def test_several_issues_are_closed(client, acme) -> None:
    targets = list(acme.issues[:4])
    for target in targets:
        move(client, acme.member, target, "in_progress")
    body = bulk(client, acme.member, acme.projects[0], targets).json()
    assert body == {"closed": targets, "skipped": []}
    assert [status(client, acme.member, t) for t in targets] == ["done"] * 4


def test_closed_keeps_the_request_order(client, acme) -> None:
    targets = [acme.issues[5], acme.issues[1], acme.issues[3]]
    for target in targets:
        move(client, acme.member, target, "in_progress")
    assert bulk(client, acme.member, acme.projects[0], targets).json()["closed"] == targets


def test_closing_increments_the_version(client, acme) -> None:
    move(client, acme.member, acme.issues[0], "in_progress")
    bulk(client, acme.member, acme.projects[0], [acme.issues[0]])
    assert issue(client, acme.member, acme.issues[0])["version"] == 3


def test_admin_can_bulk_close(client, acme) -> None:
    move(client, acme.member, acme.issues[0], "in_progress")
    response = bulk(client, acme.admin, acme.projects[0], [acme.issues[0]])
    assert response.json()["closed"] == [acme.issues[0]]


def test_works_in_the_second_project(client, acme) -> None:
    move(client, acme.member, acme.issues[10], "in_progress")
    response = bulk(client, acme.member, acme.projects[1], [acme.issues[10]])
    assert response.json() == {"closed": [acme.issues[10]], "skipped": []}


def test_works_in_globex(client, globex) -> None:
    move(client, globex.member, globex.issues[2], "in_progress")
    response = bulk(client, globex.member, globex.projects[0], [globex.issues[2]])
    assert response.json() == {"closed": [globex.issues[2]], "skipped": []}


def test_reopened_then_started_issue_can_be_closed_again(client, acme) -> None:
    move(client, acme.member, acme.issues[0], "in_progress", "done", "open", "in_progress")
    assert bulk(client, acme.member, acme.projects[0], [acme.issues[0]]).json()["closed"] == [
        acme.issues[0]
    ]


def test_100_ids_are_accepted(client, acme) -> None:
    ids = list(acme.issues[:10])
    for n in range(90):
        created = client.post(
            f"/projects/{acme.projects[0]}/issues",
            json={"title": f"Bulk {n}"},
            headers=auth(acme.member),
        )
        ids.append(created.json()["id"])
    response = bulk(client, acme.member, acme.projects[0], ids)
    assert response.status_code == 200
    assert len(response.json()["skipped"]) == 100


# -- skipping -------------------------------------------------------------------------------------


def test_open_issue_is_skipped_as_invalid_transition(client, acme) -> None:
    body = bulk(client, acme.member, acme.projects[0], [acme.issues[0]]).json()
    assert body == {
        "closed": [],
        "skipped": [{"id": acme.issues[0], "reason": "invalid_transition"}],
    }


def test_skipped_open_issue_stays_open(client, acme) -> None:
    assert bulk(client, acme.member, acme.projects[0], [acme.issues[0]]).status_code == 200
    assert issue(client, acme.member, acme.issues[0])["status"] == "open"
    assert issue(client, acme.member, acme.issues[0])["version"] == 1


def test_done_issue_is_skipped_as_already_done(client, acme) -> None:
    move(client, acme.member, acme.issues[0], "in_progress", "done")
    body = bulk(client, acme.member, acme.projects[0], [acme.issues[0]]).json()
    assert body == {"closed": [], "skipped": [{"id": acme.issues[0], "reason": "already_done"}]}


def test_skipped_done_issue_keeps_its_version(client, acme) -> None:
    move(client, acme.member, acme.issues[0], "in_progress", "done")
    assert bulk(client, acme.member, acme.projects[0], [acme.issues[0]]).status_code == 200
    assert issue(client, acme.member, acme.issues[0])["version"] == 3


def test_mixed_request_splits_closed_and_skipped(client, acme) -> None:
    started, done, untouched = acme.issues[0], acme.issues[1], acme.issues[2]
    move(client, acme.member, started, "in_progress")
    move(client, acme.member, done, "in_progress", "done")
    body = bulk(client, acme.member, acme.projects[0], [untouched, started, done]).json()
    assert body["closed"] == [started]
    assert body["skipped"] == [
        {"id": untouched, "reason": "invalid_transition"},
        {"id": done, "reason": "already_done"},
    ]


def test_skipped_keeps_the_request_order(client, acme) -> None:
    ids = [acme.issues[4], acme.issues[2], acme.issues[3]]
    body = bulk(client, acme.member, acme.projects[0], ids).json()
    assert [s["id"] for s in body["skipped"]] == ids


def test_every_id_appears_exactly_once(client, acme) -> None:
    move(client, acme.member, acme.issues[1], "in_progress")
    ids = list(acme.issues[:5])
    body = bulk(client, acme.member, acme.projects[0], ids).json()
    reported = body["closed"] + [s["id"] for s in body["skipped"]]
    assert sorted(reported) == sorted(ids)


def test_all_skipped_is_still_200(client, acme) -> None:
    response = bulk(client, acme.member, acme.projects[0], list(acme.issues[:3]))
    assert response.status_code == 200
    assert response.json()["closed"] == []


def test_second_bulk_close_reports_already_done(client, acme) -> None:
    move(client, acme.member, acme.issues[0], "in_progress")
    bulk(client, acme.member, acme.projects[0], [acme.issues[0]])
    body = bulk(client, acme.member, acme.projects[0], [acme.issues[0]]).json()
    assert body["skipped"] == [{"id": acme.issues[0], "reason": "already_done"}]


# -- atomic 404 -----------------------------------------------------------------------------------


def test_issue_of_another_project_is_404(client, acme) -> None:
    response = bulk(client, acme.member, acme.projects[0], [acme.issues[10]])
    assert response.status_code == 404
    assert error_code(response) == "not_found"
    assert bulk(client, acme.member, acme.projects[1], [acme.issues[10]]).status_code == 200


def test_404_leaves_valid_issues_untouched(client, acme) -> None:
    move(client, acme.member, acme.issues[0], "in_progress")
    response = bulk(client, acme.member, acme.projects[0], [acme.issues[0], acme.issues[10]])
    assert response.status_code == 404
    assert status(client, acme.member, acme.issues[0]) == "in_progress"
    assert bulk(client, acme.member, acme.projects[0], [acme.issues[0]]).json()["closed"] == [
        acme.issues[0]
    ]


def test_issue_of_another_org_is_404_and_changes_nothing(client, acme, globex) -> None:
    move(client, acme.member, acme.issues[0], "in_progress")
    response = bulk(client, acme.member, acme.projects[0], [acme.issues[0], globex.issues[0]])
    assert response.status_code == 404
    assert status(client, acme.member, acme.issues[0]) == "in_progress"
    assert bulk(client, acme.member, acme.projects[0], [acme.issues[0]]).json()["closed"] == [
        acme.issues[0]
    ]


def test_unknown_id_is_404_and_changes_nothing(client, acme) -> None:
    move(client, acme.member, acme.issues[0], "in_progress")
    response = bulk(client, acme.member, acme.projects[0], [acme.issues[0], 99999])
    assert response.status_code == 404
    assert status(client, acme.member, acme.issues[0]) == "in_progress"
    assert bulk(client, acme.member, acme.projects[0], [acme.issues[0]]).json()["closed"] == [
        acme.issues[0]
    ]


def test_deleted_issue_is_404_and_changes_nothing(client, acme) -> None:
    move(client, acme.member, acme.issues[0], "in_progress")
    client.delete(f"/issues/{acme.issues[1]}", headers=auth(acme.member))
    response = bulk(client, acme.member, acme.projects[0], [acme.issues[0], acme.issues[1]])
    assert response.status_code == 404
    assert status(client, acme.member, acme.issues[0]) == "in_progress"
    assert bulk(client, acme.member, acme.projects[0], [acme.issues[0]]).json()["closed"] == [
        acme.issues[0]
    ]


def test_other_orgs_project_is_404(client, acme, globex) -> None:
    move(client, globex.member, globex.issues[0], "in_progress")
    response = bulk(client, acme.admin, globex.projects[0], [globex.issues[0]])
    assert response.status_code == 404
    assert error_code(response) == "not_found"
    assert status(client, globex.member, globex.issues[0]) == "in_progress"
    assert bulk(client, globex.member, globex.projects[0], [globex.issues[0]]).status_code == 200


def test_archived_project_is_404(client, acme) -> None:
    move(client, acme.member, acme.issues[10], "in_progress")
    assert bulk(client, acme.member, acme.projects[1], [acme.issues[11]]).status_code == 200
    client.delete(f"/projects/{acme.projects[1]}", headers=auth(acme.admin))
    assert bulk(client, acme.member, acme.projects[1], [acme.issues[10]]).status_code == 404


def test_404_adds_no_audit_row(client, acme, globex) -> None:
    assert bulk(client, acme.member, acme.projects[0], [acme.issues[0]]).status_code == 200
    before = audit(client, acme)
    bulk(client, acme.member, acme.projects[0], [acme.issues[0], globex.issues[0]])
    assert audit(client, acme) == before


# -- roles and validation -------------------------------------------------------------------------


def test_viewer_is_403(client, acme) -> None:
    move(client, acme.member, acme.issues[0], "in_progress")
    response = bulk(client, acme.viewer, acme.projects[0], [acme.issues[0]])
    assert response.status_code == 403
    assert error_code(response) == "forbidden"
    assert status(client, acme.member, acme.issues[0]) == "in_progress"


def test_viewer_403_adds_no_audit_row(client, acme) -> None:
    assert bulk(client, acme.member, acme.projects[0], [acme.issues[0]]).status_code == 200
    before = audit(client, acme)
    bulk(client, acme.viewer, acme.projects[0], [acme.issues[0]])
    assert audit(client, acme) == before


def test_requires_a_token(client, acme) -> None:
    response = client.post(
        f"/projects/{acme.projects[0]}/issues/bulk-close", json={"issue_ids": [acme.issues[0]]}
    )
    assert response.status_code == 401
    assert bulk(client, acme.member, acme.projects[0], [acme.issues[0]]).status_code == 200


def test_empty_list_is_422(client, acme) -> None:
    response = bulk(client, acme.member, acme.projects[0], [])
    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    assert bulk(client, acme.member, acme.projects[0], [acme.issues[0]]).status_code == 200


def test_101_ids_are_422(client, acme) -> None:
    response = bulk(client, acme.member, acme.projects[0], list(range(1, 102)))
    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    assert bulk(client, acme.member, acme.projects[0], [acme.issues[0]]).status_code == 200


def test_repeated_id_is_422_and_changes_nothing(client, acme) -> None:
    move(client, acme.member, acme.issues[0], "in_progress")
    response = bulk(client, acme.member, acme.projects[0], [acme.issues[0], acme.issues[0]])
    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    assert status(client, acme.member, acme.issues[0]) == "in_progress"


def test_non_integer_id_is_422(client, acme) -> None:
    assert bulk(client, acme.member, acme.projects[0], ["one"]).status_code == 422
    assert bulk(client, acme.member, acme.projects[0], [acme.issues[0]]).status_code == 200


def test_missing_issue_ids_is_422(client, acme) -> None:
    response = client.post(
        f"/projects/{acme.projects[0]}/issues/bulk-close", json={}, headers=auth(acme.member)
    )
    assert response.status_code == 422
    assert bulk(client, acme.member, acme.projects[0], [acme.issues[0]]).status_code == 200


def test_zero_id_is_422(client, acme) -> None:
    assert bulk(client, acme.member, acme.projects[0], [0]).status_code == 422
    assert bulk(client, acme.member, acme.projects[0], [acme.issues[0]]).status_code == 200


# -- audit ----------------------------------------------------------------------------------------


def test_one_audit_row_for_several_closed_issues(client, acme) -> None:
    for target in acme.issues[:3]:
        move(client, acme.member, target, "in_progress")
    before = audit(client, acme)
    bulk(client, acme.member, acme.projects[0], list(acme.issues[:3]))
    assert [row["action"] for row in audit(client, acme)[len(before) :]] == ["issue.bulk_close"]


def test_audit_row_names_the_project(client, acme) -> None:
    move(client, acme.member, acme.issues[10], "in_progress")
    bulk(client, acme.admin, acme.projects[1], [acme.issues[10]])
    row = audit(client, acme)[-1]
    assert (row["action"], row["entity"], row["entity_id"], row["actor_id"]) == (
        "issue.bulk_close",
        "project",
        acme.projects[1],
        acme.admin,
    )


def test_all_skipped_request_still_adds_one_audit_row(client, acme) -> None:
    before = audit(client, acme)
    bulk(client, acme.member, acme.projects[0], list(acme.issues[:3]))
    rows = audit(client, acme)[len(before) :]
    assert [row["action"] for row in rows] == ["issue.bulk_close"]


def test_does_not_need_if_match(client, acme) -> None:
    move(client, acme.member, acme.issues[0], "in_progress")
    response = bulk(client, acme.member, acme.projects[0], [acme.issues[0]])
    assert response.status_code == 200
    assert response.json()["closed"] == [acme.issues[0]]
