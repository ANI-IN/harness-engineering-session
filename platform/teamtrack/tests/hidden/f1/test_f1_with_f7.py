"""F1 with F7 (labels, m1-alt-b): search results are full IssueOut items, labels included."""

from __future__ import annotations

from hidden_support import auth


def test_search_items_carry_labels(client, acme) -> None:
    # F7 seed: Acme's third issue carries labels 1 (bug) and 2 (feature).
    items = client.get("/issues?q=typo", headers=auth(acme.member)).json()["items"]
    third = next(item for item in items if item["id"] == acme.issues[2])
    assert [label["id"] for label in third["labels"]] == [1, 2]


def test_search_still_filters_after_labelling(client, acme) -> None:
    client.post(f"/issues/{acme.issues[0]}/labels", json={"label_id": 3}, headers=auth(acme.member))
    response = client.get("/issues?q=login&project_id=1", headers=auth(acme.member))
    assert [item["id"] for item in response.json()["items"]] == [acme.issues[0]]
    assert [label["id"] for label in response.json()["items"][0]["labels"]] == [3]
