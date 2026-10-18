"""Web issue board (Jinja2 + HTMX)."""

from __future__ import annotations

import re

from conftest import auth


def login(client, email: str) -> None:  # type: ignore[no-untyped-def]
    response = client.post("/board/login", data={"email": email}, follow_redirects=False)
    assert response.status_code == 303
    assert "tt_session" in response.cookies or "tt_session" in client.cookies


def cards(html: str) -> list[tuple[str, str]]:
    return re.findall(r'data-issue-id="(\d+)"[^>]*data-org="([a-z]+)"', html)


def test_board_requires_login(client) -> None:
    response = client.get("/board", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/board/login"


def test_login_page_lists_demo_users(client) -> None:
    html = client.get("/board/login").text
    for email in ("admin@acme.test", "viewer@globex.test"):
        assert email in html


def test_board_shows_only_own_org_cards_with_badges(client, acme) -> None:
    login(client, "member@acme.test")
    html = client.get(f"/board/projects/{acme.projects[0]}").text
    found = cards(html)
    assert len(found) == 10
    assert {org for _, org in found} == {"acme"}
    assert len(re.findall(r'class="tenant-badge tenant-acme"', html)) >= 11  # 10 cards + header


def test_board_index_redirects_to_first_project(client, acme) -> None:
    login(client, "member@acme.test")
    response = client.get("/board", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/board/projects/{acme.projects[0]}"


def test_board_has_status_columns(client, acme) -> None:
    login(client, "member@acme.test")
    html = client.get(f"/board/projects/{acme.projects[0]}").text
    for column in ("open", "in_progress", "done"):
        assert f'data-column="{column}"' in html


def test_issue_detail_for_other_org_is_404(client, globex) -> None:
    login(client, "admin@acme.test")
    assert client.get(f"/board/issues/{globex.issues[0]}").status_code == 404


def test_issue_detail_shows_title(client, acme) -> None:
    login(client, "member@acme.test")
    html = client.get(f"/board/issues/{acme.issues[0]}").text
    assert "Login page times out" in html


def test_create_issue_from_board(client, acme) -> None:
    login(client, "member@acme.test")
    response = client.post(
        f"/board/projects/{acme.projects[0]}/issues",
        data={"title": "Made on the board", "priority": "high"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    html = client.get(f"/board/projects/{acme.projects[0]}").text
    assert "Made on the board" in html


def test_transition_from_board_returns_updated_card(client, acme) -> None:
    login(client, "member@acme.test")
    response = client.post(
        f"/board/issues/{acme.issues[0]}/transition",
        data={"status": "in_progress"},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert f'data-issue-id="{acme.issues[0]}"' in response.text
    api = client.get(f"/issues/{acme.issues[0]}", headers=auth(acme.member)).json()
    assert api["status"] == "in_progress"


def test_viewer_sees_no_write_controls(client, acme) -> None:
    login(client, "viewer@acme.test")
    html = client.get(f"/board/projects/{acme.projects[0]}").text
    assert "new-issue-form" not in html


def test_board_uses_vendored_htmx(client, acme) -> None:
    login(client, "member@acme.test")
    html = client.get(f"/board/projects/{acme.projects[0]}").text
    assert "/board/static/htmx-2.0.11.min.js" in html
    assert client.get("/board/static/htmx-2.0.11.min.js").status_code == 200


def test_board_routes_are_not_in_the_api_schema(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert not any(path.startswith("/board") for path in paths)


def test_board_rejects_invalid_priority_and_api_stays_healthy(client, acme) -> None:
    login(client, "member@acme.test")
    response = client.post(
        f"/board/projects/{acme.projects[0]}/issues",
        data={"title": "Bad priority", "priority": "urgent"},
        follow_redirects=False,
    )
    assert response.status_code == 422
    listed = client.get(f"/projects/{acme.projects[0]}/issues", headers=auth(acme.member))
    assert listed.status_code == 200


def test_board_rejects_overlong_title(client, acme) -> None:
    login(client, "member@acme.test")
    response = client.post(
        f"/board/projects/{acme.projects[0]}/issues",
        data={"title": "x" * 201, "priority": "low"},
        follow_redirects=False,
    )
    assert response.status_code == 422
