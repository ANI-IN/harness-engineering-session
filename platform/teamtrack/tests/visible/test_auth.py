from __future__ import annotations

import pytest

from conftest import auth, error_code

SEEDED = [
    ("admin@acme.test", "admin"),
    ("member@acme.test", "member"),
    ("viewer@acme.test", "viewer"),
    ("admin@globex.test", "admin"),
    ("member@globex.test", "member"),
    ("viewer@globex.test", "viewer"),
]


@pytest.mark.parametrize(("email", "role"), SEEDED)
def test_login_returns_token_for_each_seeded_user(client, email: str, role: str) -> None:
    response = client.post("/auth/login", json={"email": email})
    assert response.status_code == 200
    body = response.json()
    assert body["token"].startswith("tt-")
    assert body["user"]["role"] == role


def test_login_unknown_email_is_401_envelope(client) -> None:
    response = client.post("/auth/login", json={"email": "nobody@acme.test"})
    assert response.status_code == 401
    assert error_code(response) == "unauthorized"


def test_me_returns_current_user(client, acme) -> None:
    response = client.get("/me", headers=auth(acme.member))
    assert response.status_code == 200
    assert response.json()["email"] == "member@acme.test"
    assert response.json()["org_id"] == acme.org_id


def test_missing_token_is_401(client) -> None:
    response = client.get("/me")
    assert response.status_code == 401
    assert error_code(response) == "unauthorized"


@pytest.mark.parametrize("header", ["Bearer nope", "Bearer tt-999", "Basic abc", "Bearer tt-x"])
def test_invalid_token_is_401(client, header: str) -> None:
    response = client.get("/me", headers={"Authorization": header})
    assert response.status_code == 401
    assert error_code(response) == "unauthorized"


def test_org_current(client, globex) -> None:
    response = client.get("/orgs/current", headers=auth(globex.admin))
    assert response.status_code == 200
    assert response.json() == {"id": globex.org_id, "name": "Globex", "slug": "globex"}


def test_health(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
