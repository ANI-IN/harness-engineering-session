"""F2 hidden tests: the board's comments panel (spec: docs/features/f2.md, "Board").

The page is read with an HTML parser, so attribute order, quote style, and extra classes on an
element do not matter; only the class tokens and attributes the spec names do.
"""

from __future__ import annotations

from html import unescape
from html.parser import HTMLParser

from hidden_support import auth

Tag = tuple[str, set[str], dict[str, str]]


def scan(html: str) -> tuple[list[Tag], str | None]:
    """Start tags with their class tokens, and the inner HTML of the first `section.comments`."""
    starts = [0]
    for line in html.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    tags: list[Tag] = []
    found: dict[str, int | str] = {"depth": 0}

    class Parser(HTMLParser):
        def position(self) -> int:
            line, column = self.getpos()
            return starts[line - 1] + column

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            values = {name: value or "" for name, value in attrs}
            classes = set(values.get("class", "").split())
            tags.append((tag, classes, values))
            if tag != "section":
                return
            if found["depth"]:
                found["depth"] = int(found["depth"]) + 1
            elif "panel" not in found and "comments" in classes:
                found["depth"] = 1
                found["begin"] = self.position() + len(self.get_starttag_text() or "")

        def handle_endtag(self, tag: str) -> None:
            if tag == "section" and found["depth"]:
                found["depth"] = int(found["depth"]) - 1
                if not found["depth"]:
                    found["panel"] = html[int(found["begin"]) : self.position()]

    parser = Parser(convert_charrefs=True)
    parser.feed(html)
    parser.close()
    panel = found.get("panel")
    return tags, panel if isinstance(panel, str) else None


def login(client, email: str) -> None:  # type: ignore[no-untyped-def]
    response = client.post("/board/login", data={"email": email}, follow_redirects=False)
    assert response.status_code == 303


def has_class(html: str, name: str) -> bool:
    return any(name in classes for _, classes, _ in scan(html)[0])


def comment_ids(html: str) -> list[str]:
    return [
        values["data-comment-id"]
        for _, classes, values in scan(html)[0]
        if "comment" in classes and "data-comment-id" in values
    ]


def panel(html: str) -> str:
    found = scan(html)[1]
    assert found is not None, "no comments panel"
    return found


def test_issue_page_has_a_comments_panel(client, acme) -> None:
    login(client, "member@acme.test")
    panel(client.get(f"/board/issues/{acme.issues[0]}").text)


def test_panel_lists_seeded_comments_oldest_first(client, acme) -> None:
    login(client, "member@acme.test")
    assert comment_ids(panel(client.get(f"/board/issues/{acme.issues[0]}").text)) == ["1", "2"]


def test_panel_shows_comment_text(client, acme) -> None:
    client.post(
        f"/issues/{acme.issues[1]}/comments",
        json={"body": "Seen on staging too"},
        headers=auth(acme.member),
    )
    login(client, "viewer@acme.test")
    assert "Seen on staging too" in panel(client.get(f"/board/issues/{acme.issues[1]}").text)


def test_writer_sees_the_add_form(client, acme) -> None:
    login(client, "member@acme.test")
    assert has_class(client.get(f"/board/issues/{acme.issues[0]}").text, "add-comment")


def test_viewer_sees_comments_but_no_form(client, acme) -> None:
    login(client, "viewer@acme.test")
    html = client.get(f"/board/issues/{acme.issues[0]}").text
    assert comment_ids(panel(html)) == ["1", "2"]
    assert not has_class(html, "add-comment")


def test_board_form_adds_a_comment_and_returns_to_the_issue(client, acme) -> None:
    login(client, "member@acme.test")
    response = client.post(
        f"/board/issues/{acme.issues[2]}/comments",
        data={"body": "Added on the board"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    assert response.headers["location"].endswith(f"/board/issues/{acme.issues[2]}")
    api = client.get(f"/issues/{acme.issues[2]}/comments", headers=auth(acme.member)).json()
    assert [c["body"] for c in api["items"]] == ["Added on the board"]


def test_comment_text_is_escaped(client, acme) -> None:
    body = "<script>alert(1)</script>"
    client.post(
        f"/issues/{acme.issues[1]}/comments", json={"body": body}, headers=auth(acme.member)
    )
    login(client, "member@acme.test")
    html = panel(client.get(f"/board/issues/{acme.issues[1]}").text)
    assert body not in html  # never raw markup
    assert body in unescape(html)  # shown as text, in any escaping (&lt;, &#60;, ...)


def test_deleted_comment_leaves_the_panel(client, acme) -> None:
    client.delete("/comments/1", headers=auth(acme.member))
    login(client, "admin@acme.test")
    assert comment_ids(panel(client.get(f"/board/issues/{acme.issues[0]}").text)) == ["2"]
