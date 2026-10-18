"""F3 hidden tests: Idempotency-Key on POST /projects/{project_id}/issues (docs/features/f3.md)."""

from __future__ import annotations

from hidden_support import auth, error_code


def create(client, user_id: int, project_id: int, key: str | None = None, **body):  # type: ignore[no-untyped-def]
    headers = {**auth(user_id), **({"Idempotency-Key": key} if key is not None else {})}
    payload = {"title": "Retry-safe issue", **body}
    return client.post(f"/projects/{project_id}/issues", json=payload, headers=headers)


def count(client, user_id: int, project_id: int) -> int:  # type: ignore[no-untyped-def]
    items = client.get(f"/projects/{project_id}/issues?limit=100", headers=auth(user_id))
    return len(items.json()["items"])


def titled(client, user_id: int, project_id: int, title: str) -> int:  # type: ignore[no-untyped-def]
    items = client.get(f"/projects/{project_id}/issues?limit=100", headers=auth(user_id))
    return sum(1 for item in items.json()["items"] if item["title"] == title)


def audit(client, o) -> list[str]:  # type: ignore[no-untyped-def]
    items = client.get("/audit?limit=100", headers=auth(o.admin)).json()["items"]
    return [item["action"] for item in items]


# -- replay ---------------------------------------------------------------------------------------


def test_replay_status_is_201(client, acme) -> None:
    first = create(client, acme.member, acme.projects[0], "r1")
    again = create(client, acme.member, acme.projects[0], "r1")
    assert (again.status_code, again.json()["id"]) == (201, first.json()["id"])


def test_replay_returns_the_same_body(client, acme) -> None:
    first = create(client, acme.member, acme.projects[0], "r2")
    assert create(client, acme.member, acme.projects[0], "r2").json() == first.json()


def test_replay_returns_the_same_issue_id(client, acme) -> None:
    first = create(client, acme.member, acme.projects[0], "r3").json()["id"]
    assert create(client, acme.member, acme.projects[0], "r3").json()["id"] == first


def test_replay_creates_no_issue(client, acme) -> None:
    create(client, acme.member, acme.projects[0], "r4")
    before = count(client, acme.member, acme.projects[0])
    create(client, acme.member, acme.projects[0], "r4")
    assert count(client, acme.member, acme.projects[0]) == before


def test_three_sends_create_one_issue(client, acme) -> None:
    for _ in range(3):
        create(client, acme.member, acme.projects[0], "r5", title="Sent three times")
    assert titled(client, acme.member, acme.projects[0], "Sent three times") == 1


def test_replay_adds_no_audit_row(client, acme) -> None:
    create(client, acme.member, acme.projects[0], "r6")
    before = audit(client, acme)
    create(client, acme.member, acme.projects[0], "r6")
    assert audit(client, acme) == before


def test_first_request_adds_one_issue_create_row(client, acme) -> None:
    before = audit(client, acme)
    create(client, acme.member, acme.projects[0], "r7")
    create(client, acme.member, acme.projects[0], "r7")
    assert audit(client, acme)[len(before) :] == ["issue.create"]


def test_replay_with_all_fields(client, acme) -> None:
    body = {
        "title": "Full",
        "description": "Every field",
        "priority": "high",
        "assignee_id": acme.member,
    }
    first = create(client, acme.member, acme.projects[0], "r8", **body)
    again = create(client, acme.member, acme.projects[0], "r8", **body)
    assert again.json() == first.json()
    assert titled(client, acme.member, acme.projects[0], "Full") == 1


def test_replay_by_another_user_of_the_org(client, acme) -> None:
    first = create(client, acme.member, acme.projects[0], "r9")
    again = create(client, acme.admin, acme.projects[0], "r9")
    assert again.json()["id"] == first.json()["id"]


def test_replay_as_admin(client, globex) -> None:
    first = create(client, globex.admin, globex.projects[1], "r10")
    again = create(client, globex.admin, globex.projects[1], "r10")
    assert (again.status_code, again.json()) == (201, first.json())


def test_replay_after_the_issue_changed_returns_the_first_response(client, acme) -> None:
    first = create(client, acme.member, acme.projects[0], "r11").json()
    client.delete(f"/issues/{first['id']}", headers=auth(acme.member))
    again = create(client, acme.member, acme.projects[0], "r11")
    assert (again.status_code, again.json()) == (201, first)


def test_replay_keeps_the_original_version(client, acme) -> None:
    first = create(client, acme.member, acme.projects[0], "r12").json()
    assert first["version"] == 1
    again = create(client, acme.member, acme.projects[0], "r12").json()
    assert (again["id"], again["version"]) == (first["id"], 1)


def test_replay_in_globex(client, globex) -> None:
    create(client, globex.member, globex.projects[0], "r13")
    before = count(client, globex.member, globex.projects[0])
    create(client, globex.member, globex.projects[0], "r13")
    assert count(client, globex.member, globex.projects[0]) == before


# -- conflicts ------------------------------------------------------------------------------------


def test_other_title_is_409(client, acme) -> None:
    create(client, acme.member, acme.projects[0], "c1")
    response = create(client, acme.member, acme.projects[0], "c1", title="Different")
    assert response.status_code == 409
    assert error_code(response) == "idempotency_conflict"


def test_other_priority_is_409(client, acme) -> None:
    create(client, acme.member, acme.projects[0], "c2", priority="low")
    response = create(client, acme.member, acme.projects[0], "c2", priority="high")
    assert response.status_code == 409
    assert error_code(response) == "idempotency_conflict"


def test_other_description_is_409(client, acme) -> None:
    create(client, acme.member, acme.projects[0], "c3", description="one")
    response = create(client, acme.member, acme.projects[0], "c3", description="two")
    assert response.status_code == 409


def test_other_assignee_is_409(client, acme) -> None:
    create(client, acme.member, acme.projects[0], "c4", assignee_id=acme.member)
    response = create(client, acme.member, acme.projects[0], "c4", assignee_id=acme.admin)
    assert response.status_code == 409


def test_conflict_creates_nothing(client, acme) -> None:
    create(client, acme.member, acme.projects[0], "c5")
    before = count(client, acme.member, acme.projects[0])
    create(client, acme.member, acme.projects[0], "c5", title="Not created")
    assert count(client, acme.member, acme.projects[0]) == before
    assert titled(client, acme.member, acme.projects[0], "Not created") == 0


def test_conflict_adds_no_audit_row(client, acme) -> None:
    create(client, acme.member, acme.projects[0], "c6")
    before = audit(client, acme)
    create(client, acme.member, acme.projects[0], "c6", title="Other")
    assert audit(client, acme) == before


def test_conflict_uses_the_error_envelope(client, acme) -> None:
    create(client, acme.member, acme.projects[0], "c7")
    body = create(client, acme.member, acme.projects[0], "c7", title="Other").json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message"}
    assert body["error"]["code"] == "idempotency_conflict"


def test_original_body_still_replays_after_a_conflict(client, acme) -> None:
    first = create(client, acme.member, acme.projects[0], "c8").json()
    create(client, acme.member, acme.projects[0], "c8", title="Other")
    assert create(client, acme.member, acme.projects[0], "c8").json() == first


# -- scope ----------------------------------------------------------------------------------------


def test_same_key_in_two_orgs_creates_two_issues(client, acme, globex) -> None:
    mine = create(client, acme.member, acme.projects[0], "s1", title="Shared key")
    theirs = create(client, globex.member, globex.projects[0], "s1", title="Shared key")
    assert mine.status_code == theirs.status_code == 201
    assert theirs.json()["org_id"] == globex.org_id
    again = create(client, globex.member, globex.projects[0], "s1", title="Shared key")
    assert again.json()["id"] == theirs.json()["id"]


def test_other_orgs_key_with_a_different_body_is_not_a_conflict(client, acme, globex) -> None:
    create(client, acme.member, acme.projects[0], "s2", title="Acme title")
    response = create(client, globex.member, globex.projects[0], "s2", title="Globex title")
    assert response.status_code == 201
    assert response.json()["title"] == "Globex title"
    again = create(client, globex.member, globex.projects[0], "s2", title="Globex title")
    assert again.json()["id"] == response.json()["id"]


def test_project_key_does_not_replay_on_issue_creation(client, acme) -> None:
    headers = {**auth(acme.member), "Idempotency-Key": "s3"}
    project = client.post("/projects", json={"name": "Keys", "key": "KEYS"}, headers=headers)
    assert project.status_code == 201
    issue = create(client, acme.member, acme.projects[0], "s3")
    assert issue.status_code == 201
    assert issue.json()["project_id"] == acme.projects[0]
    again = create(client, acme.member, acme.projects[0], "s3")
    assert again.json()["id"] == issue.json()["id"]


def test_issue_key_does_not_block_project_creation(client, acme) -> None:
    create(client, acme.member, acme.projects[0], "s4")
    create(client, acme.member, acme.projects[0], "s4")
    headers = {**auth(acme.member), "Idempotency-Key": "s4"}
    project = client.post("/projects", json={"name": "Free", "key": "FREE"}, headers=headers)
    assert project.status_code == 201
    assert titled(client, acme.member, acme.projects[0], "Retry-safe issue") == 1


def test_another_projects_path_is_a_new_request(client, acme) -> None:
    first = create(client, acme.member, acme.projects[0], "s5")
    second = create(client, acme.member, acme.projects[1], "s5")
    assert second.status_code == 201
    assert second.json()["project_id"] == acme.projects[1]
    assert second.json()["id"] != first.json()["id"]
    assert create(client, acme.member, acme.projects[1], "s5").json() == second.json()


def test_different_keys_create_different_issues(client, acme) -> None:
    first = create(client, acme.member, acme.projects[0], "d1", title="Twin")
    second = create(client, acme.member, acme.projects[0], "d2", title="Twin")
    assert first.json()["id"] != second.json()["id"]
    assert create(client, acme.member, acme.projects[0], "d1", title="Twin").json() == first.json()


def test_keys_are_compared_exactly(client, acme) -> None:
    lower = create(client, acme.member, acme.projects[0], "case-key", title="Lower")
    upper = create(client, acme.member, acme.projects[0], "CASE-KEY", title="Upper")
    assert upper.status_code == 201
    assert upper.json()["id"] != lower.json()["id"]
    assert create(client, acme.member, acme.projects[0], "case-key", title="Lower").json() == (
        lower.json()
    )


def test_long_key_works(client, acme) -> None:
    key = "k" * 150
    first = create(client, acme.member, acme.projects[0], key)
    assert create(client, acme.member, acme.projects[0], key).json() == first.json()


# -- failures are not remembered ------------------------------------------------------------------


def test_failed_404_does_not_use_up_the_key(client, acme, globex) -> None:
    assert create(client, acme.member, globex.projects[0], "f1").status_code == 404
    created = create(client, acme.member, acme.projects[0], "f1")
    assert created.status_code == 201
    assert create(client, acme.member, acme.projects[0], "f1").json() == created.json()


def test_failed_422_does_not_use_up_the_key(client, acme) -> None:
    assert create(client, acme.member, acme.projects[0], "f2", title="").status_code == 422
    created = create(client, acme.member, acme.projects[0], "f2", title="Valid now")
    assert created.status_code == 201
    assert create(client, acme.member, acme.projects[0], "f2", title="Valid now").json() == (
        created.json()
    )


def test_failed_403_does_not_use_up_the_key(client, acme) -> None:
    assert create(client, acme.viewer, acme.projects[0], "f3").status_code == 403
    created = create(client, acme.member, acme.projects[0], "f3")
    assert created.status_code == 201
    assert (
        create(client, acme.member, acme.projects[0], "f3").json()["id"] == (created.json()["id"])
    )


def test_invalid_assignee_does_not_use_up_the_key(client, acme, globex) -> None:
    bad = create(client, acme.member, acme.projects[0], "f4", assignee_id=globex.member)
    assert bad.status_code == 422
    good = create(client, acme.member, acme.projects[0], "f4")
    assert good.status_code == 201
    assert create(client, acme.member, acme.projects[0], "f4").json() == good.json()


def test_archived_project_with_a_key_is_404_and_stores_nothing(client, acme) -> None:
    client.delete(f"/projects/{acme.projects[1]}", headers=auth(acme.admin))
    assert create(client, acme.member, acme.projects[1], "f5").status_code == 404
    created = create(client, acme.member, acme.projects[0], "f5")
    assert create(client, acme.member, acme.projects[0], "f5").json() == created.json()


# -- the rest of the endpoint keeps working -------------------------------------------------------


def test_board_issue_list_shows_one_card_after_a_replay(client, acme) -> None:
    create(client, acme.member, acme.projects[0], "b1", title="Board once")
    create(client, acme.member, acme.projects[0], "b1", title="Board once")
    client.post("/board/login", data={"email": "member@acme.test"}, follow_redirects=False)
    html = client.get(f"/board/projects/{acme.projects[0]}").text
    assert html.count("Board once") == 1


def test_audit_counts_one_create_per_key(client, acme) -> None:
    before = audit(client, acme)
    for key in ("a1", "a2", "a1", "a2", "a1"):
        create(client, acme.member, acme.projects[0], key)
    assert audit(client, acme)[len(before) :] == ["issue.create", "issue.create"]


def test_replayed_issue_appears_once_in_the_project_list(client, acme) -> None:
    created = create(client, acme.member, acme.projects[0], "l1", title="Listed once").json()
    create(client, acme.member, acme.projects[0], "l1", title="Listed once")
    items = client.get(
        f"/projects/{acme.projects[0]}/issues?limit=100", headers=auth(acme.member)
    ).json()["items"]
    assert [item["id"] for item in items].count(created["id"]) == 1
    assert titled(client, acme.member, acme.projects[0], "Listed once") == 1


def test_replay_names_the_original_creator(client, acme) -> None:
    create(client, acme.member, acme.projects[0], "x1")
    again = create(client, acme.admin, acme.projects[0], "x1")
    assert again.json()["created_by"] == acme.member


def test_replay_between_two_creates_adds_nothing(client, acme) -> None:
    before = count(client, acme.member, acme.projects[0])
    first = create(client, acme.member, acme.projects[0], "x2").json()["id"]
    replay = create(client, acme.member, acme.projects[0], "x2").json()["id"]
    plain = create(client, acme.member, acme.projects[0]).json()["id"]
    assert replay == first != plain
    assert count(client, acme.member, acme.projects[0]) == before + 2


def test_conflict_after_several_replays(client, acme) -> None:
    for _ in range(3):
        create(client, acme.member, acme.projects[0], "x3")
    response = create(client, acme.member, acme.projects[0], "x3", title="Changed later")
    assert response.status_code == 409
    assert titled(client, acme.member, acme.projects[0], "Retry-safe issue") == 1


def test_conflict_in_globex(client, globex) -> None:
    create(client, globex.member, globex.projects[1], "x4")
    response = create(client, globex.member, globex.projects[1], "x4", priority="low")
    assert response.status_code == 409
    assert error_code(response) == "idempotency_conflict"


def test_replay_on_the_second_project(client, acme) -> None:
    first = create(client, acme.member, acme.projects[1], "x5", title="Mobile retry")
    create(client, acme.member, acme.projects[1], "x5", title="Mobile retry")
    assert titled(client, acme.member, acme.projects[1], "Mobile retry") == 1
    assert first.json()["project_id"] == acme.projects[1]


def test_replay_with_the_default_priority_written_out(client, acme) -> None:
    first = create(client, acme.member, acme.projects[0], "x6", priority="medium")
    again = create(client, acme.member, acme.projects[0], "x6", priority="medium")
    assert again.json()["id"] == first.json()["id"]
    assert again.json()["priority"] == "medium"
