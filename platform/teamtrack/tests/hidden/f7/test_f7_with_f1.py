"""F7 combined with F1 (org-wide search): label_id on GET /issues."""

from __future__ import annotations

from hidden_support import auth

BUG, FEATURE, DOCS, GLOBEX_BUG = 1, 2, 3, 4


def search(client, user_id: int, query: str):  # type: ignore[no-untyped-def]
    return client.get(f"/issues{query}", headers=auth(user_id))


def test_org_search_filters_by_label(client, acme) -> None:
    items = search(client, acme.member, f"?label_id={FEATURE}").json()["items"]
    assert [item["id"] for item in items] == [acme.issues[2]]


def test_org_search_label_filter_spans_projects(client, acme) -> None:
    client.post(
        f"/issues/{acme.issues[15]}/labels", json={"label_id": BUG}, headers=auth(acme.member)
    )
    items = search(client, acme.member, f"?label_id={BUG}").json()["items"]
    assert [item["id"] for item in items] == [acme.issues[1], acme.issues[2], acme.issues[15]]


def test_org_search_label_combines_with_other_filters(client, acme) -> None:
    items = search(client, acme.member, f"?label_id={BUG}&q=typo").json()["items"]
    assert [item["id"] for item in items] == [acme.issues[2]]


def test_org_search_label_of_another_org_is_404(client, acme) -> None:
    assert search(client, acme.member, f"?label_id={GLOBEX_BUG}").status_code == 404
    assert search(client, acme.member, f"?label_id={BUG}").status_code == 200
