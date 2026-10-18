from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Issue, Project, Watcher
from app.repositories.common import page, split_page


def get(session: Session, org_id: int, issue_id: int, user_id: int) -> Watcher | None:
    return session.scalar(
        select(Watcher).where(
            Watcher.org_id == org_id, Watcher.issue_id == issue_id, Watcher.user_id == user_id
        )
    )


def list_for_issue(
    session: Session, org_id: int, issue_id: int, after: int | None, limit: int
) -> tuple[list[Watcher], int | None]:
    base = select(Watcher).where(Watcher.org_id == org_id, Watcher.issue_id == issue_id)
    stmt = page(base, Watcher.id, after, limit)
    return split_page(list(session.scalars(stmt)), limit, lambda w: w.id)


def watched_issues(
    session: Session, org_id: int, user_id: int, after: int | None, limit: int
) -> tuple[list[Issue], int | None]:
    """Live issues in active projects that the user watches, by ascending issue id."""
    base = (
        select(Issue)
        .join(Watcher, Watcher.issue_id == Issue.id)
        .join(Project, Project.id == Issue.project_id)
        .where(
            Watcher.org_id == org_id,
            Watcher.user_id == user_id,
            Issue.org_id == org_id,
            Issue.deleted_at.is_(None),
            Project.archived_at.is_(None),
        )
    )
    stmt = page(base, Issue.id, after, limit)
    return split_page(list(session.scalars(stmt)), limit, lambda i: i.id)


def add(session: Session, org_id: int, issue_id: int, user_id: int) -> Watcher:
    watcher = Watcher(org_id=org_id, issue_id=issue_id, user_id=user_id)
    session.add(watcher)
    session.flush()
    return watcher


def remove(session: Session, watcher: Watcher) -> None:
    session.delete(watcher)
    session.flush()
