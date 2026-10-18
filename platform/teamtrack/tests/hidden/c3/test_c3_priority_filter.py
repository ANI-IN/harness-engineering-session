"""C3 hidden tests: `GET /projects/{project_id}/issues?priority=` (spec: docs/features/c3.md).

Seed data: the first Acme project holds issues 1-10 with priorities low, medium, high repeating
from issue 1, so low = 1, 4, 7, 10; medium = 2, 5, 8; high = 3, 6, 9.
"""

from __future__ import annotations

from hidden_support import auth, error_code


def ids(response) -> list[int]:  # type: ignore[no-untyped-def]
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


def test_priority_filter_lists_only_that_priority(client, acme) -> None:
    project = acme.projects[0]
    response = client.get(f"/projects/{project}/issues?priority=high", headers=auth(acme.viewer))
    assert ids(response) == [3, 6, 9]
    assert {item["priority"] for item in response.json()["items"]} == {"high"}


def test_priority_filter_pages_with_the_cursor(client, acme) -> None:
    url = f"/projects/{acme.projects[0]}/issues?priority=low&limit=2"
    page1 = client.get(url, headers=auth(acme.member)).json()
    assert [item["id"] for item in page1["items"]] == [1, 4]
    page2 = client.get(f"{url}&cursor={page1['next_cursor']}", headers=auth(acme.member)).json()
    assert [item["id"] for item in page2["items"]] == [7, 10]
    assert page2["next_cursor"] is None


def test_unknown_priority_is_a_validation_error(client, acme) -> None:
    response = client.get(
        f"/projects/{acme.projects[0]}/issues?priority=urgent", headers=auth(acme.admin)
    )
    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_another_orgs_project_is_not_found_with_the_filter(client, acme, globex) -> None:
    own = client.get(
        f"/projects/{acme.projects[0]}/issues?priority=medium", headers=auth(acme.admin)
    )
    assert ids(own) == [2, 5, 8]
    other = client.get(
        f"/projects/{globex.projects[0]}/issues?priority=medium", headers=auth(acme.admin)
    )
    assert other.status_code == 404
    assert error_code(other) == "not_found"


def test_deleted_issues_are_not_listed(client, acme) -> None:
    assert client.delete("/issues/3", headers=auth(acme.member)).status_code == 204
    response = client.get(
        f"/projects/{acme.projects[0]}/issues?priority=high", headers=auth(acme.admin)
    )
    assert ids(response) == [6, 9]


def test_filter_uses_the_current_priority(client, acme) -> None:
    changed = client.patch("/issues/1", json={"priority": "high"}, headers=auth(acme.member))
    assert changed.status_code == 200
    response = client.get(
        f"/projects/{acme.projects[0]}/issues?priority=high", headers=auth(acme.admin)
    )
    assert ids(response) == [1, 3, 6, 9]
