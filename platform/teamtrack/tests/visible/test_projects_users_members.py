from __future__ import annotations

from conftest import auth, error_code


def test_create_project(client, acme) -> None:
    response = client.post(
        "/projects", json={"name": "Docs", "key": "DOC"}, headers=auth(acme.member)
    )
    assert response.status_code == 201
    assert response.json()["key"] == "DOC"
    assert response.json()["org_id"] == acme.org_id


def test_duplicate_project_key_in_org_is_409(client, acme) -> None:
    response = client.post(
        "/projects", json={"name": "Again", "key": "WEB"}, headers=auth(acme.member)
    )
    assert response.status_code == 409
    assert error_code(response) == "conflict"


def test_same_project_key_in_other_org_is_allowed(client, globex) -> None:
    response = client.post(
        "/projects", json={"name": "Web", "key": "WEB"}, headers=auth(globex.member)
    )
    assert response.status_code == 201


def test_project_key_must_be_uppercase_letters(client, acme) -> None:
    response = client.post(
        "/projects", json={"name": "x", "key": "bad key"}, headers=auth(acme.member)
    )
    assert response.status_code == 422


def test_archived_project_is_hidden(client, acme) -> None:
    assert (
        client.delete(f"/projects/{acme.projects[1]}", headers=auth(acme.admin)).status_code == 204
    )
    ids = {p["id"] for p in client.get("/projects", headers=auth(acme.admin)).json()["items"]}
    assert acme.projects[1] not in ids
    assert client.get(f"/projects/{acme.projects[1]}", headers=auth(acme.admin)).status_code == 404


def test_patch_project(client, acme) -> None:
    response = client.patch(
        f"/projects/{acme.projects[0]}", json={"name": "Website v2"}, headers=auth(acme.member)
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Website v2"


def test_create_user(client, acme) -> None:
    response = client.post(
        "/users",
        json={"email": "new@acme.test", "name": "New", "role": "viewer"},
        headers=auth(acme.admin),
    )
    assert response.status_code == 201
    assert response.json()["org_id"] == acme.org_id


def test_duplicate_email_is_409(client, acme) -> None:
    response = client.post(
        "/users",
        json={"email": "member@acme.test", "name": "x", "role": "viewer"},
        headers=auth(acme.admin),
    )
    assert response.status_code == 409


def test_invalid_role_is_422(client, acme) -> None:
    response = client.post(
        "/users",
        json={"email": "r@acme.test", "name": "x", "role": "owner"},
        headers=auth(acme.admin),
    )
    assert response.status_code == 422


def test_patch_user_role(client, acme) -> None:
    response = client.patch(
        f"/users/{acme.viewer}", json={"role": "member"}, headers=auth(acme.admin)
    )
    assert response.json()["role"] == "member"


def test_add_and_remove_member(client, acme) -> None:
    project = acme.projects[1]
    added = client.post(
        f"/projects/{project}/members", json={"user_id": acme.viewer}, headers=auth(acme.admin)
    )
    assert added.status_code == 201
    members = client.get(f"/projects/{project}/members", headers=auth(acme.admin)).json()["items"]
    assert acme.viewer in {m["user_id"] for m in members}
    removed = client.delete(f"/projects/{project}/members/{acme.viewer}", headers=auth(acme.admin))
    assert removed.status_code == 204


def test_adding_existing_member_is_409(client, acme) -> None:
    project = acme.projects[0]
    response = client.post(
        f"/projects/{project}/members", json={"user_id": acme.member}, headers=auth(acme.admin)
    )
    assert response.status_code == 409


def test_removing_non_member_is_404(client, acme) -> None:
    response = client.delete(
        f"/projects/{acme.projects[1]}/members/{acme.viewer}", headers=auth(acme.admin)
    )
    assert response.status_code == 404
