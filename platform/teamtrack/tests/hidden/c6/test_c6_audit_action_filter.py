"""C6 hidden tests: `GET /audit?action=` (spec: docs/features/c6.md). The seed writes no audit
rows, so each test makes the writes it lists."""

from __future__ import annotations

from hidden_support import auth, error_code


def new_issue(client, project: int, user: int, title: str) -> int:  # type: ignore[no-untyped-def]
    response = client.post(f"/projects/{project}/issues", json={"title": title}, headers=auth(user))
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def new_project(client, admin: int, key: str) -> int:  # type: ignore[no-untyped-def]
    response = client.post(
        "/projects", json={"name": f"Project {key}", "key": key}, headers=auth(admin)
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def test_filter_lists_only_that_action(client, acme) -> None:
    new_project(client, acme.admin, "AUD")
    issue = new_issue(client, acme.projects[0], acme.member, "Audited")
    body = client.get("/audit?action=issue.create", headers=auth(acme.admin)).json()
    assert [(row["action"], row["entity_id"]) for row in body["items"]] == [("issue.create", issue)]


def test_filter_with_no_match_is_an_empty_last_page(client, acme) -> None:
    new_project(client, acme.admin, "AUD")
    body = client.get("/audit?action=issue.delete", headers=auth(acme.admin)).json()
    assert body == {"items": [], "next_cursor": None}


def test_empty_action_is_a_validation_error(client, acme) -> None:
    response = client.get("/audit?action=", headers=auth(acme.admin))
    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_action_longer_than_50_characters_is_a_validation_error(client, acme) -> None:
    response = client.get("/audit?action=" + "a" * 51, headers=auth(acme.admin))
    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_filter_pages_with_the_cursor(client, acme) -> None:
    new_project(client, acme.admin, "AUD")
    created = [new_issue(client, acme.projects[0], acme.member, f"Issue {n}") for n in range(3)]
    page1 = client.get("/audit?action=issue.create&limit=2", headers=auth(acme.admin)).json()
    assert [row["entity_id"] for row in page1["items"]] == created[:2]
    page2 = client.get(
        f"/audit?action=issue.create&limit=2&cursor={page1['next_cursor']}",
        headers=auth(acme.admin),
    ).json()
    assert [row["entity_id"] for row in page2["items"]] == created[2:]
    assert page2["next_cursor"] is None


def test_filter_never_shows_another_orgs_rows(client, acme, globex) -> None:
    new_project(client, globex.admin, "GLB")
    new_issue(client, acme.projects[0], acme.member, "Acme only")
    body = client.get("/audit?action=issue.create", headers=auth(globex.admin)).json()
    assert body == {"items": [], "next_cursor": None}
