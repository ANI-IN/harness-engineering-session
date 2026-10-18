"""F2 hidden tests: comments API (spec: docs/features/f2.md)."""

from __future__ import annotations

from hidden_support import auth, error_code

ACME_COMMENTS = (1, 2)  # Acme issue 1: by the member, then by the admin
GLOBEX_COMMENTS = (3, 4)  # Globex issue 21: by the member, then by the admin
FIELDS = {"id", "org_id", "issue_id", "author_id", "body", "created_at"}


def post(client, user_id: int, issue_id: int, body: object = "A comment", **headers):  # type: ignore[no-untyped-def]
    return client.post(
        f"/issues/{issue_id}/comments", json={"body": body}, headers={**auth(user_id), **headers}
    )


def page(client, user_id: int, issue_id: int, query: str = "?limit=100"):  # type: ignore[no-untyped-def]
    return client.get(f"/issues/{issue_id}/comments{query}", headers=auth(user_id))


def listed(client, user_id: int, issue_id: int) -> list[int]:  # type: ignore[no-untyped-def]
    response = page(client, user_id, issue_id)
    assert response.status_code == 200, response.text
    return [c["id"] for c in response.json()["items"]]


def delete(client, user_id: int, comment_id: int):  # type: ignore[no-untyped-def]
    return client.delete(f"/comments/{comment_id}", headers=auth(user_id))


def audit(client, o) -> list[dict]:  # type: ignore[no-untyped-def]
    return client.get("/audit?limit=100", headers=auth(o.admin)).json()["items"]


# -- create ---------------------------------------------------------------------------------------


def test_create_returns_201(client, acme) -> None:
    assert post(client, acme.member, acme.issues[3]).status_code == 201


def test_create_returns_the_comment_out_fields(client, acme) -> None:
    assert set(post(client, acme.member, acme.issues[3]).json()) == FIELDS


def test_created_comment_names_issue_author_and_org(client, acme) -> None:
    comment = post(client, acme.admin, acme.issues[3], "Hello").json()
    assert (comment["issue_id"], comment["author_id"], comment["org_id"]) == (
        acme.issues[3],
        acme.admin,
        acme.org_id,
    )
    assert comment["body"] == "Hello"


def test_member_can_comment(client, globex) -> None:
    assert post(client, globex.member, globex.issues[5]).status_code == 201


def test_viewer_cannot_comment(client, acme) -> None:
    response = post(client, acme.viewer, acme.issues[0])
    assert response.status_code == 403
    assert error_code(response) == "forbidden"
    assert listed(client, acme.viewer, acme.issues[0]) == list(ACME_COMMENTS)


def test_body_of_one_character_is_accepted(client, acme) -> None:
    assert post(client, acme.member, acme.issues[0], "x").status_code == 201


def test_body_of_5000_characters_is_accepted(client, acme) -> None:
    response = post(client, acme.member, acme.issues[0], "y" * 5000)
    assert response.status_code == 201
    assert len(response.json()["body"]) == 5000


def test_empty_body_is_422(client, acme) -> None:
    response = post(client, acme.member, acme.issues[0], "")
    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    assert listed(client, acme.member, acme.issues[0]) == list(ACME_COMMENTS)


def test_body_over_5000_characters_is_422(client, acme) -> None:
    response = post(client, acme.member, acme.issues[0], "z" * 5001)
    assert response.status_code == 422
    assert listed(client, acme.member, acme.issues[0]) == list(ACME_COMMENTS)


def test_missing_body_is_422(client, acme) -> None:
    response = client.post(f"/issues/{acme.issues[0]}/comments", json={}, headers=auth(acme.member))
    assert response.status_code == 422
    assert listed(client, acme.member, acme.issues[0]) == list(ACME_COMMENTS)


def test_unknown_field_is_422(client, acme) -> None:
    response = client.post(
        f"/issues/{acme.issues[0]}/comments",
        json={"body": "ok", "author_id": acme.admin},
        headers=auth(acme.member),
    )
    assert response.status_code == 422
    assert listed(client, acme.member, acme.issues[0]) == list(ACME_COMMENTS)


def test_comment_on_another_orgs_issue_is_404(client, acme, globex) -> None:
    response = post(client, acme.admin, globex.issues[0])
    assert response.status_code == 404
    assert error_code(response) == "not_found"
    assert listed(client, globex.admin, globex.issues[0]) == list(GLOBEX_COMMENTS)


def test_comment_on_a_deleted_issue_is_404(client, acme) -> None:
    client.delete(f"/issues/{acme.issues[5]}", headers=auth(acme.member))
    assert post(client, acme.member, acme.issues[5]).status_code == 404
    assert post(client, acme.member, acme.issues[6]).status_code == 201


def test_comment_on_an_issue_in_an_archived_project_is_404(client, acme) -> None:
    client.delete(f"/projects/{acme.projects[1]}", headers=auth(acme.admin))
    assert post(client, acme.member, acme.issues[10]).status_code == 404
    assert post(client, acme.member, acme.issues[0]).status_code == 201


# -- list -----------------------------------------------------------------------------------------


def test_seeded_comments_are_listed_oldest_first(client, acme) -> None:
    assert listed(client, acme.member, acme.issues[0]) == list(ACME_COMMENTS)


def test_seeded_comment_authors(client, globex) -> None:
    items = page(client, globex.viewer, globex.issues[0]).json()["items"]
    assert [c["author_id"] for c in items] == [globex.member, globex.admin]


def test_new_comments_come_last(client, acme) -> None:
    first = post(client, acme.member, acme.issues[0], "one").json()["id"]
    second = post(client, acme.admin, acme.issues[0], "two").json()["id"]
    assert listed(client, acme.member, acme.issues[0]) == [*ACME_COMMENTS, first, second]


def test_list_holds_only_that_issues_comments(client, acme) -> None:
    other = post(client, acme.member, acme.issues[1]).json()["id"]
    assert listed(client, acme.member, acme.issues[1]) == [other]
    assert other not in listed(client, acme.member, acme.issues[0])


def test_issue_without_comments_has_an_empty_list(client, acme) -> None:
    response = page(client, acme.member, acme.issues[7])
    assert response.json() == {"items": [], "next_cursor": None}


def test_viewer_can_list(client, acme) -> None:
    assert listed(client, acme.viewer, acme.issues[0]) == list(ACME_COMMENTS)


def test_list_uses_the_envelope(client, acme) -> None:
    body = page(client, acme.member, acme.issues[0], "").json()
    assert set(body) == {"items", "next_cursor"}
    assert all(set(c) == FIELDS for c in body["items"])


def test_list_paginates_with_a_cursor(client, acme) -> None:
    first = page(client, acme.member, acme.issues[0], "?limit=1").json()
    assert [c["id"] for c in first["items"]] == [ACME_COMMENTS[0]]
    rest = page(client, acme.member, acme.issues[0], f"?limit=1&cursor={first['next_cursor']}")
    assert [c["id"] for c in rest.json()["items"]] == [ACME_COMMENTS[1]]
    assert rest.json()["next_cursor"] is None


def test_default_page_is_20(client, acme) -> None:
    for n in range(20):
        post(client, acme.member, acme.issues[0], f"c{n}")
    body = page(client, acme.member, acme.issues[0], "").json()
    assert len(body["items"]) == 20
    assert body["next_cursor"] is not None


def test_list_limit_over_100_is_422(client, acme) -> None:
    assert page(client, acme.member, acme.issues[0], "?limit=101").status_code == 422
    assert listed(client, acme.member, acme.issues[0]) == list(ACME_COMMENTS)


def test_list_of_another_orgs_issue_is_404(client, acme, globex) -> None:
    response = page(client, acme.member, globex.issues[0])
    assert response.status_code == 404
    assert error_code(response) == "not_found"
    assert listed(client, acme.member, acme.issues[0]) == list(ACME_COMMENTS)


def test_list_of_a_deleted_issue_is_404(client, acme) -> None:
    assert listed(client, acme.member, acme.issues[0]) == list(ACME_COMMENTS)
    client.delete(f"/issues/{acme.issues[0]}", headers=auth(acme.member))
    assert page(client, acme.member, acme.issues[0]).status_code == 404


def test_list_in_an_archived_project_is_404(client, acme) -> None:
    assert listed(client, acme.member, acme.issues[0]) == list(ACME_COMMENTS)
    client.delete(f"/projects/{acme.projects[0]}", headers=auth(acme.admin))
    assert page(client, acme.member, acme.issues[0]).status_code == 404


# -- delete ---------------------------------------------------------------------------------------


def test_author_deletes_own_comment(client, acme) -> None:
    assert delete(client, acme.member, ACME_COMMENTS[0]).status_code == 204
    assert listed(client, acme.member, acme.issues[0]) == [ACME_COMMENTS[1]]


def test_admin_deletes_a_members_comment(client, globex) -> None:
    assert delete(client, globex.admin, GLOBEX_COMMENTS[0]).status_code == 204
    assert listed(client, globex.admin, globex.issues[0]) == [GLOBEX_COMMENTS[1]]


def test_member_cannot_delete_the_admins_comment(client, acme) -> None:
    response = delete(client, acme.member, ACME_COMMENTS[1])
    assert response.status_code == 403
    assert error_code(response) == "forbidden"
    assert listed(client, acme.member, acme.issues[0]) == list(ACME_COMMENTS)


def test_member_cannot_delete_another_members_comment(client, acme) -> None:
    user = client.post(
        "/users",
        json={"email": "second@acme.test", "name": "Second Member", "role": "member"},
        headers=auth(acme.admin),
    ).json()
    other = post(client, user["id"], acme.issues[0]).json()["id"]
    assert delete(client, acme.member, other).status_code == 403
    assert delete(client, user["id"], other).status_code == 204


def test_viewer_cannot_delete(client, acme) -> None:
    response = delete(client, acme.viewer, ACME_COMMENTS[0])
    assert response.status_code == 403
    assert listed(client, acme.viewer, acme.issues[0]) == list(ACME_COMMENTS)


def test_deleting_another_orgs_comment_is_404(client, acme, globex) -> None:
    response = delete(client, acme.admin, GLOBEX_COMMENTS[0])
    assert response.status_code == 404
    assert error_code(response) == "not_found"
    assert listed(client, globex.admin, globex.issues[0]) == list(GLOBEX_COMMENTS)


def test_deleting_twice_is_404(client, acme) -> None:
    assert delete(client, acme.member, ACME_COMMENTS[0]).status_code == 204
    assert delete(client, acme.member, ACME_COMMENTS[0]).status_code == 404


def test_deleting_a_comment_of_a_deleted_issue_is_404(client, acme) -> None:
    assert listed(client, acme.admin, acme.issues[0]) == list(ACME_COMMENTS)
    client.delete(f"/issues/{acme.issues[0]}", headers=auth(acme.member))
    assert delete(client, acme.admin, ACME_COMMENTS[1]).status_code == 404


# -- audit ----------------------------------------------------------------------------------------


def test_create_adds_one_comment_create_row(client, acme) -> None:
    before = audit(client, acme)
    comment = post(client, acme.member, acme.issues[0]).json()
    rows = audit(client, acme)[len(before) :]
    assert [(r["action"], r["entity"], r["entity_id"]) for r in rows] == [
        ("comment.create", "comment", comment["id"])
    ]
    assert rows[0]["actor_id"] == acme.member


def test_delete_adds_one_comment_delete_row(client, acme) -> None:
    before = audit(client, acme)
    assert delete(client, acme.admin, ACME_COMMENTS[0]).status_code == 204
    rows = audit(client, acme)[len(before) :]
    assert [(r["action"], r["entity"], r["entity_id"]) for r in rows] == [
        ("comment.delete", "comment", ACME_COMMENTS[0])
    ]


def test_refused_writes_add_no_audit_rows(client, acme) -> None:
    assert listed(client, acme.member, acme.issues[0]) == list(ACME_COMMENTS)
    before = audit(client, acme)
    post(client, acme.viewer, acme.issues[0])
    post(client, acme.member, acme.issues[0], "")
    delete(client, acme.member, ACME_COMMENTS[1])
    assert audit(client, acme) == before


def test_listing_adds_no_audit_row(client, acme) -> None:
    before = audit(client, acme)
    assert listed(client, acme.member, acme.issues[0]) == list(ACME_COMMENTS)
    assert audit(client, acme) == before


# -- idempotency ----------------------------------------------------------------------------------


def test_same_key_and_body_replays_the_first_response(client, acme) -> None:
    first = post(client, acme.member, acme.issues[0], "Once", **{"Idempotency-Key": "k1"})
    again = post(client, acme.member, acme.issues[0], "Once", **{"Idempotency-Key": "k1"})
    assert (again.status_code, again.json()) == (201, first.json())


def test_replay_creates_nothing_and_adds_no_audit_row(client, acme) -> None:
    post(client, acme.member, acme.issues[0], "Once", **{"Idempotency-Key": "k2"})
    before = audit(client, acme)
    post(client, acme.member, acme.issues[0], "Once", **{"Idempotency-Key": "k2"})
    assert len(listed(client, acme.member, acme.issues[0])) == 3
    assert audit(client, acme) == before


def test_same_key_with_another_body_is_409(client, acme) -> None:
    post(client, acme.member, acme.issues[0], "Once", **{"Idempotency-Key": "k3"})
    response = post(client, acme.member, acme.issues[0], "Twice", **{"Idempotency-Key": "k3"})
    assert response.status_code == 409
    assert error_code(response) == "idempotency_conflict"
    assert len(listed(client, acme.member, acme.issues[0])) == 3


def test_keys_are_scoped_per_org(client, acme, globex) -> None:
    mine = post(client, acme.member, acme.issues[0], "Mine", **{"Idempotency-Key": "k4"})
    theirs = post(client, globex.member, globex.issues[0], "Theirs", **{"Idempotency-Key": "k4"})
    assert mine.status_code == theirs.status_code == 201
    assert theirs.json()["org_id"] == globex.org_id
