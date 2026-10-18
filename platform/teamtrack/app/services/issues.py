from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import AuditEntry, Issue
from app.repositories import issues as issues_repo
from app.repositories import users as users_repo
from app.services import audit, projects
from app.services.context import Actor
from app.services.errors import Invalid, NotFound, ServiceError

PRIORITIES = frozenset({"low", "medium", "high"})

TRANSITIONS: dict[str, frozenset[str]] = {
    "open": frozenset({"in_progress"}),
    "in_progress": frozenset({"open", "done"}),
    "done": frozenset({"open"}),
}


def _validate(title: object = None, description: object = None, priority: object = None) -> None:
    """Field rules enforced here so every caller (API, board, scripts) gets them."""
    if title is not None and not (isinstance(title, str) and 1 <= len(title.strip()) <= 200):
        raise Invalid("title must be 1 to 200 characters")
    if description is not None and not (
        isinstance(description, str) and len(description) <= 10_000
    ):
        raise Invalid("description must be at most 10,000 characters")
    if priority is not None and priority not in PRIORITIES:
        raise Invalid("priority must be one of: low, medium, high")


def get(session: Session, actor: Actor, issue_id: int) -> Issue:
    issue = issues_repo.get(session, actor.org_id, issue_id)
    if issue is None:
        raise NotFound("issue not found")
    return issue


def list_for_project(
    session: Session, actor: Actor, project_id: int, after: int | None, limit: int
) -> tuple[list[Issue], int | None]:
    project = projects.get(session, actor, project_id)
    return issues_repo.list_for_project(session, actor.org_id, project.id, after, limit)


def _check_assignee(session: Session, actor: Actor, assignee_id: int | None) -> None:
    if assignee_id is not None and users_repo.get(session, actor.org_id, assignee_id) is None:
        raise Invalid("assignee must belong to your organization", code="invalid_assignee")


def _touch(issue: Issue) -> None:
    issue.version += 1
    issue.updated_at = utcnow()


def create(
    session: Session,
    actor: Actor,
    project_id: int,
    title: str,
    description: str,
    priority: str,
    assignee_id: int | None,
    *,
    commit: bool = True,
) -> Issue:
    project = projects.get(session, actor, project_id)
    _validate(title, description, priority)
    _check_assignee(session, actor, assignee_id)
    issue = issues_repo.add(
        session, actor.org_id, project.id, title, description, priority, assignee_id, actor.user_id
    )
    audit.record(session, actor, "issue.create", "issue", issue.id)
    if commit:
        session.commit()
    return issue


class PreconditionFailed(ServiceError):
    status_code = 412
    code = "precondition_failed"


def etag(issue: Issue) -> str:
    """The issue's entity tag: its version in double quotes."""
    return f'"{issue.version}"'


def check_if_match(
    session: Session, actor: Actor, issue_id: int, if_match: str | None
) -> int | None:
    """Optimistic concurrency: 404 for an issue the caller cannot see. Without If-Match the write
    is not conditional (None). Otherwise If-Match must be the current ETag; a stale, empty, or
    malformed value is 412. Returns the version the write is based on."""
    issue = get(session, actor, issue_id)
    if if_match is None:
        return None
    if if_match.strip() != etag(issue):
        raise PreconditionFailed(f"the issue has changed; current version is {issue.version}")
    return issue.version


def _get_at(session: Session, actor: Actor, issue_id: int, expected_version: int | None) -> Issue:
    issue = get(session, actor, issue_id)
    if expected_version is not None and expected_version != issue.version:
        raise PreconditionFailed(f"the issue has changed; current version is {issue.version}")
    return issue


def history(
    session: Session, actor: Actor, issue_id: int, after: int | None, limit: int
) -> tuple[list[AuditEntry], int | None]:
    """The issue's audit entries, oldest first."""
    issue = get(session, actor, issue_id)
    return audit.list_for_entity(session, actor, "issue", issue.id, after, limit)


def update(
    session: Session,
    actor: Actor,
    issue_id: int,
    changes: dict[str, object],
    expected_version: int | None = None,
) -> Issue:
    issue = _get_at(session, actor, issue_id, expected_version)
    _validate(changes.get("title"), changes.get("description"), changes.get("priority"))
    for field in ("title", "description", "priority"):
        if changes.get(field) is not None:
            setattr(issue, field, changes[field])
    _touch(issue)
    audit.record(session, actor, "issue.update", "issue", issue.id)
    session.commit()
    return issue


def assign(
    session: Session,
    actor: Actor,
    issue_id: int,
    assignee_id: int | None,
    expected_version: int | None = None,
) -> Issue:
    issue = _get_at(session, actor, issue_id, expected_version)
    _check_assignee(session, actor, assignee_id)
    issue.assignee_id = assignee_id
    _touch(issue)
    audit.record(session, actor, "issue.assign", "issue", issue.id)
    session.commit()
    return issue


def transition(
    session: Session,
    actor: Actor,
    issue_id: int,
    status: str,
    expected_version: int | None = None,
) -> Issue:
    issue = _get_at(session, actor, issue_id, expected_version)
    if status not in TRANSITIONS.get(issue.status, frozenset()):
        raise Invalid(
            f"cannot move an issue from {issue.status} to {status}", code="invalid_transition"
        )
    issue.status = status
    _touch(issue)
    audit.record(session, actor, "issue.transition", "issue", issue.id)
    session.commit()
    return issue


def delete(session: Session, actor: Actor, issue_id: int) -> None:
    issue = get(session, actor, issue_id)
    issue.deleted_at = utcnow()
    _touch(issue)
    audit.record(session, actor, "issue.delete", "issue", issue.id)
    session.commit()


def search(
    session: Session,
    actor: Actor,
    *,
    status: str | None = None,
    priority: str | None = None,
    assignee_id: int | None = None,
    project_id: int | None = None,
    q: str | None = None,
    after: int | None = None,
    limit: int = 20,
) -> tuple[list[Issue], int | None]:
    """Org-wide search: live issues of the caller's org in active projects, filters ANDed.

    A project or assignee id that is not in the caller's org is a 404, exactly as if it did not
    exist (house rule R1)."""
    if project_id is not None:
        projects.get(session, actor, project_id)
    if assignee_id is not None and users_repo.get(session, actor.org_id, assignee_id) is None:
        raise NotFound("assignee not found")
    return issues_repo.search(
        session,
        actor.org_id,
        status=status,
        priority=priority,
        assignee_id=assignee_id,
        project_id=project_id,
        q=q,
        after=after,
        limit=limit,
    )
