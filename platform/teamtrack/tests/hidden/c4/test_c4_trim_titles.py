"""C4 hidden tests: issue titles are stored trimmed (spec: docs/features/c4.md)."""

from __future__ import annotations

from hidden_support import auth


def create(client, project: int, user: int, title: str):  # type: ignore[no-untyped-def]
    return client.post(f"/projects/{project}/issues", json={"title": title}, headers=auth(user))


def test_create_trims_spaces(client, acme) -> None:
    response = create(client, acme.projects[0], acme.member, "  Fix the login form  ")
    assert response.status_code == 201, response.text
    assert response.json()["title"] == "Fix the login form"


def test_create_trims_tabs_and_newlines(client, acme) -> None:
    response = create(client, acme.projects[0], acme.admin, "\tExport fails\n")
    assert response.status_code == 201, response.text
    assert response.json()["title"] == "Export fails"


def test_the_stored_title_is_trimmed(client, acme) -> None:
    created = create(client, acme.projects[0], acme.member, "   Slow search   ")
    issue_id = created.json()["id"]
    fetched = client.get(f"/issues/{issue_id}", headers=auth(acme.viewer))
    assert fetched.json()["title"] == "Slow search"


def test_patch_trims_the_title(client, acme) -> None:
    response = client.patch(
        f"/issues/{acme.issues[0]}", json={"title": "  Renamed issue \n"}, headers=auth(acme.member)
    )
    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Renamed issue"


def test_the_length_limit_applies_after_trimming(client, acme) -> None:
    title = "   " + "x" * 200 + "   "
    response = create(client, acme.projects[0], acme.member, title)
    assert response.status_code == 201, response.text
    assert response.json()["title"] == "x" * 200


def test_board_create_form_trims_the_title(client, acme) -> None:
    login = client.post("/board/login", data={"email": "member@acme.test"}, follow_redirects=False)
    assert login.status_code == 303
    response = client.post(
        f"/board/projects/{acme.projects[1]}/issues",
        data={"title": "  Board issue  ", "priority": "low"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    listed = client.get(
        f"/projects/{acme.projects[1]}/issues?limit=100", headers=auth(acme.member)
    ).json()
    assert listed["items"][-1]["title"] == "Board issue"
