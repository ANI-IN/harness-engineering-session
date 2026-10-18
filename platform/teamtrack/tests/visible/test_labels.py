"""F7: labels and issue labels."""

from __future__ import annotations

from conftest import auth, error_code

ACME_LABELS = (1, 2, 3)  # bug, feature, docs
GLOBEX_LABELS = (4, 5, 6)


def labels(client, user_id: int) -> list[dict]:  # type: ignore[no-untyped-def]
    response = client.get("/labels?limit=100", headers=auth(user_id))
    assert response.status_code == 200, response.text
    return response.json()["items"]


def create(client, user_id: int, name: str, color: str = "#112233", **headers):  # type: ignore[no-untyped-def]
    return client.post(
        "/labels", json={"name": name, "color": color}, headers={**auth(user_id), **headers}
    )


def issue_labels(client, o, issue_id: int) -> list[int]:  # type: ignore[no-untyped-def]
    issue = client.get(f"/issues/{issue_id}", headers=auth(o.member)).json()
    return [label["id"] for label in issue["labels"]]


def audit_actions(client, o) -> list[str]:  # type: ignore[no-untyped-def]
    items = client.get("/audit?limit=100", headers=auth(o.admin)).json()["items"]
    return [item["action"] for item in items]


def test_seeded_labels_are_listed_for_the_org_only(client, acme) -> None:
    found = labels(client, acme.viewer)
    assert [label["id"] for label in found] == list(ACME_LABELS)
    assert {label["name"] for label in found} == {"bug", "feature", "docs"}
    assert all(set(label) == {"id", "org_id", "name", "color"} for label in found)


def test_create_label(client, acme) -> None:
    response = create(client, acme.member, "urgent", "#ff0000")
    assert response.status_code == 201
    assert response.json()["name"] == "urgent"
    assert response.json()["color"] == "#ff0000"
    assert response.json()["org_id"] == acme.org_id


def test_names_are_unique_per_org_ignoring_case(client, acme, globex) -> None:
    response = create(client, acme.member, "BUG")
    assert response.status_code == 409
    assert error_code(response) == "label_exists"
    assert create(client, globex.member, "urgent").status_code == 201
    assert create(client, acme.member, "urgent").status_code == 201


def test_invalid_name_or_color_is_422(client, acme) -> None:
    for name, color in (("", "#112233"), ("x" * 51, "#112233"), ("ok", "red"), ("ok", "#12345")):
        response = create(client, acme.member, name, color)
        assert response.status_code == 422, (name, color)
        assert error_code(response) == "validation_error"


def test_viewer_cannot_write_labels(client, acme) -> None:
    assert create(client, acme.viewer, "nope").status_code == 403
    response = client.patch(
        f"/labels/{ACME_LABELS[0]}", json={"name": "x"}, headers=auth(acme.viewer)
    )
    assert response.status_code == 403
    assert client.delete(f"/labels/{ACME_LABELS[0]}", headers=auth(acme.viewer)).status_code == 403


def test_rename_and_recolor(client, acme) -> None:
    response = client.patch(
        f"/labels/{ACME_LABELS[2]}",
        json={"name": "documentation", "color": "#000000"},
        headers=auth(acme.member),
    )
    assert response.status_code == 200
    assert (response.json()["name"], response.json()["color"]) == ("documentation", "#000000")


def test_rename_to_an_existing_name_is_409(client, acme) -> None:
    response = client.patch(
        f"/labels/{ACME_LABELS[2]}", json={"name": "Feature"}, headers=auth(acme.member)
    )
    assert response.status_code == 409
    assert error_code(response) == "label_exists"


def test_other_orgs_label_is_404(client, acme, globex) -> None:
    label = GLOBEX_LABELS[0]
    response = client.patch(f"/labels/{label}", json={"name": "x"}, headers=auth(acme.admin))
    assert response.status_code == 404
    assert client.delete(f"/labels/{label}", headers=auth(acme.admin)).status_code == 404


def test_issue_out_carries_labels(client, acme) -> None:
    assert issue_labels(client, acme, acme.issues[2]) == [ACME_LABELS[0], ACME_LABELS[1]]
    issue = client.get(f"/issues/{acme.issues[2]}", headers=auth(acme.member)).json()
    assert issue["labels"][0] == {"id": ACME_LABELS[0], "name": "bug", "color": "#d73a4a"}
    assert issue_labels(client, acme, acme.issues[0]) == []


def test_add_and_remove_a_label_on_an_issue(client, acme) -> None:
    issue = acme.issues[0]
    response = client.post(
        f"/issues/{issue}/labels", json={"label_id": ACME_LABELS[2]}, headers=auth(acme.member)
    )
    assert response.status_code == 200
    assert [label["id"] for label in response.json()["labels"]] == [ACME_LABELS[2]]
    response = client.delete(f"/issues/{issue}/labels/{ACME_LABELS[2]}", headers=auth(acme.member))
    assert response.status_code == 204
    assert issue_labels(client, acme, issue) == []


def test_label_of_another_org_cannot_be_put_on_an_issue(client, acme, globex) -> None:
    response = client.post(
        f"/issues/{acme.issues[0]}/labels",
        json={"label_id": GLOBEX_LABELS[0]},
        headers=auth(acme.member),
    )
    assert response.status_code == 404
    assert issue_labels(client, acme, acme.issues[0]) == []


def test_deleting_a_label_removes_it_from_issues(client, acme) -> None:
    assert client.delete(f"/labels/{ACME_LABELS[0]}", headers=auth(acme.member)).status_code == 204
    assert issue_labels(client, acme, acme.issues[2]) == [ACME_LABELS[1]]
    assert [label["id"] for label in labels(client, acme.member)] == list(ACME_LABELS[1:])


def test_project_issue_list_filters_by_label(client, acme) -> None:
    path = f"/projects/{acme.projects[0]}/issues?label_id={ACME_LABELS[0]}"
    items = client.get(path, headers=auth(acme.member)).json()["items"]
    assert [i["id"] for i in items] == [acme.issues[1], acme.issues[2]]


def test_label_filter_from_another_org_is_404(client, acme, globex) -> None:
    path = f"/projects/{acme.projects[0]}/issues?label_id={GLOBEX_LABELS[0]}"
    assert client.get(path, headers=auth(acme.member)).status_code == 404


def test_label_writes_add_one_audit_row_each(client, acme) -> None:
    before = audit_actions(client, acme)
    label_id = create(client, acme.member, "triage").json()["id"]
    client.post(
        f"/issues/{acme.issues[0]}/labels", json={"label_id": label_id}, headers=auth(acme.member)
    )
    client.delete(f"/issues/{acme.issues[0]}/labels/{label_id}", headers=auth(acme.member))
    client.patch(f"/labels/{label_id}", json={"color": "#abcdef"}, headers=auth(acme.member))
    client.delete(f"/labels/{label_id}", headers=auth(acme.member))
    assert audit_actions(client, acme)[len(before) :] == [
        "label.create",
        "issue.label_add",
        "issue.label_remove",
        "label.update",
        "label.delete",
    ]


def test_create_label_is_idempotent_with_a_key(client, acme) -> None:
    first = create(client, acme.member, "once", **{"Idempotency-Key": "l-1"})
    again = create(client, acme.member, "once", **{"Idempotency-Key": "l-1"})
    assert again.status_code == 201
    assert again.json() == first.json()
    other = create(client, acme.member, "twice", **{"Idempotency-Key": "l-1"})
    assert other.status_code == 409
    assert error_code(other) == "idempotency_conflict"
