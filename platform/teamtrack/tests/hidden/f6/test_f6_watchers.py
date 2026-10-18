"""F6 hidden tests: watchers (spec: docs/features/f6.md)."""

from __future__ import annotations

from hidden_support import auth, error_code

# Seed: each org's member watches the org's first two issues (watchers 1-2 Acme, 3-4 Globex).


def watch(client, user_id: int, issue_id: int, who: str | int = "me"):  # type: ignore[no-untyped-def]
    return client.put(f"/issues/{issue_id}/watchers/{who}", headers=auth(user_id))


def unwatch(client, user_id: int, issue_id: int, who: str | int = "me"):  # type: ignore[no-untyped-def]
    return client.delete(f"/issues/{issue_id}/watchers/{who}", headers=auth(user_id))


def watchers_page(client, user_id: int, issue_id: int, query: str = "?limit=100"):  # type: ignore[no-untyped-def]
    return client.get(f"/issues/{issue_id}/watchers{query}", headers=auth(user_id))


def watchers(client, user_id: int, issue_id: int) -> list[int]:  # type: ignore[no-untyped-def]
    response = watchers_page(client, user_id, issue_id)
    assert response.status_code == 200, response.text
    return [w["user_id"] for w in response.json()["items"]]


def watching_page(client, user_id: int, query: str = "?limit=100"):  # type: ignore[no-untyped-def]
    return client.get(f"/me/watching{query}", headers=auth(user_id))


def watching(client, user_id: int) -> list[int]:  # type: ignore[no-untyped-def]
    response = watching_page(client, user_id)
    assert response.status_code == 200, response.text
    return [i["id"] for i in response.json()["items"]]


def audit(client, o) -> list[dict]:  # type: ignore[no-untyped-def]
    return client.get("/audit?limit=100", headers=auth(o.admin)).json()["items"]


# -- seed and reads -------------------------------------------------------------------------------


def test_seeded_watchers_of_the_first_issue(client, acme) -> None:
    assert watchers(client, acme.member, acme.issues[0]) == [acme.member]


def test_seeded_watching_list(client, globex) -> None:
    assert watching(client, globex.member) == [globex.issues[0], globex.issues[1]]


def test_watcher_items_have_user_and_time(client, acme) -> None:
    items = watchers_page(client, acme.viewer, acme.issues[0]).json()["items"]
    assert set(items[0]) == {"user_id", "created_at"}


def test_watchers_list_uses_the_envelope(client, acme) -> None:
    body = watchers_page(client, acme.member, acme.issues[0], "").json()
    assert set(body) == {"items", "next_cursor"}


def test_issue_without_watchers_has_an_empty_list(client, acme) -> None:
    assert watchers_page(client, acme.member, acme.issues[9]).json() == {
        "items": [],
        "next_cursor": None,
    }


def test_watching_items_are_issue_out(client, acme) -> None:
    item = watching_page(client, acme.member).json()["items"][0]
    single = client.get(f"/issues/{item['id']}", headers=auth(acme.member)).json()
    assert item == single


def test_watching_list_uses_the_envelope(client, acme) -> None:
    body = watching_page(client, acme.member, "").json()
    assert set(body) == {"items", "next_cursor"}


def test_admin_watches_nothing_at_first(client, acme) -> None:
    assert watching_page(client, acme.admin).json() == {"items": [], "next_cursor": None}


def test_viewer_can_read_both_lists(client, acme) -> None:
    assert watchers(client, acme.viewer, acme.issues[1]) == [acme.member]
    assert watching(client, acme.viewer) == []


def test_reads_require_a_token(client, acme) -> None:
    assert client.get("/me/watching").status_code == 401
    assert watching(client, acme.member) == [acme.issues[0], acme.issues[1]]


# -- watch / unwatch myself -----------------------------------------------------------------------


def test_watch_returns_204(client, acme) -> None:
    response = watch(client, acme.admin, acme.issues[4])
    assert response.status_code == 204
    assert response.content == b""


def test_watched_issue_shows_the_caller_as_watcher(client, acme) -> None:
    watch(client, acme.admin, acme.issues[4])
    assert watchers(client, acme.member, acme.issues[4]) == [acme.admin]


def test_watched_issue_appears_in_my_watching(client, acme) -> None:
    watch(client, acme.member, acme.issues[7])
    assert watching(client, acme.member) == [acme.issues[0], acme.issues[1], acme.issues[7]]


def test_watchers_are_listed_in_the_order_added(client, acme) -> None:
    watch(client, acme.admin, acme.issues[0])
    assert watchers(client, acme.member, acme.issues[0]) == [acme.member, acme.admin]


def test_watching_is_ordered_by_issue_id(client, acme) -> None:
    watch(client, acme.admin, acme.issues[12])
    watch(client, acme.admin, acme.issues[3])
    assert watching(client, acme.admin) == [acme.issues[3], acme.issues[12]]


def test_watching_twice_returns_204_and_changes_nothing(client, acme) -> None:
    assert watch(client, acme.member, acme.issues[0]).status_code == 204
    assert watchers(client, acme.member, acme.issues[0]) == [acme.member]


def test_watching_twice_adds_no_audit_row(client, acme) -> None:
    assert watchers(client, acme.member, acme.issues[0]) == [acme.member]
    before = audit(client, acme)
    watch(client, acme.member, acme.issues[0])
    assert audit(client, acme) == before


def test_unwatch_returns_204(client, acme) -> None:
    response = unwatch(client, acme.member, acme.issues[0])
    assert response.status_code == 204
    assert watchers(client, acme.member, acme.issues[0]) == []


def test_unwatched_issue_leaves_my_watching(client, acme) -> None:
    unwatch(client, acme.member, acme.issues[1])
    assert watching(client, acme.member) == [acme.issues[0]]


def test_unwatch_when_not_watching_returns_204_without_audit(client, acme) -> None:
    assert watchers(client, acme.admin, acme.issues[5]) == []
    before = audit(client, acme)
    assert unwatch(client, acme.admin, acme.issues[5]).status_code == 204
    assert audit(client, acme) == before


def test_watch_unwatch_watch_again(client, acme) -> None:
    watch(client, acme.admin, acme.issues[8])
    unwatch(client, acme.admin, acme.issues[8])
    assert watch(client, acme.admin, acme.issues[8]).status_code == 204
    assert watchers(client, acme.admin, acme.issues[8]) == [acme.admin]


def test_viewer_cannot_watch(client, acme) -> None:
    response = watch(client, acme.viewer, acme.issues[0])
    assert response.status_code == 403
    assert error_code(response) == "forbidden"
    assert watchers(client, acme.viewer, acme.issues[0]) == [acme.member]


def test_viewer_cannot_unwatch(client, acme) -> None:
    response = unwatch(client, acme.viewer, acme.issues[0])
    assert response.status_code == 403
    assert watchers(client, acme.viewer, acme.issues[0]) == [acme.member]


# -- tenant isolation and deleted issues ----------------------------------------------------------


def test_watching_another_orgs_issue_is_404(client, acme, globex) -> None:
    response = watch(client, acme.member, globex.issues[0])
    assert response.status_code == 404
    assert error_code(response) == "not_found"
    assert watchers(client, globex.member, globex.issues[0]) == [globex.member]


def test_unwatching_another_orgs_issue_is_404(client, acme, globex) -> None:
    assert unwatch(client, acme.member, globex.issues[0]).status_code == 404
    assert watchers(client, globex.member, globex.issues[0]) == [globex.member]


def test_listing_watchers_of_another_orgs_issue_is_404(client, acme, globex) -> None:
    response = watchers_page(client, acme.admin, globex.issues[0])
    assert response.status_code == 404
    assert watchers(client, acme.admin, acme.issues[0]) == [acme.member]


def test_watching_lists_only_my_org(client, acme, globex) -> None:
    watch(client, globex.admin, globex.issues[5])
    assert watching(client, acme.admin) == []
    assert watching(client, globex.admin) == [globex.issues[5]]


def test_deleted_issue_is_404_for_watch(client, acme) -> None:
    client.delete(f"/issues/{acme.issues[6]}", headers=auth(acme.member))
    assert watch(client, acme.admin, acme.issues[6]).status_code == 404
    assert watch(client, acme.admin, acme.issues[7]).status_code == 204


def test_deleted_issue_is_404_for_the_watchers_list(client, acme) -> None:
    assert watchers(client, acme.member, acme.issues[0]) == [acme.member]
    client.delete(f"/issues/{acme.issues[0]}", headers=auth(acme.member))
    assert watchers_page(client, acme.member, acme.issues[0]).status_code == 404


def test_deleted_issue_leaves_my_watching(client, acme) -> None:
    client.delete(f"/issues/{acme.issues[0]}", headers=auth(acme.member))
    assert watching(client, acme.member) == [acme.issues[1]]


def test_archived_projects_issues_leave_my_watching(client, acme) -> None:
    watch(client, acme.member, acme.issues[10])
    client.delete(f"/projects/{acme.projects[0]}", headers=auth(acme.admin))
    assert watching(client, acme.member) == [acme.issues[10]]


def test_issue_in_an_archived_project_is_404(client, acme) -> None:
    assert watch(client, acme.admin, acme.issues[11]).status_code == 204
    client.delete(f"/projects/{acme.projects[1]}", headers=auth(acme.admin))
    assert watch(client, acme.member, acme.issues[11]).status_code == 404


# -- admin endpoints ------------------------------------------------------------------------------


def test_admin_adds_a_watcher(client, acme) -> None:
    assert watch(client, acme.admin, acme.issues[3], acme.viewer).status_code == 204
    assert watchers(client, acme.admin, acme.issues[3]) == [acme.viewer]


def test_added_user_sees_the_issue_in_watching(client, acme) -> None:
    watch(client, acme.admin, acme.issues[3], acme.viewer)
    assert watching(client, acme.viewer) == [acme.issues[3]]


def test_admin_removes_a_watcher(client, acme) -> None:
    assert unwatch(client, acme.admin, acme.issues[0], acme.member).status_code == 204
    assert watchers(client, acme.admin, acme.issues[0]) == []


def test_admin_adding_an_existing_watcher_changes_nothing(client, acme) -> None:
    assert watchers(client, acme.admin, acme.issues[0]) == [acme.member]
    before = audit(client, acme)
    assert watch(client, acme.admin, acme.issues[0], acme.member).status_code == 204
    assert audit(client, acme) == before


def test_admin_cannot_add_a_user_of_another_org(client, acme, globex) -> None:
    response = watch(client, acme.admin, acme.issues[0], globex.member)
    assert response.status_code == 404
    assert error_code(response) == "not_found"
    assert watchers(client, acme.admin, acme.issues[0]) == [acme.member]


def test_admin_cannot_add_an_unknown_user(client, acme) -> None:
    assert watch(client, acme.admin, acme.issues[0], 9999).status_code == 404
    assert watchers(client, acme.admin, acme.issues[0]) == [acme.member]


def test_admin_cannot_remove_a_user_of_another_org(client, acme, globex) -> None:
    assert unwatch(client, acme.admin, acme.issues[0], globex.member).status_code == 404
    assert watchers(client, acme.admin, acme.issues[0]) == [acme.member]


def test_admin_cannot_manage_another_orgs_issue(client, acme, globex) -> None:
    assert watch(client, acme.admin, globex.issues[0], acme.viewer).status_code == 404
    assert watchers(client, globex.admin, globex.issues[0]) == [globex.member]


def test_member_cannot_use_the_admin_endpoint(client, acme) -> None:
    response = watch(client, acme.member, acme.issues[0], acme.viewer)
    assert response.status_code == 403
    assert error_code(response) == "forbidden"
    assert watchers(client, acme.member, acme.issues[0]) == [acme.member]


def test_member_cannot_remove_others(client, acme) -> None:
    watch(client, acme.admin, acme.issues[4], acme.viewer)
    assert unwatch(client, acme.member, acme.issues[4], acme.viewer).status_code == 403
    assert watchers(client, acme.member, acme.issues[4]) == [acme.viewer]


def test_viewer_cannot_use_the_admin_endpoint(client, acme) -> None:
    assert watch(client, acme.viewer, acme.issues[0], acme.viewer).status_code == 403
    assert watching(client, acme.viewer) == []


# -- audit and pagination -------------------------------------------------------------------------


def test_watch_adds_one_watcher_add_row(client, acme) -> None:
    before = audit(client, acme)
    watch(client, acme.admin, acme.issues[4])
    rows = audit(client, acme)[len(before) :]
    assert [(r["action"], r["entity"], r["entity_id"]) for r in rows] == [
        ("watcher.add", "issue", acme.issues[4])
    ]


def test_unwatch_adds_one_watcher_remove_row(client, acme) -> None:
    before = audit(client, acme)
    unwatch(client, acme.member, acme.issues[0])
    rows = audit(client, acme)[len(before) :]
    assert [(r["action"], r["entity"], r["entity_id"]) for r in rows] == [
        ("watcher.remove", "issue", acme.issues[0])
    ]


def test_admin_add_is_audited_with_the_admin_as_actor(client, acme) -> None:
    watch(client, acme.admin, acme.issues[2], acme.viewer)
    row = audit(client, acme)[-1]
    assert (row["action"], row["actor_id"]) == ("watcher.add", acme.admin)


def test_refused_writes_add_no_audit_rows(client, acme, globex) -> None:
    assert watchers(client, acme.admin, acme.issues[0]) == [acme.member]
    before = audit(client, acme)
    watch(client, acme.viewer, acme.issues[0])
    watch(client, acme.member, acme.issues[0], acme.viewer)
    watch(client, acme.admin, acme.issues[0], globex.member)
    assert audit(client, acme) == before


def test_watching_paginates(client, acme) -> None:
    for issue_id in acme.issues[2:5]:
        watch(client, acme.member, issue_id)
    first = watching_page(client, acme.member, "?limit=2").json()
    assert [i["id"] for i in first["items"]] == list(acme.issues[:2])
    rest = watching_page(client, acme.member, f"?limit=2&cursor={first['next_cursor']}").json()
    assert [i["id"] for i in rest["items"]] == list(acme.issues[2:4])


def test_watchers_list_paginates(client, acme) -> None:
    watch(client, acme.admin, acme.issues[0])
    first = watchers_page(client, acme.member, acme.issues[0], "?limit=1").json()
    assert [w["user_id"] for w in first["items"]] == [acme.member]
    rest = watchers_page(
        client, acme.member, acme.issues[0], f"?limit=1&cursor={first['next_cursor']}"
    ).json()
    assert [w["user_id"] for w in rest["items"]] == [acme.admin]
    assert rest["next_cursor"] is None
