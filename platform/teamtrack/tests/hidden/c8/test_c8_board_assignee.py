"""C8 hidden tests: the board's issue detail page shows the assignee (spec: docs/features/c8.md).

Seed data: in each project the 1st, 3rd, 5th... issue is assigned to the org's member and the
others are unassigned, so Acme issue 1 is assigned and issue 2 is not.
"""

from __future__ import annotations

import re

from hidden_support import auth


def login(client, email: str) -> None:  # type: ignore[no-untyped-def]
    response = client.post("/board/login", data={"email": email}, follow_redirects=False)
    assert response.status_code == 303


def assignee(html: str) -> tuple[str | None, str]:
    match = re.search(r'<dd class="assignee"(?: data-user-id="(\d+)")?>\s*([^<]*?)\s*</dd>', html)
    assert match, 'no <dd class="assignee"> on the page'
    return match.group(1), match.group(2)


def test_assigned_issue_shows_the_assignees_name(client, acme) -> None:
    login(client, "member@acme.test")
    page = client.get(f"/board/issues/{acme.issues[0]}")
    assert page.status_code == 200
    assert assignee(page.text)[1] == "Acme Member"


def test_assigned_issue_carries_the_user_id(client, acme) -> None:
    login(client, "admin@acme.test")
    assert assignee(client.get(f"/board/issues/{acme.issues[0]}").text) == (
        str(acme.member),
        "Acme Member",
    )


def test_unassigned_issue_says_unassigned(client, acme) -> None:
    login(client, "member@acme.test")
    assert assignee(client.get(f"/board/issues/{acme.issues[1]}").text) == (None, "Unassigned")


def test_page_follows_a_reassignment(client, acme) -> None:
    moved = client.post(
        f"/issues/{acme.issues[0]}/assign",
        json={"assignee_id": acme.admin},
        headers=auth(acme.admin),
    )
    assert moved.status_code == 200
    login(client, "member@acme.test")
    assert assignee(client.get(f"/board/issues/{acme.issues[0]}").text)[1] == "Acme Admin"


def test_other_org_sees_its_own_assignee(client, globex) -> None:
    login(client, "member@globex.test")
    assert assignee(client.get(f"/board/issues/{globex.issues[0]}").text)[1] == "Globex Member"


def test_viewers_see_the_assignee_too(client, acme) -> None:
    login(client, "viewer@acme.test")
    assert assignee(client.get(f"/board/issues/{acme.issues[2]}").text)[1] == "Acme Member"
