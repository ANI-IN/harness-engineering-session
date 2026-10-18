"""C2 hidden tests: `GET /projects?q=` (spec: docs/features/c2.md)."""

from __future__ import annotations

from hidden_support import auth, error_code


def names(response) -> list[str]:  # type: ignore[no-untyped-def]
    assert response.status_code == 200, response.text
    return [item["name"] for item in response.json()["items"]]


def test_search_matches_a_substring_of_the_name(client, acme) -> None:
    assert names(client.get("/projects?q=web", headers=auth(acme.member))) == ["Website"]


def test_search_ignores_case(client, acme) -> None:
    assert names(client.get("/projects?q=MOB", headers=auth(acme.viewer))) == ["Mobile"]


def test_search_never_matches_another_orgs_projects(client, acme) -> None:
    body = client.get("/projects?q=plat", headers=auth(acme.admin)).json()
    assert body == {"items": [], "next_cursor": None}


def test_empty_search_is_a_validation_error(client, acme) -> None:
    response = client.get("/projects?q=", headers=auth(acme.admin))
    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_search_longer_than_100_characters_is_a_validation_error(client, acme) -> None:
    response = client.get("/projects?q=" + "a" * 101, headers=auth(acme.admin))
    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_search_pages_with_the_cursor(client, acme) -> None:
    for name, key in (("Web Shop", "WSHOP"), ("Webhooks", "HOOKS")):
        created = client.post(
            "/projects", json={"name": name, "key": key}, headers=auth(acme.admin)
        )
        assert created.status_code == 201, created.text
    page1 = client.get("/projects?q=web&limit=2", headers=auth(acme.admin)).json()
    assert [item["name"] for item in page1["items"]] == ["Website", "Web Shop"]
    assert page1["next_cursor"]
    page2 = client.get(
        f"/projects?q=web&limit=2&cursor={page1['next_cursor']}", headers=auth(acme.admin)
    ).json()
    assert [item["name"] for item in page2["items"]] == ["Webhooks"]
    assert page2["next_cursor"] is None


def test_search_skips_archived_projects(client, acme) -> None:
    archived = client.delete(f"/projects/{acme.projects[0]}", headers=auth(acme.admin))
    assert archived.status_code == 204
    assert names(client.get("/projects?q=web", headers=auth(acme.admin))) == []
