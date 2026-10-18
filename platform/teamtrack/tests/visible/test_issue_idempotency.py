"""F3: Idempotency-Key on POST /projects/{project_id}/issues (house rule R4)."""

from __future__ import annotations

from conftest import auth, error_code


def create(client, user_id: int, project_id: int, key: str | None, **body):  # type: ignore[no-untyped-def]
    headers = {**auth(user_id), **({"Idempotency-Key": key} if key else {})}
    payload = {"title": "Checkout button missing", **body}
    return client.post(f"/projects/{project_id}/issues", json=payload, headers=headers)


def count_issues(client, user_id: int, project_id: int) -> int:  # type: ignore[no-untyped-def]
    path = f"/projects/{project_id}/issues?limit=100"
    return len(client.get(path, headers=auth(user_id)).json()["items"])


def audit_count(client, o) -> int:  # type: ignore[no-untyped-def]
    return len(client.get("/audit?limit=100", headers=auth(o.admin)).json()["items"])


def test_same_key_and_body_returns_the_first_response(client, acme) -> None:
    first = create(client, acme.member, acme.projects[0], "k-1")
    second = create(client, acme.member, acme.projects[0], "k-1")
    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json() == first.json()


def test_replay_creates_nothing(client, acme) -> None:
    create(client, acme.member, acme.projects[0], "k-2")
    before = count_issues(client, acme.member, acme.projects[0])
    create(client, acme.member, acme.projects[0], "k-2")
    assert count_issues(client, acme.member, acme.projects[0]) == before


def test_replay_adds_no_audit_row(client, acme) -> None:
    create(client, acme.member, acme.projects[0], "k-3")
    before = audit_count(client, acme)
    create(client, acme.member, acme.projects[0], "k-3")
    assert audit_count(client, acme) == before


def test_same_key_with_a_different_body_is_409(client, acme) -> None:
    create(client, acme.member, acme.projects[0], "k-4")
    before = count_issues(client, acme.member, acme.projects[0])
    response = create(client, acme.member, acme.projects[0], "k-4", title="Another title")
    assert response.status_code == 409
    assert error_code(response) == "idempotency_conflict"
    assert count_issues(client, acme.member, acme.projects[0]) == before


def test_keys_are_scoped_per_org(client, acme, globex) -> None:
    mine = create(client, acme.member, acme.projects[0], "shared")
    theirs = create(client, globex.member, globex.projects[0], "shared", title="Globex issue")
    assert mine.status_code == theirs.status_code == 201
    assert theirs.json()["org_id"] == globex.org_id


def test_keys_are_scoped_per_endpoint(client, acme) -> None:
    headers = {**auth(acme.member), "Idempotency-Key": "k-5"}
    project = client.post("/projects", json={"name": "Keys", "key": "KEYS"}, headers=headers)
    assert project.status_code == 201
    issue = create(client, acme.member, acme.projects[0], "k-5")
    assert issue.status_code == 201
    assert issue.json()["project_id"] == acme.projects[0]


def test_each_project_has_its_own_key_space(client, acme) -> None:
    first = create(client, acme.member, acme.projects[0], "k-6")
    second = create(client, acme.member, acme.projects[1], "k-6")
    assert second.status_code == 201
    assert second.json()["id"] != first.json()["id"]
    assert second.json()["project_id"] == acme.projects[1]


def test_without_a_key_every_request_creates(client, acme) -> None:
    first = create(client, acme.member, acme.projects[0], None)
    second = create(client, acme.member, acme.projects[0], None)
    assert first.json()["id"] != second.json()["id"]


def test_a_failed_create_is_not_stored(client, acme, globex) -> None:
    assert create(client, acme.member, globex.projects[0], "k-7").status_code == 404
    assert create(client, acme.member, acme.projects[0], "k-7").status_code == 201


def test_viewer_with_a_key_is_still_403(client, acme) -> None:
    response = create(client, acme.viewer, acme.projects[0], "k-8")
    assert response.status_code == 403
    assert error_code(response) == "forbidden"
