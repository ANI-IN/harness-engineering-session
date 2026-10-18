"""R4 idempotent creates (users, projects) and R5 one audit row per write."""

from __future__ import annotations

import pytest

from conftest import auth, error_code

CREATES = [
    ("/users", {"email": "dup@acme.test", "name": "Dup", "role": "member"}, "/users"),
    ("/projects", {"name": "Dup", "key": "DUP"}, "/projects"),
]


def count(client, path: str, user: int) -> int:  # type: ignore[no-untyped-def]
    return len(client.get(f"{path}?limit=100", headers=auth(user)).json()["items"])


@pytest.mark.parametrize(("path", "body", "list_path"), CREATES)
def test_same_key_twice_creates_one_record(client, acme, path, body, list_path) -> None:
    headers = {**auth(acme.admin), "Idempotency-Key": "k-1"}
    before = count(client, list_path, acme.admin)
    first = client.post(path, json=body, headers=headers)
    second = client.post(path, json=body, headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert count(client, list_path, acme.admin) == before + 1


@pytest.mark.parametrize(("path", "body", "list_path"), CREATES)
def test_same_key_different_body_is_409(client, acme, path, body, list_path) -> None:
    headers = {**auth(acme.admin), "Idempotency-Key": "k-2"}
    client.post(path, json=body, headers=headers)
    changed = {**body, "name": "Other"}
    response = client.post(path, json=changed, headers=headers)
    assert response.status_code == 409
    assert error_code(response) == "idempotency_conflict"


def test_keys_are_scoped_per_org(client, acme, globex) -> None:
    body = {"name": "Shared", "key": "SHR"}
    a = client.post("/projects", json=body, headers={**auth(acme.admin), "Idempotency-Key": "same"})
    g = client.post(
        "/projects", json=body, headers={**auth(globex.admin), "Idempotency-Key": "same"}
    )
    assert a.status_code == g.status_code == 201
    assert a.json()["id"] != g.json()["id"]


def test_without_key_each_post_creates(client, acme) -> None:
    before = count(client, "/projects", acme.admin)
    client.post("/projects", json={"name": "A", "key": "AAA"}, headers=auth(acme.admin))
    client.post("/projects", json={"name": "B", "key": "BBB"}, headers=auth(acme.admin))
    assert count(client, "/projects", acme.admin) == before + 2


def audit_count(client, o) -> int:  # type: ignore[no-untyped-def]
    return count(client, "/audit", o.admin)


def writes(o):  # type: ignore[no-untyped-def]
    project, issue = o.projects[0], o.issues[1]
    return [
        ("POST", "/users", {"email": "aud@acme.test", "name": "Aud", "role": "viewer"}),
        ("PATCH", f"/users/{o.viewer}", {"name": "Renamed"}),
        ("POST", "/projects", {"name": "Audit", "key": "AUD"}),
        ("PATCH", f"/projects/{project}", {"name": "Renamed"}),
        ("POST", f"/projects/{project}/members", {"user_id": o.viewer}),
        ("POST", f"/projects/{project}/issues", {"title": "Audited"}),
        ("PATCH", f"/issues/{issue}", {"title": "Renamed"}),
        ("POST", f"/issues/{issue}/assign", {"assignee_id": o.member}),
        ("POST", f"/issues/{issue}/transition", {"status": "in_progress"}),
        ("DELETE", f"/issues/{issue}", None),
        ("DELETE", f"/projects/{o.projects[1]}", None),
    ]


@pytest.mark.parametrize("index", range(11))
def test_each_write_adds_exactly_one_audit_row(client, acme, index: int) -> None:
    method, path, body = writes(acme)[index]
    before = audit_count(client, acme)
    response = client.request(method, path, json=body, headers=auth(acme.admin))
    assert response.status_code < 300, response.text
    assert audit_count(client, acme) == before + 1


def test_idempotent_replay_adds_no_audit_row(client, acme) -> None:
    headers = {**auth(acme.admin), "Idempotency-Key": "aud-1"}
    client.post("/projects", json={"name": "Once", "key": "ONC"}, headers=headers)
    before = audit_count(client, acme)
    client.post("/projects", json={"name": "Once", "key": "ONC"}, headers=headers)
    assert audit_count(client, acme) == before


def test_reads_add_no_audit_row(client, acme) -> None:
    before = audit_count(client, acme)
    client.get("/projects", headers=auth(acme.admin))
    client.get(f"/issues/{acme.issues[0]}", headers=auth(acme.admin))
    assert audit_count(client, acme) == before


def test_audit_row_names_actor_and_action(client, acme) -> None:
    client.post(
        f"/projects/{acme.projects[0]}/issues", json={"title": "Who"}, headers=auth(acme.member)
    )
    items = client.get("/audit?limit=100", headers=auth(acme.admin)).json()["items"]
    last = items[-1]
    assert last["actor_id"] == acme.member
    assert last["action"] == "issue.create"
