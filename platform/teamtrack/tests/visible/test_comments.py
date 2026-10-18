"""F2: comments on issues (API and the board's comments panel)."""

from __future__ import annotations

import re

from conftest import auth, error_code

ACME_COMMENTS = (1, 2)  # seeded on Acme's first issue: by the member, then by the admin
GLOBEX_COMMENTS = (3, 4)


def post(client, user_id: int, issue_id: int, body: str = "Looks good", **headers):  # type: ignore[no-untyped-def]
    return client.post(
        f"/issues/{issue_id}/comments", json={"body": body}, headers={**auth(user_id), **headers}
    )


def listed(client, user_id: int, issue_id: int) -> list[dict]:  # type: ignore[no-untyped-def]
    response = client.get(f"/issues/{issue_id}/comments?limit=100", headers=auth(user_id))
    assert response.status_code == 200, response.text
    return response.json()["items"]


def audit_actions(client, o) -> list[str]:  # type: ignore[no-untyped-def]
    items = client.get("/audit?limit=100", headers=auth(o.admin)).json()["items"]
    return [item["action"] for item in items]


def test_create_comment_returns_201_and_the_comment(client, acme) -> None:
    response = post(client, acme.member, acme.issues[1], "First!")
    assert response.status_code == 201
    comment = response.json()
    assert set(comment) == {"id", "org_id", "issue_id", "author_id", "body", "created_at"}
    assert comment["issue_id"] == acme.issues[1]
    assert comment["author_id"] == acme.member
    assert comment["org_id"] == acme.org_id
    assert comment["body"] == "First!"


def test_list_is_oldest_first_and_includes_the_seed(client, acme) -> None:
    new_id = post(client, acme.admin, acme.issues[0]).json()["id"]
    assert [c["id"] for c in listed(client, acme.viewer, acme.issues[0])] == [
        *ACME_COMMENTS,
        new_id,
    ]


def test_list_uses_the_envelope_and_cursor(client, acme) -> None:
    body = client.get(f"/issues/{acme.issues[0]}/comments?limit=1", headers=auth(acme.member))
    page = body.json()
    assert set(page) == {"items", "next_cursor"}
    assert [c["id"] for c in page["items"]] == [ACME_COMMENTS[0]]
    rest = client.get(
        f"/issues/{acme.issues[0]}/comments?limit=1&cursor={page['next_cursor']}",
        headers=auth(acme.member),
    ).json()
    assert [c["id"] for c in rest["items"]] == [ACME_COMMENTS[1]]


def test_viewer_cannot_comment(client, acme) -> None:
    response = post(client, acme.viewer, acme.issues[0])
    assert response.status_code == 403
    assert error_code(response) == "forbidden"


def test_other_orgs_issue_is_404(client, acme, globex) -> None:
    assert post(client, acme.member, globex.issues[0]).status_code == 404
    response = client.get(f"/issues/{globex.issues[0]}/comments", headers=auth(acme.member))
    assert response.status_code == 404


def test_deleted_issue_is_404(client, acme) -> None:
    client.delete(f"/issues/{acme.issues[0]}", headers=auth(acme.member))
    assert post(client, acme.member, acme.issues[0]).status_code == 404
    response = client.get(f"/issues/{acme.issues[0]}/comments", headers=auth(acme.member))
    assert response.status_code == 404
    response = client.delete(f"/comments/{ACME_COMMENTS[0]}", headers=auth(acme.admin))
    assert response.status_code == 404


def test_issue_in_archived_project_is_404(client, acme) -> None:
    client.delete(f"/projects/{acme.projects[0]}", headers=auth(acme.admin))
    assert post(client, acme.member, acme.issues[0]).status_code == 404
    response = client.get(f"/issues/{acme.issues[0]}/comments", headers=auth(acme.member))
    assert response.status_code == 404


def test_body_must_be_1_to_5000_characters(client, acme) -> None:
    for body in ("", "x" * 5001):
        response = post(client, acme.member, acme.issues[0], body)
        assert response.status_code == 422
        assert error_code(response) == "validation_error"
    assert post(client, acme.member, acme.issues[0], "x" * 5000).status_code == 201


def test_author_can_delete_own_comment(client, acme) -> None:
    response = client.delete(f"/comments/{ACME_COMMENTS[0]}", headers=auth(acme.member))
    assert response.status_code == 204
    assert [c["id"] for c in listed(client, acme.member, acme.issues[0])] == [ACME_COMMENTS[1]]


def test_member_cannot_delete_someone_elses_comment(client, acme) -> None:
    response = client.delete(f"/comments/{ACME_COMMENTS[1]}", headers=auth(acme.member))
    assert response.status_code == 403
    assert error_code(response) == "forbidden"


def test_admin_can_delete_any_comment_in_the_org(client, acme) -> None:
    response = client.delete(f"/comments/{ACME_COMMENTS[0]}", headers=auth(acme.admin))
    assert response.status_code == 204


def test_other_orgs_comment_is_404(client, acme, globex) -> None:
    response = client.delete(f"/comments/{GLOBEX_COMMENTS[0]}", headers=auth(acme.admin))
    assert response.status_code == 404
    assert error_code(response) == "not_found"


def test_create_and_delete_each_add_one_audit_row(client, acme) -> None:
    before = audit_actions(client, acme)
    comment_id = post(client, acme.member, acme.issues[0]).json()["id"]
    assert audit_actions(client, acme)[len(before) :] == ["comment.create"]
    client.delete(f"/comments/{comment_id}", headers=auth(acme.member))
    assert audit_actions(client, acme)[len(before) :] == ["comment.create", "comment.delete"]


def test_refused_writes_add_no_audit_row(client, acme) -> None:
    before = audit_actions(client, acme)
    post(client, acme.viewer, acme.issues[0])
    client.delete(f"/comments/{ACME_COMMENTS[1]}", headers=auth(acme.member))
    assert audit_actions(client, acme) == before


def test_idempotency_key_replays_and_conflicts(client, acme) -> None:
    first = post(client, acme.member, acme.issues[0], "Once", **{"Idempotency-Key": "c-1"})
    again = post(client, acme.member, acme.issues[0], "Once", **{"Idempotency-Key": "c-1"})
    assert again.status_code == 201
    assert again.json() == first.json()
    assert len(listed(client, acme.member, acme.issues[0])) == 3
    other = post(client, acme.member, acme.issues[0], "Different", **{"Idempotency-Key": "c-1"})
    assert other.status_code == 409
    assert error_code(other) == "idempotency_conflict"


def login(client, email: str) -> None:  # type: ignore[no-untyped-def]
    response = client.post("/board/login", data={"email": email}, follow_redirects=False)
    assert response.status_code == 303


def test_board_issue_page_shows_the_comments_panel(client, acme) -> None:
    login(client, "member@acme.test")
    html = client.get(f"/board/issues/{acme.issues[0]}").text
    assert '<section class="comments"' in html
    found = re.findall(r'class="comment" data-comment-id="(\d+)"', html)
    assert found == [str(i) for i in ACME_COMMENTS]
    assert 'class="add-comment"' in html


def test_board_hides_the_comment_form_from_viewers(client, acme) -> None:
    login(client, "viewer@acme.test")
    html = client.get(f"/board/issues/{acme.issues[0]}").text
    assert '<section class="comments"' in html
    assert 'class="add-comment"' not in html


def test_board_adds_a_comment_and_escapes_it(client, acme) -> None:
    login(client, "member@acme.test")
    response = client.post(
        f"/board/issues/{acme.issues[0]}/comments",
        data={"body": "<b>bold</b> claim"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    html = client.get(f"/board/issues/{acme.issues[0]}").text
    assert "&lt;b&gt;bold&lt;/b&gt; claim" in html
    assert len(re.findall(r'class="comment" data-comment-id=', html)) == 3
