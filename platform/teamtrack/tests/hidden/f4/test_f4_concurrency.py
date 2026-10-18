"""F4 hidden tests: ETag and If-Match on issue writes (spec: docs/features/f4.md)."""

from __future__ import annotations

from hidden_support import auth, error_code


def get(client, user_id: int, issue_id: int):  # type: ignore[no-untyped-def]
    return client.get(f"/issues/{issue_id}", headers=auth(user_id))


def headers(user_id: int, if_match: str | None) -> dict[str, str]:
    return {**auth(user_id), **({"If-Match": if_match} if if_match is not None else {})}


def patch(client, user_id: int, issue_id: int, if_match: str | None, body=None):  # type: ignore[no-untyped-def]
    return client.patch(
        f"/issues/{issue_id}", json=body or {"title": "Edited"}, headers=headers(user_id, if_match)
    )


def assign(client, user_id: int, issue_id: int, if_match: str | None, assignee=None):  # type: ignore[no-untyped-def]
    return client.post(
        f"/issues/{issue_id}/assign",
        json={"assignee_id": assignee},
        headers=headers(user_id, if_match),
    )


def transition(client, user_id: int, issue_id: int, if_match: str | None, status="in_progress"):  # type: ignore[no-untyped-def]
    return client.post(
        f"/issues/{issue_id}/transition",
        json={"status": status},
        headers=headers(user_id, if_match),
    )


def audit_count(client, o) -> int:  # type: ignore[no-untyped-def]
    return len(client.get("/audit?limit=100", headers=auth(o.admin)).json()["items"])


# -- ETag -----------------------------------------------------------------------------------------


def test_get_returns_an_etag(client, acme) -> None:
    assert get(client, acme.member, acme.issues[0]).headers.get("ETag") == '"1"'


def test_etag_is_the_quoted_version(client, acme) -> None:
    response = get(client, acme.viewer, acme.issues[4])
    assert response.headers["ETag"] == f'"{response.json()["version"]}"'


def test_etag_follows_the_version(client, acme) -> None:
    patch(client, acme.member, acme.issues[0], '"1"')
    patch(client, acme.member, acme.issues[0], '"2"', {"priority": "high"})
    assert get(client, acme.member, acme.issues[0]).headers["ETag"] == '"3"'


def test_etag_in_globex(client, globex) -> None:
    assert get(client, globex.viewer, globex.issues[3]).headers["ETag"] == '"1"'


# -- without If-Match -----------------------------------------------------------------------------


def test_patch_without_if_match_succeeds_and_returns_the_new_etag(client, acme) -> None:
    response = patch(client, acme.member, acme.issues[0], None, {"title": "No header"})
    assert response.status_code == 200
    assert (response.json()["title"], response.json()["version"]) == ("No header", 2)
    assert response.headers["ETag"] == '"2"'


def test_assign_without_if_match_succeeds_and_returns_the_new_etag(client, acme) -> None:
    response = assign(client, acme.member, acme.issues[1], None, acme.viewer)
    assert response.status_code == 200
    assert (response.json()["assignee_id"], response.json()["version"]) == (acme.viewer, 2)
    assert response.headers["ETag"] == '"2"'


def test_transition_without_if_match_succeeds_and_returns_the_new_etag(client, acme) -> None:
    response = transition(client, acme.member, acme.issues[2], None)
    assert response.status_code == 200
    assert (response.json()["status"], response.json()["version"]) == ("in_progress", 2)
    assert response.headers["ETag"] == '"2"'


def test_write_without_if_match_makes_the_old_etag_stale(client, acme) -> None:
    etag = get(client, acme.member, acme.issues[0]).headers["ETag"]
    written = patch(client, acme.member, acme.issues[0], None, {"title": "Unconditional"})
    assert written.status_code == 200
    response = patch(client, acme.member, acme.issues[0], etag, {"title": "Based on old"})
    assert response.status_code == 412
    assert get(client, acme.member, acme.issues[0]).json()["title"] == "Unconditional"


# -- 412 ------------------------------------------------------------------------------------------


def test_patch_with_a_stale_version_is_412(client, acme) -> None:
    patch(client, acme.member, acme.issues[0], '"1"')
    response = patch(client, acme.member, acme.issues[0], '"1"')
    assert response.status_code == 412
    assert error_code(response) == "precondition_failed"


def test_assign_with_a_stale_version_is_412(client, acme) -> None:
    assign(client, acme.member, acme.issues[1], '"1"', acme.viewer)
    response = assign(client, acme.member, acme.issues[1], '"1"', None)
    assert response.status_code == 412
    assert error_code(response) == "precondition_failed"


def test_transition_with_a_stale_version_is_412(client, acme) -> None:
    transition(client, acme.member, acme.issues[2], '"1"')
    response = transition(client, acme.member, acme.issues[2], '"1"', "done")
    assert response.status_code == 412
    assert error_code(response) == "precondition_failed"


def test_a_future_version_is_412(client, acme) -> None:
    response = patch(client, acme.member, acme.issues[0], '"2"')
    assert response.status_code == 412


def test_unquoted_version_is_412(client, acme) -> None:
    response = patch(client, acme.member, acme.issues[0], "1")
    assert response.status_code == 412
    assert error_code(response) == "precondition_failed"


def test_weak_etag_is_412(client, acme) -> None:
    assert patch(client, acme.member, acme.issues[0], 'W/"1"').status_code == 412


def test_garbage_if_match_is_412(client, acme) -> None:
    assert transition(client, acme.member, acme.issues[0], '"abc"').status_code == 412


def test_empty_if_match_is_412(client, acme) -> None:
    response = assign(client, acme.member, acme.issues[0], "", acme.viewer)
    assert response.status_code == 412
    assert error_code(response) == "precondition_failed"


def test_malformed_if_match_changes_nothing(client, acme) -> None:
    assert patch(client, acme.member, acme.issues[0], "one", {"title": "Nope"}).status_code == 412
    issue = get(client, acme.member, acme.issues[0]).json()
    assert (issue["title"], issue["version"]) == ("Login page times out", 1)


def test_412_changes_nothing(client, acme) -> None:
    response = assign(client, acme.member, acme.issues[0], '"9"', acme.viewer)
    assert response.status_code == 412
    issue = get(client, acme.member, acme.issues[0]).json()
    assert (issue["assignee_id"], issue["version"]) == (acme.member, 1)


def test_the_second_of_two_writers_loses_cleanly(client, acme) -> None:
    etag = get(client, acme.member, acme.issues[5]).headers["ETag"]
    assert patch(client, acme.member, acme.issues[5], etag, {"title": "First"}).status_code == 200
    second = patch(client, acme.admin, acme.issues[5], etag, {"title": "Second"})
    assert second.status_code == 412
    assert get(client, acme.member, acme.issues[5]).json()["title"] == "First"


# -- success --------------------------------------------------------------------------------------


def test_patch_with_the_current_etag_succeeds(client, acme) -> None:
    response = patch(client, acme.member, acme.issues[0], '"1"', {"title": "Renamed"})
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed"
    assert response.headers.get("ETag") == '"2"'


def test_patch_returns_the_new_etag(client, acme) -> None:
    response = patch(client, acme.member, acme.issues[0], '"1"')
    assert (response.json()["version"], response.headers["ETag"]) == (2, '"2"')


def test_assign_returns_the_new_etag(client, acme) -> None:
    response = assign(client, acme.member, acme.issues[1], '"1"', acme.viewer)
    assert response.status_code == 200
    assert (response.json()["version"], response.headers["ETag"]) == (2, '"2"')


def test_transition_returns_the_new_etag(client, acme) -> None:
    response = transition(client, acme.member, acme.issues[2], '"1"')
    assert response.status_code == 200
    assert (response.json()["status"], response.headers["ETag"]) == ("in_progress", '"2"')


def test_a_chain_of_writes_using_each_new_etag(client, acme) -> None:
    etag = get(client, acme.member, acme.issues[6]).headers["ETag"]
    etag = patch(client, acme.member, acme.issues[6], etag).headers["ETag"]
    etag = assign(client, acme.member, acme.issues[6], etag, acme.admin).headers["ETag"]
    etag = transition(client, acme.member, acme.issues[6], etag).headers["ETag"]
    assert etag == '"4"'
    assert get(client, acme.member, acme.issues[6]).json()["version"] == 4


def test_successful_write_adds_one_audit_row(client, acme) -> None:
    before = audit_count(client, acme)
    assert patch(client, acme.member, acme.issues[0], '"9"').status_code == 412
    assert patch(client, acme.member, acme.issues[0], '"1"').status_code == 200
    assert audit_count(client, acme) == before + 1


# -- check order ----------------------------------------------------------------------------------


def test_viewer_gets_403_before_412(client, acme) -> None:
    assert patch(client, acme.viewer, acme.issues[0], '"9"').status_code == 403
    assert patch(client, acme.member, acme.issues[0], '"9"').status_code == 412


def test_other_orgs_issue_gets_404_before_412(client, acme, globex) -> None:
    response = patch(client, acme.member, globex.issues[0], '"9"')
    assert response.status_code == 404
    assert error_code(response) == "not_found"
    assert patch(client, acme.member, acme.issues[0], '"9"').status_code == 412


def test_deleted_issue_gets_404_before_412(client, acme) -> None:
    client.delete(f"/issues/{acme.issues[3]}", headers=auth(acme.member))
    assert transition(client, acme.member, acme.issues[3], '"9"').status_code == 404
    assert transition(client, acme.member, acme.issues[4], '"9"').status_code == 412


def test_no_token_gets_401_before_412(client, acme) -> None:
    response = client.patch(
        f"/issues/{acme.issues[0]}", json={"title": "x"}, headers={"If-Match": '"9"'}
    )
    assert response.status_code == 401
    assert patch(client, acme.member, acme.issues[0], '"9"').status_code == 412


def test_invalid_body_without_if_match_is_422(client, acme) -> None:
    response = patch(client, acme.member, acme.issues[0], None, {"priority": "urgent"})
    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    assert get(client, acme.member, acme.issues[0]).headers["ETag"] == '"1"'


def test_invalid_body_with_a_stale_version_is_412(client, acme) -> None:
    response = patch(client, acme.member, acme.issues[0], '"5"', {"priority": "urgent"})
    assert response.status_code == 412


def test_invalid_body_with_the_current_version_is_422(client, acme) -> None:
    response = patch(client, acme.member, acme.issues[0], '"1"', {"priority": "urgent"})
    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    assert get(client, acme.member, acme.issues[0]).headers["ETag"] == '"1"'


def test_disallowed_transition_without_if_match_is_422(client, acme) -> None:
    response = transition(client, acme.member, acme.issues[0], None, "done")
    assert response.status_code == 422
    assert error_code(response) == "invalid_transition"
    assert get(client, acme.member, acme.issues[0]).headers["ETag"] == '"1"'


def test_disallowed_transition_with_the_current_version_is_422(client, acme) -> None:
    response = transition(client, acme.member, acme.issues[0], '"1"', "done")
    assert response.status_code == 422
    assert error_code(response) == "invalid_transition"
    assert get(client, acme.member, acme.issues[0]).headers["ETag"] == '"1"'


def test_foreign_assignee_without_if_match_is_422(client, acme, globex) -> None:
    response = assign(client, acme.member, acme.issues[0], None, globex.member)
    assert response.status_code == 422
    assert error_code(response) == "invalid_assignee"
    assert get(client, acme.member, acme.issues[0]).headers["ETag"] == '"1"'


def test_foreign_assignee_with_the_current_version_is_422(client, acme, globex) -> None:
    response = assign(client, acme.member, acme.issues[0], '"1"', globex.member)
    assert response.status_code == 422
    assert error_code(response) == "invalid_assignee"
    assert get(client, acme.member, acme.issues[0]).headers["ETag"] == '"1"'


# -- refused writes add no audit rows -------------------------------------------------------------


def test_malformed_if_match_adds_no_audit_row(client, acme) -> None:
    before = audit_count(client, acme)
    assert transition(client, acme.member, acme.issues[0], 'W/"1"').status_code == 412
    assert audit_count(client, acme) == before


def test_412_adds_no_audit_row(client, acme) -> None:
    before = audit_count(client, acme)
    assert assign(client, acme.member, acme.issues[0], '"3"', None).status_code == 412
    assert audit_count(client, acme) == before


# -- OpenAPI --------------------------------------------------------------------------------------


def _responses(client, path: str, method: str) -> set[str]:  # type: ignore[no-untyped-def]
    return set(client.get("/openapi.json").json()["paths"][path][method]["responses"])


def test_openapi_documents_412_on_patch(client) -> None:
    assert "412" in _responses(client, "/issues/{issue_id}", "patch")


def test_openapi_documents_412_on_assign(client) -> None:
    assert "412" in _responses(client, "/issues/{issue_id}/assign", "post")


def test_openapi_documents_412_on_transition(client) -> None:
    assert "412" in _responses(client, "/issues/{issue_id}/transition", "post")
