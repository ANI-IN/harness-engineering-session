"""Issue watchers (F6). Every function works only inside actor.org_id."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Issue, Watcher
from app.repositories import issues as issues_repo
from app.repositories import projects as projects_repo
from app.repositories import users as users_repo
from app.repositories import watchers as watchers_repo
from app.services import audit
from app.services.context import Actor
from app.services.errors import NotFound


def _issue(session: Session, actor: Actor, issue_id: int) -> Issue:
    """A live issue in an active project of the caller's org; anything else is a 404."""
    issue = issues_repo.get(session, actor.org_id, issue_id)
    if issue is None or projects_repo.get(session, actor.org_id, issue.project_id) is None:
        raise NotFound("issue not found")
    return issue


def _user(session: Session, actor: Actor, user_id: int) -> int:
    if users_repo.get(session, actor.org_id, user_id) is None:
        raise NotFound("user not found")
    return user_id


def list_page(
    session: Session, actor: Actor, issue_id: int, after: int | None, limit: int
) -> tuple[list[Watcher], int | None]:
    issue = _issue(session, actor, issue_id)
    return watchers_repo.list_for_issue(session, actor.org_id, issue.id, after, limit)


def watching(
    session: Session, actor: Actor, after: int | None, limit: int
) -> tuple[list[Issue], int | None]:
    return watchers_repo.watched_issues(session, actor.org_id, actor.user_id, after, limit)


def watch(session: Session, actor: Actor, issue_id: int, user_id: int | None = None) -> None:
    """Add a watcher (the caller, or `user_id` for admins). Watching twice changes nothing."""
    issue = _issue(session, actor, issue_id)
    target = actor.user_id if user_id is None else _user(session, actor, user_id)
    if watchers_repo.get(session, actor.org_id, issue.id, target) is not None:
        return
    watchers_repo.add(session, actor.org_id, issue.id, target)
    audit.record(session, actor, "watcher.add", "issue", issue.id)
    session.commit()


def unwatch(session: Session, actor: Actor, issue_id: int, user_id: int | None = None) -> None:
    """Remove a watcher. Removing someone who does not watch the issue changes nothing."""
    issue = _issue(session, actor, issue_id)
    target = actor.user_id if user_id is None else _user(session, actor, user_id)
    watcher = watchers_repo.get(session, actor.org_id, issue.id, target)
    if watcher is None:
        return
    watchers_repo.remove(session, watcher)
    audit.record(session, actor, "watcher.remove", "issue", issue.id)
    session.commit()
