"""C7 hidden tests: project members show the user's email, name, and role
(spec: docs/features/c7.md)."""

from __future__ import annotations

from hidden_support import auth


def members(client, project: int, user: int) -> list[dict]:  # type: ignore[no-untyped-def,type-arg]
    response = client.get(f"/projects/{project}/members", headers=auth(user))
    assert response.status_code == 200, response.text
    return response.json()["items"]


def test_list_items_carry_the_users_details(client, acme) -> None:
    items = members(client, acme.projects[0], acme.viewer)
    assert [(m["user_id"], m["email"], m["name"], m["role"]) for m in items] == [
        (acme.admin, "admin@acme.test", "Acme Admin", "admin"),
        (acme.member, "member@acme.test", "Acme Member", "member"),
    ]


def test_add_response_carries_the_users_details(client, acme) -> None:
    response = client.post(
        f"/projects/{acme.projects[0]}/members",
        json={"user_id": acme.viewer},
        headers=auth(acme.admin),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["user_id"], body["email"], body["role"]) == (
        acme.viewer,
        "viewer@acme.test",
        "viewer",
    )
    assert body["name"] == "Acme Viewer"


def test_other_org_lists_its_own_users_details(client, globex) -> None:
    items = members(client, globex.projects[1], globex.member)
    assert [m["email"] for m in items] == ["admin@globex.test", "member@globex.test"]


def test_role_shown_is_the_current_role(client, acme) -> None:
    changed = client.patch(
        f"/users/{acme.member}", json={"role": "viewer"}, headers=auth(acme.admin)
    )
    assert changed.status_code == 200
    roles = {m["user_id"]: m["role"] for m in members(client, acme.projects[0], acme.admin)}
    assert roles[acme.member] == "viewer"


def test_name_shown_is_the_current_name(client, acme) -> None:
    changed = client.patch(
        f"/users/{acme.member}", json={"name": "Max Member"}, headers=auth(acme.admin)
    )
    assert changed.status_code == 200
    names = {m["user_id"]: m["name"] for m in members(client, acme.projects[0], acme.admin)}
    assert names[acme.member] == "Max Member"


def test_schema_documents_the_new_fields(client) -> None:
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    properties = schemas["MemberOut"]["properties"]
    assert {"email", "name", "role"} <= set(properties)
