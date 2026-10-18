"""F7 hidden tests: labels (spec: docs/features/f7.md)."""

from __future__ import annotations

from hidden_support import auth, error_code

# Seed: Acme labels 1 bug, 2 feature, 3 docs; Globex labels 4, 5, 6 with the same names. Each
# org's second issue carries bug; its third issue carries bug and feature.
BUG, FEATURE, DOCS = 1, 2, 3
GLOBEX_BUG = 4


def labels_page(client, user_id: int, query: str = "?limit=100"):  # type: ignore[no-untyped-def]
    return client.get(f"/labels{query}", headers=auth(user_id))


def label_ids(client, user_id: int) -> list[int]:  # type: ignore[no-untyped-def]
    response = labels_page(client, user_id)
    assert response.status_code == 200, response.text
    return [label["id"] for label in response.json()["items"]]


def create(client, user_id: int, name: str = "urgent", color: str = "#ff0000", **headers):  # type: ignore[no-untyped-def]
    return client.post(
        "/labels", json={"name": name, "color": color}, headers={**auth(user_id), **headers}
    )


def update(client, user_id: int, label_id: int, **body):  # type: ignore[no-untyped-def]
    return client.patch(f"/labels/{label_id}", json=body, headers=auth(user_id))


def remove(client, user_id: int, label_id: int):  # type: ignore[no-untyped-def]
    return client.delete(f"/labels/{label_id}", headers=auth(user_id))


def attach(client, user_id: int, issue_id: int, label_id: object):  # type: ignore[no-untyped-def]
    return client.post(
        f"/issues/{issue_id}/labels", json={"label_id": label_id}, headers=auth(user_id)
    )


def detach(client, user_id: int, issue_id: int, label_id: int):  # type: ignore[no-untyped-def]
    return client.delete(f"/issues/{issue_id}/labels/{label_id}", headers=auth(user_id))


def on_issue(client, user_id: int, issue_id: int) -> list[int]:  # type: ignore[no-untyped-def]
    issue = client.get(f"/issues/{issue_id}", headers=auth(user_id)).json()
    return [label["id"] for label in issue["labels"]]


def audit(client, o) -> list[dict]:  # type: ignore[no-untyped-def]
    return client.get("/audit?limit=100", headers=auth(o.admin)).json()["items"]


# -- listing --------------------------------------------------------------------------------------


def test_seeded_labels_are_listed(client, acme) -> None:
    assert label_ids(client, acme.member) == [BUG, FEATURE, DOCS]


def test_seeded_label_fields(client, acme) -> None:
    first = labels_page(client, acme.viewer).json()["items"][0]
    assert first == {"id": BUG, "org_id": acme.org_id, "name": "bug", "color": "#d73a4a"}


def test_globex_sees_only_its_labels(client, globex) -> None:
    assert label_ids(client, globex.member) == [4, 5, 6]


def test_label_list_uses_the_envelope_and_cursor(client, acme) -> None:
    first = labels_page(client, acme.member, "?limit=2").json()
    assert set(first) == {"items", "next_cursor"}
    assert [label["id"] for label in first["items"]] == [BUG, FEATURE]
    rest = labels_page(client, acme.member, f"?limit=2&cursor={first['next_cursor']}").json()
    assert [label["id"] for label in rest["items"]] == [DOCS]


def test_label_list_requires_a_token(client, acme) -> None:
    assert client.get("/labels").status_code == 401
    assert label_ids(client, acme.viewer) == [BUG, FEATURE, DOCS]


# -- create ---------------------------------------------------------------------------------------


def test_create_returns_201_and_the_label(client, acme) -> None:
    response = create(client, acme.member, "urgent", "#ff0000")
    assert response.status_code == 201
    body = response.json()
    assert (body["name"], body["color"], body["org_id"]) == ("urgent", "#ff0000", acme.org_id)
    assert set(body) == {"id", "org_id", "name", "color"}


def test_created_label_is_listed(client, acme) -> None:
    created = create(client, acme.admin, "triage", "#00ff00").json()["id"]
    assert label_ids(client, acme.member) == [BUG, FEATURE, DOCS, created]


def test_uppercase_hex_color_is_accepted(client, acme) -> None:
    assert create(client, acme.member, "loud", "#ABCDEF").status_code == 201


def test_name_of_50_characters_is_accepted(client, acme) -> None:
    assert create(client, acme.member, "n" * 50).status_code == 201


def test_duplicate_name_is_409(client, acme) -> None:
    response = create(client, acme.member, "bug")
    assert response.status_code == 409
    assert error_code(response) == "label_exists"


def test_duplicate_name_ignores_case(client, acme) -> None:
    response = create(client, acme.member, "Bug")
    assert response.status_code == 409
    assert error_code(response) == "label_exists"
    assert label_ids(client, acme.member) == [BUG, FEATURE, DOCS]


def test_other_org_may_use_the_same_name(client, acme, globex) -> None:
    assert create(client, globex.member, "urgent").status_code == 201
    assert create(client, acme.member, "URGENT").status_code == 201


def test_empty_name_is_422(client, acme) -> None:
    response = create(client, acme.member, "")
    assert response.status_code == 422
    assert error_code(response) == "validation_error"
    assert label_ids(client, acme.member) == [BUG, FEATURE, DOCS]


def test_name_of_51_characters_is_422(client, acme) -> None:
    assert create(client, acme.member, "n" * 51).status_code == 422
    assert label_ids(client, acme.member) == [BUG, FEATURE, DOCS]


def test_color_name_is_422(client, acme) -> None:
    assert create(client, acme.member, "x", "red").status_code == 422
    assert label_ids(client, acme.member) == [BUG, FEATURE, DOCS]


def test_short_hex_color_is_422(client, acme) -> None:
    assert create(client, acme.member, "x", "#fff").status_code == 422
    assert label_ids(client, acme.member) == [BUG, FEATURE, DOCS]


def test_non_hex_color_is_422(client, acme) -> None:
    assert create(client, acme.member, "x", "#gggggg").status_code == 422
    assert label_ids(client, acme.member) == [BUG, FEATURE, DOCS]


def test_viewer_cannot_create(client, acme) -> None:
    response = create(client, acme.viewer)
    assert response.status_code == 403
    assert error_code(response) == "forbidden"
    assert label_ids(client, acme.viewer) == [BUG, FEATURE, DOCS]


def test_create_is_idempotent_with_a_key(client, acme) -> None:
    first = create(client, acme.member, "once", **{"Idempotency-Key": "l1"})
    again = create(client, acme.member, "once", **{"Idempotency-Key": "l1"})
    assert (again.status_code, again.json()) == (201, first.json())
    assert len(label_ids(client, acme.member)) == 4


def test_same_key_with_another_body_is_409(client, acme) -> None:
    create(client, acme.member, "once", **{"Idempotency-Key": "l2"})
    response = create(client, acme.member, "other", **{"Idempotency-Key": "l2"})
    assert response.status_code == 409
    assert error_code(response) == "idempotency_conflict"


# -- update and delete ----------------------------------------------------------------------------


def test_rename(client, acme) -> None:
    response = update(client, acme.member, DOCS, name="documentation")
    assert response.status_code == 200
    assert response.json()["name"] == "documentation"
    assert response.json()["color"] == "#0075ca"


def test_recolor(client, acme) -> None:
    response = update(client, acme.member, DOCS, color="#123456")
    assert (response.status_code, response.json()["color"]) == (200, "#123456")


def test_rename_to_another_labels_name_is_409(client, acme) -> None:
    response = update(client, acme.member, DOCS, name="FEATURE")
    assert response.status_code == 409
    assert error_code(response) == "label_exists"


def test_rename_to_a_different_case_of_itself_is_allowed(client, acme) -> None:
    response = update(client, acme.member, BUG, name="Bug")
    assert (response.status_code, response.json()["name"]) == (200, "Bug")


def test_update_with_an_invalid_color_is_422(client, acme) -> None:
    assert update(client, acme.member, BUG, color="blue").status_code == 422
    assert labels_page(client, acme.member).json()["items"][0]["color"] == "#d73a4a"


def test_viewer_cannot_update(client, acme) -> None:
    assert update(client, acme.viewer, BUG, name="x").status_code == 403
    assert labels_page(client, acme.member).json()["items"][0]["name"] == "bug"


def test_updating_another_orgs_label_is_404(client, acme) -> None:
    response = update(client, acme.admin, GLOBEX_BUG, name="mine")
    assert response.status_code == 404
    assert error_code(response) == "not_found"
    assert update(client, acme.admin, BUG, name="ours").status_code == 200


def test_delete_returns_204_and_unlists(client, acme) -> None:
    assert remove(client, acme.member, DOCS).status_code == 204
    assert label_ids(client, acme.member) == [BUG, FEATURE]


def test_deleting_a_label_removes_it_from_issues(client, acme) -> None:
    assert on_issue(client, acme.member, acme.issues[2]) == [BUG, FEATURE]
    remove(client, acme.member, BUG)
    assert on_issue(client, acme.member, acme.issues[2]) == [FEATURE]
    assert on_issue(client, acme.member, acme.issues[1]) == []


def test_viewer_cannot_delete(client, acme) -> None:
    assert remove(client, acme.viewer, BUG).status_code == 403
    assert label_ids(client, acme.viewer) == [BUG, FEATURE, DOCS]


def test_deleting_another_orgs_label_is_404(client, acme, globex) -> None:
    assert remove(client, acme.admin, GLOBEX_BUG).status_code == 404
    assert label_ids(client, globex.admin) == [4, 5, 6]


def test_deleting_twice_is_404(client, acme) -> None:
    assert remove(client, acme.member, DOCS).status_code == 204
    assert remove(client, acme.member, DOCS).status_code == 404


# -- labels on issues -----------------------------------------------------------------------------


def test_issue_out_has_labels(client, acme) -> None:
    issue = client.get(f"/issues/{acme.issues[2]}", headers=auth(acme.member)).json()
    assert issue["labels"] == [
        {"id": BUG, "name": "bug", "color": "#d73a4a"},
        {"id": FEATURE, "name": "feature", "color": "#a2eeef"},
    ]


def test_unlabelled_issue_has_an_empty_list(client, acme) -> None:
    assert on_issue(client, acme.member, acme.issues[0]) == []


def test_project_issue_list_items_carry_labels(client, acme) -> None:
    items = client.get(
        f"/projects/{acme.projects[0]}/issues?limit=3", headers=auth(acme.member)
    ).json()["items"]
    assert [[label["id"] for label in item["labels"]] for item in items] == [
        [],
        [BUG],
        [BUG, FEATURE],
    ]


def test_attach_returns_the_issue_with_its_labels(client, acme) -> None:
    response = attach(client, acme.member, acme.issues[0], DOCS)
    assert response.status_code == 200
    assert response.json()["id"] == acme.issues[0]
    assert [label["id"] for label in response.json()["labels"]] == [DOCS]


def test_labels_are_ordered_by_id(client, acme) -> None:
    attach(client, acme.member, acme.issues[1], DOCS)
    attach(client, acme.member, acme.issues[1], FEATURE)
    assert on_issue(client, acme.member, acme.issues[1]) == [BUG, FEATURE, DOCS]


def test_attaching_twice_changes_nothing(client, acme) -> None:
    response = attach(client, acme.member, acme.issues[1], BUG)
    assert response.status_code == 200
    assert [label["id"] for label in response.json()["labels"]] == [BUG]


def test_attaching_twice_adds_no_audit_row(client, acme) -> None:
    assert on_issue(client, acme.member, acme.issues[1]) == [BUG]
    before = audit(client, acme)
    attach(client, acme.member, acme.issues[1], BUG)
    assert audit(client, acme) == before


def test_labels_do_not_change_the_version(client, acme) -> None:
    attach(client, acme.member, acme.issues[0], BUG)
    issue = client.get(f"/issues/{acme.issues[0]}", headers=auth(acme.member)).json()
    assert ([label["id"] for label in issue["labels"]], issue["version"]) == ([BUG], 1)


def test_detach_returns_204(client, acme) -> None:
    assert detach(client, acme.member, acme.issues[2], BUG).status_code == 204
    assert on_issue(client, acme.member, acme.issues[2]) == [FEATURE]


def test_detaching_a_label_the_issue_lacks_is_404(client, acme) -> None:
    response = detach(client, acme.member, acme.issues[1], DOCS)
    assert response.status_code == 404
    assert error_code(response) == "not_found"
    assert on_issue(client, acme.member, acme.issues[1]) == [BUG]


def test_attaching_another_orgs_label_is_404(client, acme) -> None:
    response = attach(client, acme.member, acme.issues[0], GLOBEX_BUG)
    assert response.status_code == 404
    assert on_issue(client, acme.member, acme.issues[0]) == []


def test_attaching_to_another_orgs_issue_is_404(client, acme, globex) -> None:
    assert attach(client, acme.member, globex.issues[0], BUG).status_code == 404
    assert on_issue(client, globex.member, globex.issues[0]) == []


def test_detaching_from_another_orgs_issue_is_404(client, acme, globex) -> None:
    assert detach(client, acme.member, globex.issues[1], GLOBEX_BUG).status_code == 404
    assert on_issue(client, globex.member, globex.issues[1]) == [GLOBEX_BUG]


def test_attaching_to_a_deleted_issue_is_404(client, acme) -> None:
    client.delete(f"/issues/{acme.issues[0]}", headers=auth(acme.member))
    assert attach(client, acme.member, acme.issues[0], BUG).status_code == 404
    assert attach(client, acme.member, acme.issues[3], BUG).status_code == 200


def test_attaching_in_an_archived_project_is_404(client, acme) -> None:
    client.delete(f"/projects/{acme.projects[1]}", headers=auth(acme.admin))
    assert attach(client, acme.member, acme.issues[10], BUG).status_code == 404
    assert attach(client, acme.member, acme.issues[0], BUG).status_code == 200


def test_viewer_cannot_attach_or_detach(client, acme) -> None:
    assert attach(client, acme.viewer, acme.issues[0], BUG).status_code == 403
    assert detach(client, acme.viewer, acme.issues[1], BUG).status_code == 403
    assert on_issue(client, acme.viewer, acme.issues[1]) == [BUG]


def test_attach_with_an_invalid_label_id_is_422(client, acme) -> None:
    assert attach(client, acme.member, acme.issues[0], "bug").status_code == 422
    assert on_issue(client, acme.member, acme.issues[0]) == []


# -- label filter on project issues ---------------------------------------------------------------


def test_project_list_filters_by_label(client, acme) -> None:
    items = client.get(
        f"/projects/{acme.projects[0]}/issues?label_id={BUG}", headers=auth(acme.member)
    ).json()["items"]
    assert [item["id"] for item in items] == [acme.issues[1], acme.issues[2]]


def test_project_list_label_without_issues_is_empty(client, acme) -> None:
    response = client.get(
        f"/projects/{acme.projects[0]}/issues?label_id={DOCS}", headers=auth(acme.member)
    )
    assert response.json() == {"items": [], "next_cursor": None}


def test_project_list_label_of_another_org_is_404(client, acme) -> None:
    response = client.get(
        f"/projects/{acme.projects[0]}/issues?label_id={GLOBEX_BUG}", headers=auth(acme.member)
    )
    assert response.status_code == 404
    assert error_code(response) == "not_found"


# -- audit ----------------------------------------------------------------------------------------


def test_label_writes_are_audited(client, acme) -> None:
    before = audit(client, acme)
    label = create(client, acme.member, "audited").json()["id"]
    update(client, acme.member, label, color="#000000")
    remove(client, acme.member, label)
    rows = audit(client, acme)[len(before) :]
    assert [(r["action"], r["entity"], r["entity_id"]) for r in rows] == [
        ("label.create", "label", label),
        ("label.update", "label", label),
        ("label.delete", "label", label),
    ]


def test_issue_label_writes_are_audited_on_the_issue(client, acme) -> None:
    before = audit(client, acme)
    attach(client, acme.member, acme.issues[0], DOCS)
    detach(client, acme.member, acme.issues[0], DOCS)
    rows = audit(client, acme)[len(before) :]
    assert [(r["action"], r["entity"], r["entity_id"]) for r in rows] == [
        ("issue.label_add", "issue", acme.issues[0]),
        ("issue.label_remove", "issue", acme.issues[0]),
    ]


def test_refused_writes_add_no_audit_rows(client, acme) -> None:
    assert label_ids(client, acme.member) == [BUG, FEATURE, DOCS]
    before = audit(client, acme)
    create(client, acme.member, "bug")
    create(client, acme.viewer, "nope")
    update(client, acme.member, DOCS, name="feature")
    detach(client, acme.member, acme.issues[1], DOCS)
    assert audit(client, acme) == before
