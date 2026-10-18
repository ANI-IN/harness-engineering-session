"""F4 hidden tests: the board edit form version and the 409 conflict page (docs/features/f4.md).

The page is read with an HTML parser, so attribute order, quote style, and extra classes do not
matter.
"""

from __future__ import annotations

from html.parser import HTMLParser

from hidden_support import auth

Tag = tuple[str, set[str], dict[str, str], bool]  # tag, classes, attributes, inside the edit form


def scan(html: str) -> list[Tag]:
    """Start tags with their class tokens, marking those inside the issue page's edit form."""
    tags: list[Tag] = []
    state = {"form": False}

    class Parser(HTMLParser):
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            values = {name: value or "" for name, value in attrs}
            classes = set(values.get("class", "").split())
            if tag == "form" and "edit-issue" in classes:
                state["form"] = True
            tags.append((tag, classes, values, state["form"]))

        def handle_endtag(self, tag: str) -> None:
            if tag == "form":
                state["form"] = False

    parser = Parser(convert_charrefs=True)
    parser.feed(html)
    parser.close()
    return tags


def login(client, email: str = "member@acme.test") -> None:  # type: ignore[no-untyped-def]
    response = client.post("/board/login", data={"email": email}, follow_redirects=False)
    assert response.status_code == 303


def form_version(html: str) -> str | None:
    tags = scan(html)
    assert any(tag == "form" and inside for tag, _, _, inside in tags), "no edit form"
    for tag, _, values, inside in tags:
        hidden = values.get("type", "").lower() == "hidden"
        if inside and tag == "input" and values.get("name") == "version" and hidden:
            return values.get("value")
    return None


def save(client, issue_id: int, title: str, version: str | None):  # type: ignore[no-untyped-def]
    data = {"title": title, "priority": "medium"}
    if version is not None:
        data["version"] = version
    return client.post(f"/board/issues/{issue_id}/edit", data=data, follow_redirects=False)


def title(client, o, issue_id: int) -> str:  # type: ignore[no-untyped-def]
    return client.get(f"/issues/{issue_id}", headers=auth(o.member)).json()["title"]


def test_edit_form_has_a_hidden_version_field(client, acme) -> None:
    login(client)
    assert form_version(client.get(f"/board/issues/{acme.issues[0]}").text) == "1"


def test_edit_form_version_follows_changes(client, acme) -> None:
    client.patch(
        f"/issues/{acme.issues[0]}",
        json={"title": "Moved on"},
        headers={**auth(acme.member), "If-Match": '"1"'},
    )
    login(client)
    assert form_version(client.get(f"/board/issues/{acme.issues[0]}").text) == "2"


def test_save_with_the_current_version_redirects(client, acme) -> None:
    login(client)
    response = save(client, acme.issues[0], "Saved on the board", "1")
    assert response.status_code == 303
    assert title(client, acme, acme.issues[0]) == "Saved on the board"
    assert form_version(client.get(f"/board/issues/{acme.issues[0]}").text) == "2"
    response = save(client, acme.issues[0], "Saved twice", "2")
    assert response.status_code == 303


def test_stale_save_returns_409(client, acme) -> None:
    login(client)
    save(client, acme.issues[0], "Tab A", "1")
    assert save(client, acme.issues[0], "Tab B", "1").status_code == 409


def test_stale_save_keeps_the_first_edit(client, acme) -> None:
    login(client)
    save(client, acme.issues[0], "Tab A", "1")
    save(client, acme.issues[0], "Tab B", "1")
    assert title(client, acme, acme.issues[0]) == "Tab A"


def test_conflict_page_is_html_with_a_conflict_message(client, acme) -> None:
    login(client)
    save(client, acme.issues[0], "Tab A", "1")
    response = save(client, acme.issues[0], "Tab B", "1")
    assert response.headers["content-type"].startswith("text/html")
    tags = scan(response.text)
    assert any("conflict" in classes for _, classes, _, _ in tags)
    links = [values.get("href", "") for tag, _, values, _ in tags if tag == "a"]
    assert any(href.endswith(f"/board/issues/{acme.issues[0]}") for href in links)


def test_save_without_a_version_is_409(client, acme) -> None:
    login(client)
    assert save(client, acme.issues[0], "No version", None).status_code == 409
    assert title(client, acme, acme.issues[0]) == "Login page times out"


def test_api_change_makes_the_open_form_stale(client, acme) -> None:
    login(client)
    version = form_version(client.get(f"/board/issues/{acme.issues[1]}").text)
    client.post(
        f"/issues/{acme.issues[1]}/assign",
        json={"assignee_id": acme.viewer},
        headers={**auth(acme.admin), "If-Match": '"1"'},
    )
    assert save(client, acme.issues[1], "From an old form", version).status_code == 409
