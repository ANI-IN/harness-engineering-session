"""F2 guards: behaviour that must not break while adding comments (pass before and after)."""

from __future__ import annotations

from hidden_support import auth


def login(client, email: str) -> None:  # type: ignore[no-untyped-def]
    response = client.post("/board/login", data={"email": email}, follow_redirects=False)
    assert response.status_code == 303


def test_issue_page_still_shows_the_issue(client, acme) -> None:
    login(client, "member@acme.test")
    html = client.get(f"/board/issues/{acme.issues[0]}").text
    assert "Login page times out" in html


def test_board_issue_page_of_another_org_is_still_404(client, globex) -> None:
    login(client, "admin@acme.test")
    assert client.get(f"/board/issues/{globex.issues[0]}").status_code == 404


def test_deleting_an_issue_still_works(client, acme) -> None:
    response = client.delete(f"/issues/{acme.issues[3]}", headers=auth(acme.member))
    assert response.status_code == 204
