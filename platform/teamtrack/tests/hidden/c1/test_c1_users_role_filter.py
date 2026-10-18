"""C1 hidden tests: `GET /users?role=` (spec: docs/features/c1.md)."""

from __future__ import annotations

from hidden_support import auth, error_code


def ids(response) -> list[int]:  # type: ignore[no-untyped-def]
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


def add_member(client, admin: int, email: str) -> int:  # type: ignore[no-untyped-def]
    body = {"email": email, "name": email.split("@")[0], "role": "member"}
    response = client.post("/users", json=body, headers=auth(admin))
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def test_viewer_filter_lists_only_the_viewer(client, acme) -> None:
    assert ids(client.get("/users?role=viewer", headers=auth(acme.admin))) == [acme.viewer]


def test_admin_filter_lists_only_the_admin(client, acme) -> None:
    assert ids(client.get("/users?role=admin", headers=auth(acme.member))) == [acme.admin]


def test_filter_lists_only_the_callers_org(client, globex) -> None:
    response = client.get("/users?role=member", headers=auth(globex.viewer))
    assert ids(response) == [globex.member]
    assert {item["org_id"] for item in response.json()["items"]} == {globex.org_id}


def test_unknown_role_is_a_validation_error(client, acme) -> None:
    response = client.get("/users?role=owner", headers=auth(acme.admin))
    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_filtered_list_pages_with_the_cursor(client, acme) -> None:
    first = add_member(client, acme.admin, "second.member@acme.test")
    second = add_member(client, acme.admin, "third.member@acme.test")
    page1 = client.get("/users?role=member&limit=2", headers=auth(acme.admin)).json()
    assert [item["id"] for item in page1["items"]] == [acme.member, first]
    assert page1["next_cursor"]
    page2 = client.get(
        f"/users?role=member&limit=2&cursor={page1['next_cursor']}", headers=auth(acme.admin)
    ).json()
    assert [item["id"] for item in page2["items"]] == [second]
    assert page2["next_cursor"] is None


def test_filter_with_no_match_is_an_empty_last_page(client, acme) -> None:
    changed = client.patch(
        f"/users/{acme.viewer}", json={"role": "member"}, headers=auth(acme.admin)
    )
    assert changed.status_code == 200
    body = client.get("/users?role=viewer", headers=auth(acme.admin)).json()
    assert body == {"items": [], "next_cursor": None}
