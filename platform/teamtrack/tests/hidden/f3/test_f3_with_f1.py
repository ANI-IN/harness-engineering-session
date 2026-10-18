"""F3 combined with F1 (org-wide search): a replayed create is one issue everywhere."""

from __future__ import annotations

from hidden_support import auth


def create(client, o, key: str, title: str):  # type: ignore[no-untyped-def]
    return client.post(
        f"/projects/{o.projects[0]}/issues",
        json={"title": title},
        headers={**auth(o.member), "Idempotency-Key": key},
    )


def test_org_search_finds_one_issue_after_a_replay(client, acme) -> None:
    create(client, acme, "w1", "Searchable once")
    create(client, acme, "w1", "Searchable once")
    items = client.get("/issues?q=searchable once", headers=auth(acme.member)).json()["items"]
    assert len(items) == 1


def test_org_search_total_grows_by_one(client, acme) -> None:
    before = len(client.get("/issues?limit=100", headers=auth(acme.member)).json()["items"])
    for _ in range(3):
        create(client, acme, "w2", "Counted once")
    after = len(client.get("/issues?limit=100", headers=auth(acme.member)).json()["items"])
    assert after == before + 1
