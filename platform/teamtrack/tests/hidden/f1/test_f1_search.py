"""F1 hidden tests: GET /issues (spec: docs/features/f1.md)."""

from __future__ import annotations

from hidden_support import auth, error_code

# Seed (app/seed.py): ten issues per project, all open. Title n, priority n % 3 (low, medium,
# high), assigned to the org's member when n is even. Acme: project 1 = issues 1-10, project 2 =
# issues 11-20. Globex: project 3 = 21-30, project 4 = 31-40.


def get(client, user_id: int, query: str = ""):  # type: ignore[no-untyped-def]
    return client.get(f"/issues{query}", headers=auth(user_id))


def ids(response) -> list[int]:  # type: ignore[no-untyped-def]
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


def write(client, user_id: int, issue_id: int, action: str, body: dict) -> None:  # type: ignore[no-untyped-def]
    version = client.get(f"/issues/{issue_id}", headers=auth(user_id)).json()["version"]
    headers = {**auth(user_id), "If-Match": f'"{version}"'}
    response = client.post(f"/issues/{issue_id}/{action}", json=body, headers=headers)
    assert response.status_code == 200, response.text


def new_issue(client, user_id: int, project_id: int, title: str, **body) -> int:  # type: ignore[no-untyped-def]
    response = client.post(
        f"/projects/{project_id}/issues", json={"title": title, **body}, headers=auth(user_id)
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


# -- envelope, scope, roles ----------------------------------------------------------------------


def test_lists_every_issue_of_the_org(client, acme) -> None:
    assert ids(get(client, acme.member, "?limit=100")) == list(acme.issues)


def test_never_lists_another_orgs_issues(client, acme, globex) -> None:
    found = ids(get(client, globex.admin, "?limit=100"))
    assert found == list(globex.issues)
    assert not set(found) & set(acme.issues)


def test_items_belong_to_the_callers_org(client, globex) -> None:
    items = get(client, globex.member, "?limit=100").json()["items"]
    assert {item["org_id"] for item in items} == {globex.org_id}


def test_response_is_the_list_envelope(client, acme) -> None:
    body = get(client, acme.member).json()
    assert set(body) == {"items", "next_cursor"}
    assert isinstance(body["items"], list)


def test_items_have_the_issue_out_shape(client, acme) -> None:
    item = get(client, acme.member, "?limit=1").json()["items"][0]
    single = client.get(f"/issues/{item['id']}", headers=auth(acme.member)).json()
    assert set(item) == set(single)
    assert item == single


def test_viewer_can_search(client, acme) -> None:
    assert len(ids(get(client, acme.viewer, "?limit=100"))) == 20


def test_admin_can_search(client, acme) -> None:
    assert len(ids(get(client, acme.admin, "?limit=100"))) == 20


def test_requires_a_token(client, acme) -> None:
    response = client.get("/issues")
    assert response.status_code == 401
    assert ids(get(client, acme.member)) != []


def test_search_adds_no_audit_row(client, acme) -> None:
    before = len(client.get("/audit?limit=100", headers=auth(acme.admin)).json()["items"])
    assert ids(get(client, acme.member, "?q=login"))
    after = len(client.get("/audit?limit=100", headers=auth(acme.admin)).json()["items"])
    assert after == before


# -- pagination -----------------------------------------------------------------------------------


def test_default_limit_is_20(client, acme) -> None:
    new_issue(client, acme.member, acme.projects[0], "Twenty-first")
    body = get(client, acme.member).json()
    assert len(body["items"]) == 20
    assert body["next_cursor"] is not None


def test_last_page_has_no_cursor(client, acme) -> None:
    assert get(client, acme.member).json()["next_cursor"] is None


def test_limit_caps_the_page(client, acme) -> None:
    body = get(client, acme.member, "?limit=5").json()
    assert [item["id"] for item in body["items"]] == list(acme.issues[:5])
    assert body["next_cursor"] is not None


def test_cursor_walks_every_issue_once_in_id_order(client, acme) -> None:
    seen: list[int] = []
    cursor = None
    for _ in range(10):
        body = get(client, acme.member, "?limit=6" + (f"&cursor={cursor}" if cursor else "")).json()
        seen.extend(item["id"] for item in body["items"])
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert seen == list(acme.issues)


def test_cursor_keeps_filters(client, acme) -> None:
    seen: list[int] = []
    cursor = None
    for _ in range(10):
        query = "?priority=low&limit=3" + (f"&cursor={cursor}" if cursor else "")
        body = get(client, acme.member, query).json()
        seen.extend(item["id"] for item in body["items"])
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert seen == [1, 4, 7, 10, 11, 14, 17, 20]


def test_limit_over_100_is_422(client, acme) -> None:
    response = get(client, acme.member, "?limit=101")
    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    assert ids(get(client, acme.member, "?limit=100"))


def test_limit_zero_is_422(client, acme) -> None:
    assert get(client, acme.member, "?limit=0").status_code == 422
    assert ids(get(client, acme.member, "?limit=1"))


# -- filters --------------------------------------------------------------------------------------


def test_status_filter(client, acme) -> None:
    write(client, acme.member, acme.issues[4], "transition", {"status": "in_progress"})
    write(client, acme.member, acme.issues[12], "transition", {"status": "in_progress"})
    assert ids(get(client, acme.member, "?status=in_progress")) == [5, 13]


def test_status_open_excludes_moved_issues(client, acme) -> None:
    write(client, acme.member, acme.issues[0], "transition", {"status": "in_progress"})
    found = ids(get(client, acme.member, "?status=open&limit=100"))
    assert acme.issues[0] not in found
    assert len(found) == 19


def test_status_done(client, acme) -> None:
    write(client, acme.member, acme.issues[1], "transition", {"status": "in_progress"})
    write(client, acme.member, acme.issues[1], "transition", {"status": "done"})
    assert ids(get(client, acme.member, "?status=done")) == [2]


def test_priority_low(client, acme) -> None:
    assert ids(get(client, acme.member, "?priority=low&limit=100")) == [1, 4, 7, 10, 11, 14, 17, 20]


def test_priority_medium(client, acme) -> None:
    assert ids(get(client, acme.member, "?priority=medium&limit=100")) == [2, 5, 8, 12, 15, 18]


def test_priority_high_in_globex(client, globex) -> None:
    assert ids(get(client, globex.member, "?priority=high&limit=100")) == [23, 26, 29, 33, 36, 39]


def test_assignee_filter(client, acme) -> None:
    expected = [i for i in acme.issues if (i - 1) % 10 % 2 == 0]
    assert ids(get(client, acme.member, f"?assignee_id={acme.member}&limit=100")) == expected


def test_assignee_without_issues_gives_an_empty_list(client, acme) -> None:
    assert ids(get(client, acme.member, f"?assignee_id={acme.admin}")) == []


def test_assignee_filter_follows_reassignment(client, acme) -> None:
    write(client, acme.member, acme.issues[1], "assign", {"assignee_id": acme.viewer})
    assert ids(get(client, acme.member, f"?assignee_id={acme.viewer}")) == [2]


def test_project_filter(client, acme) -> None:
    assert ids(get(client, acme.member, f"?project_id={acme.projects[1]}&limit=100")) == list(
        acme.issues[10:]
    )


def test_q_matches_a_title_substring(client, acme) -> None:
    assert ids(get(client, acme.member, "?q=page&limit=100")) == [1, 3, 11, 13]


def test_q_ignores_case(client, acme) -> None:
    assert ids(get(client, acme.member, "?q=PaGe&limit=100")) == [1, 3, 11, 13]


def test_q_matches_inside_words(client, acme) -> None:
    assert ids(get(client, acme.member, "?q=ashboa")) == [9, 19]


def test_q_without_matches_gives_an_empty_list(client, acme) -> None:
    body = get(client, acme.member, "?q=no-such-title").json()
    assert body == {"items": [], "next_cursor": None}


def test_q_underscore_is_literal(client, acme) -> None:
    assert ids(get(client, acme.member, "?q=_")) == []
    created = new_issue(client, acme.member, acme.projects[0], "snake_case field")
    assert ids(get(client, acme.member, "?q=_")) == [created]


def test_q_percent_is_literal(client, acme) -> None:
    assert ids(get(client, acme.member, "?q=%25")) == []
    created = new_issue(client, acme.member, acme.projects[0], "Discount 100% wrong")
    assert ids(get(client, acme.member, "?q=0%25")) == [created]


def test_q_of_100_characters_is_accepted(client, acme) -> None:
    assert ids(get(client, acme.member, "?q=" + "x" * 100)) == []


def test_filters_combine_with_and(client, acme) -> None:
    query = f"?project_id={acme.projects[1]}&priority=high&assignee_id={acme.member}"
    assert ids(get(client, acme.member, query)) == [13, 19]


def test_q_and_status_combine(client, acme) -> None:
    write(client, acme.member, acme.issues[10], "transition", {"status": "in_progress"})
    assert ids(get(client, acme.member, "?q=login&status=in_progress")) == [11]


def test_new_issue_is_found(client, acme) -> None:
    created = new_issue(client, acme.member, acme.projects[1], "Fresh search target")
    assert ids(get(client, acme.member, "?q=fresh search")) == [created]


# -- excluded rows --------------------------------------------------------------------------------


def test_deleted_issues_are_excluded(client, acme) -> None:
    client.delete(f"/issues/{acme.issues[2]}", headers=auth(acme.member))
    found = ids(get(client, acme.member, "?limit=100"))
    assert acme.issues[2] not in found
    assert len(found) == 19


def test_deleted_issue_is_excluded_from_filtered_results(client, acme) -> None:
    client.delete(f"/issues/{acme.issues[0]}", headers=auth(acme.member))
    assert ids(get(client, acme.member, "?q=login")) == [11]


def test_archived_projects_issues_are_excluded(client, acme) -> None:
    client.delete(f"/projects/{acme.projects[0]}", headers=auth(acme.admin))
    assert ids(get(client, acme.member, "?limit=100")) == list(acme.issues[10:])


# -- 404 and 422 ----------------------------------------------------------------------------------


def test_project_of_another_org_is_404(client, acme, globex) -> None:
    response = get(client, acme.member, f"?project_id={globex.projects[0]}")
    assert response.status_code == 404
    assert error_code(response) == "not_found"
    assert ids(get(client, acme.member, f"?project_id={acme.projects[0]}"))


def test_unknown_project_is_404(client, acme) -> None:
    assert get(client, acme.member, "?project_id=9999").status_code == 404
    assert ids(get(client, acme.member, f"?project_id={acme.projects[1]}"))


def test_archived_project_is_404(client, acme) -> None:
    assert ids(get(client, acme.member, f"?project_id={acme.projects[1]}"))
    client.delete(f"/projects/{acme.projects[1]}", headers=auth(acme.admin))
    response = get(client, acme.member, f"?project_id={acme.projects[1]}")
    assert response.status_code == 404
    assert error_code(response) == "not_found"


def test_assignee_of_another_org_is_404(client, acme, globex) -> None:
    response = get(client, acme.member, f"?assignee_id={globex.member}")
    assert response.status_code == 404
    assert error_code(response) == "not_found"
    assert ids(get(client, acme.member, f"?assignee_id={acme.member}"))


def test_unknown_assignee_is_404(client, acme) -> None:
    assert get(client, acme.member, "?assignee_id=9999").status_code == 404
    assert ids(get(client, acme.member, f"?assignee_id={acme.member}"))


def test_unknown_status_is_422(client, acme) -> None:
    response = get(client, acme.member, "?status=closed")
    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_unknown_priority_is_422(client, acme) -> None:
    response = get(client, acme.member, "?priority=urgent")
    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_non_integer_ids_are_422(client, acme) -> None:
    assert get(client, acme.member, "?assignee_id=abc").status_code == 422
    assert get(client, acme.member, "?project_id=1.5").status_code == 422


def test_empty_q_is_422(client, acme) -> None:
    response = get(client, acme.member, "?q=")
    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_q_over_100_characters_is_422(client, acme) -> None:
    response = get(client, acme.member, "?q=" + "x" * 101)
    assert response.status_code == 422
    assert error_code(response) == "validation_error"
