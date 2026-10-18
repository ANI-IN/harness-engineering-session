"""F3 guards: issue creation without a key and the existing checks keep working."""

from __future__ import annotations

from hidden_support import auth, error_code


def create(client, user_id: int, project_id: int, **headers):  # type: ignore[no-untyped-def]
    return client.post(
        f"/projects/{project_id}/issues",
        json={"title": "Guarded"},
        headers={**auth(user_id), **headers},
    )


def test_without_a_key_each_request_creates_an_issue(client, acme) -> None:
    first = create(client, acme.member, acme.projects[0])
    second = create(client, acme.member, acme.projects[0])
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


def test_viewer_is_403_with_a_key(client, acme) -> None:
    response = create(client, acme.viewer, acme.projects[0], **{"Idempotency-Key": "g1"})
    assert response.status_code == 403
    assert error_code(response) == "forbidden"


def test_other_orgs_project_is_404_with_a_key(client, acme, globex) -> None:
    response = create(client, acme.member, globex.projects[0], **{"Idempotency-Key": "g2"})
    assert response.status_code == 404


def test_project_creation_keys_still_replay(client, acme) -> None:
    headers = {**auth(acme.admin), "Idempotency-Key": "g3"}
    first = client.post("/projects", json={"name": "Once", "key": "ONCE"}, headers=headers)
    again = client.post("/projects", json={"name": "Once", "key": "ONCE"}, headers=headers)
    assert again.json() == first.json()
