"""F1: org-wide issue search (GET /issues) with filters and cursor pagination."""

from __future__ import annotations

from conftest import auth, error_code


def search(client, user_id: int, query: str = ""):  # type: ignore[no-untyped-def]
    return client.get(f"/issues{query}", headers=auth(user_id))


def ids(response) -> list[int]:  # type: ignore[no-untyped-def]
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


def change(client, o, issue_id: int, action: str, body: dict):  # type: ignore[no-untyped-def]
    version = client.get(f"/issues/{issue_id}", headers=auth(o.member)).json()["version"]
    headers = {**auth(o.member), "If-Match": f'"{version}"'}
    response = client.post(f"/issues/{issue_id}/{action}", json=body, headers=headers)
    assert response.status_code == 200, response.text


def test_search_returns_only_the_callers_org(client, acme, globex) -> None:
    found = ids(search(client, acme.member, "?limit=100"))
    assert sorted(found) == list(acme.issues)
    assert not set(found) & set(globex.issues)


def test_search_uses_the_list_envelope_and_issue_fields(client, acme) -> None:
    body = search(client, acme.viewer, "?limit=1").json()
    assert set(body) == {"items", "next_cursor"}
    assert body["items"][0]["org_id"] == acme.org_id
    assert {"id", "project_id", "title", "status", "priority", "version"} <= set(body["items"][0])


def test_default_page_size_is_20(client, acme) -> None:
    client.post(
        f"/projects/{acme.projects[1]}/issues",
        json={"title": "One more"},
        headers=auth(acme.member),
    )
    body = search(client, acme.member).json()
    assert len(body["items"]) == 20
    assert body["next_cursor"] is not None


def test_cursor_walks_every_issue_once_in_id_order(client, acme) -> None:
    seen: list[int] = []
    cursor = None
    for _ in range(10):
        query = "?limit=7" + (f"&cursor={cursor}" if cursor else "")
        body = search(client, acme.member, query).json()
        seen.extend(item["id"] for item in body["items"])
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert seen == list(acme.issues)


def test_filter_by_status(client, acme) -> None:
    change(client, acme, acme.issues[3], "transition", {"status": "in_progress"})
    assert ids(search(client, acme.member, "?status=in_progress")) == [acme.issues[3]]


def test_filter_by_priority(client, acme) -> None:
    found = ids(search(client, acme.member, "?priority=high&limit=100"))
    issues = [client.get(f"/issues/{i}", headers=auth(acme.member)).json() for i in found]
    assert found and all(issue["priority"] == "high" for issue in issues)


def test_filter_by_assignee(client, acme) -> None:
    change(client, acme, acme.issues[1], "assign", {"assignee_id": acme.viewer})
    assert ids(search(client, acme.member, f"?assignee_id={acme.viewer}")) == [acme.issues[1]]


def test_filter_by_project(client, acme) -> None:
    found = ids(search(client, acme.member, f"?project_id={acme.projects[1]}&limit=100"))
    assert found == list(acme.issues[10:])


def test_q_is_a_case_insensitive_title_substring(client, acme) -> None:
    found = ids(search(client, acme.member, "?q=LOGIN%20page&limit=100"))
    assert found == [acme.issues[0], acme.issues[10]]


def test_q_treats_percent_as_a_literal_character(client, acme) -> None:
    client.post(
        f"/projects/{acme.projects[0]}/issues",
        json={"title": "Discount 100% off"},
        headers=auth(acme.member),
    )
    found = ids(search(client, acme.member, "?q=100%25&limit=100"))
    assert len(found) == 1


def test_filters_combine_with_and(client, acme) -> None:
    query = f"?project_id={acme.projects[0]}&priority=low&q=login"
    assert ids(search(client, acme.member, query)) == [acme.issues[0]]


def test_deleted_issues_are_excluded(client, acme) -> None:
    client.delete(f"/issues/{acme.issues[0]}", headers=auth(acme.member))
    assert acme.issues[0] not in ids(search(client, acme.member, "?limit=100"))


def test_issues_of_archived_projects_are_excluded(client, acme) -> None:
    client.delete(f"/projects/{acme.projects[1]}", headers=auth(acme.admin))
    assert ids(search(client, acme.member, "?limit=100")) == list(acme.issues[:10])


def test_project_of_another_org_is_404(client, acme, globex) -> None:
    response = search(client, acme.member, f"?project_id={globex.projects[0]}")
    assert response.status_code == 404
    assert error_code(response) == "not_found"


def test_archived_project_filter_is_404(client, acme) -> None:
    client.delete(f"/projects/{acme.projects[1]}", headers=auth(acme.admin))
    response = search(client, acme.member, f"?project_id={acme.projects[1]}")
    assert response.status_code == 404


def test_assignee_of_another_org_is_404(client, acme, globex) -> None:
    response = search(client, acme.member, f"?assignee_id={globex.member}")
    assert response.status_code == 404
    assert error_code(response) == "not_found"


def test_invalid_filter_values_are_422(client, acme) -> None:
    for query in (
        "?status=closed",
        "?priority=urgent",
        "?assignee_id=abc",
        "?q=",
        "?q=" + "x" * 101,
    ):
        response = search(client, acme.member, query)
        assert response.status_code == 422, query
        assert error_code(response) == "validation_error"


def test_search_requires_authentication(client) -> None:
    assert client.get("/issues").status_code == 401
