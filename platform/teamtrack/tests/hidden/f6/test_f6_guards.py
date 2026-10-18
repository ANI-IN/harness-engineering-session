"""F6 guards: /me and issue reads keep working while watchers are added."""

from __future__ import annotations

from hidden_support import auth


def test_me_still_returns_the_caller(client, acme) -> None:
    assert client.get("/me", headers=auth(acme.member)).json()["id"] == acme.member


def test_issue_read_still_works(client, acme) -> None:
    assert client.get(f"/issues/{acme.issues[0]}", headers=auth(acme.viewer)).status_code == 200


def test_deleting_an_issue_still_works(client, acme) -> None:
    assert client.delete(f"/issues/{acme.issues[0]}", headers=auth(acme.member)).status_code == 204
