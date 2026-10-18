"""Comments on issues (F2). Every function works only inside actor.org_id."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Comment, Issue
from app.repositories import comments as comments_repo
from app.repositories import issues as issues_repo
from app.repositories import projects as projects_repo
from app.services import audit
from app.services.context import Actor
from app.services.errors import Forbidden, Invalid, NotFound

MAX_BODY = 5000


def _issue(session: Session, actor: Actor, issue_id: int) -> Issue:
    """A live issue in an active project of the caller's org; anything else is a 404."""
    issue = issues_repo.get(session, actor.org_id, issue_id)
    if issue is None or projects_repo.get(session, actor.org_id, issue.project_id) is None:
        raise NotFound("issue not found")
    return issue


def list_page(
    session: Session, actor: Actor, issue_id: int, after: int | None, limit: int
) -> tuple[list[Comment], int | None]:
    issue = _issue(session, actor, issue_id)
    return comments_repo.list_for_issue(session, actor.org_id, issue.id, after, limit)


def create(
    session: Session, actor: Actor, issue_id: int, body: str, *, commit: bool = True
) -> Comment:
    issue = _issue(session, actor, issue_id)
    if not isinstance(body, str) or not 1 <= len(body) <= MAX_BODY:
        raise Invalid(f"body must be 1 to {MAX_BODY} characters")
    comment = comments_repo.add(session, actor.org_id, issue.id, actor.user_id, body)
    audit.record(session, actor, "comment.create", "comment", comment.id)
    if commit:
        session.commit()
    return comment


def delete(session: Session, actor: Actor, comment_id: int) -> None:
    comment = comments_repo.get(session, actor.org_id, comment_id)
    if comment is None:
        raise NotFound("comment not found")
    _issue(session, actor, comment.issue_id)
    if comment.author_id != actor.user_id and not actor.is_admin:
        raise Forbidden("only the author or an admin can delete a comment")
    audit.record(session, actor, "comment.delete", "comment", comment.id)
    comments_repo.remove(session, comment)
    session.commit()
