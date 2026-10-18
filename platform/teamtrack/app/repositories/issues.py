from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Issue
from app.repositories.common import page, split_page


def get(session: Session, org_id: int, issue_id: int) -> Issue | None:
    """Live (not soft-deleted) issue in the org."""
    return session.scalar(
        select(Issue).where(
            Issue.org_id == org_id, Issue.id == issue_id, Issue.deleted_at.is_(None)
        )
    )


def list_for_project(
    session: Session, org_id: int, project_id: int, after: int | None, limit: int
) -> tuple[list[Issue], int | None]:
    base = select(Issue).where(
        Issue.org_id == org_id, Issue.project_id == project_id, Issue.deleted_at.is_(None)
    )
    stmt = page(base, Issue.id, after, limit)
    return split_page(list(session.scalars(stmt)), limit, lambda i: i.id)


def add(
    session: Session,
    org_id: int,
    project_id: int,
    title: str,
    description: str,
    priority: str,
    assignee_id: int | None,
    created_by: int,
) -> Issue:
    issue = Issue(
        org_id=org_id,
        project_id=project_id,
        title=title,
        description=description,
        priority=priority,
        assignee_id=assignee_id,
        created_by=created_by,
    )
    session.add(issue)
    session.flush()
    return issue


def list_all_legacy(session: Session, offset: int, limit: int) -> list[Issue]:
    """LEGACY (used only by /v1/issues). Not tenant-scoped: do not use or copy this function."""
    return list(session.scalars(select(Issue).order_by(Issue.id).offset(offset).limit(limit)))
