"""F7 with F1: GET /issues accepts label_id."""

from __future__ import annotations

from conftest import auth

ACME_LABELS = (1, 2, 3)
GLOBEX_LABELS = (4, 5, 6)


def test_org_search_filters_by_label(client, acme) -> None:
    response = client.get(f"/issues?label_id={ACME_LABELS[1]}", headers=auth(acme.member))
    assert [i["id"] for i in response.json()["items"]] == [acme.issues[2]]


def test_org_search_label_filter_combines_with_others(client, acme) -> None:
    path = f"/issues?label_id={ACME_LABELS[0]}&priority=medium"
    response = client.get(path, headers=auth(acme.member))
    assert [i["id"] for i in response.json()["items"]] == [acme.issues[1]]


def test_org_search_label_of_another_org_is_404(client, acme) -> None:
    response = client.get(f"/issues?label_id={GLOBEX_LABELS[0]}", headers=auth(acme.member))
    assert response.status_code == 404
