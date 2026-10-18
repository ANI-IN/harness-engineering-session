from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.models import Issue, IssueLabel, Project
from app.repositories.common import page, split_page


def get(session: Session, org_id: int, issue_id: int) -> Issue | None:
    """Live (not soft-deleted) issue in the org."""
    return session.scalar(
        select(Issue).where(
            Issue.org_id == org_id, Issue.id == issue_id, Issue.deleted_at.is_(None)
        )
    )


def list_for_project(
    session: Session,
    org_id: int,
    project_id: int,
    after: int | None,
    limit: int,
    label_id: int | None = None,
) -> tuple[list[Issue], int | None]:
    base = select(Issue).where(
        Issue.org_id == org_id, Issue.project_id == project_id, Issue.deleted_at.is_(None)
    )
    if label_id is not None:
        base = base.where(Issue.id.in_(labelled(label_id)))
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


def search(
    session: Session,
    org_id: int,
    *,
    status: str | None,
    priority: str | None,
    assignee_id: int | None,
    project_id: int | None,
    q: str | None,
    after: int | None,
    limit: int,
    label_id: int | None = None,
) -> tuple[list[Issue], int | None]:
    """Live issues of the org in active projects; `q` is a case-insensitive title substring."""
    base = (
        select(Issue)
        .join(Project, Project.id == Issue.project_id)
        .where(
            Issue.org_id == org_id,
            Issue.deleted_at.is_(None),
            Project.org_id == org_id,
            Project.archived_at.is_(None),
        )
    )
    if status is not None:
        base = base.where(Issue.status == status)
    if priority is not None:
        base = base.where(Issue.priority == priority)
    if assignee_id is not None:
        base = base.where(Issue.assignee_id == assignee_id)
    if project_id is not None:
        base = base.where(Issue.project_id == project_id)
    if label_id is not None:
        base = base.where(Issue.id.in_(labelled(label_id)))
    if q:
        # autoescape: % and _ in the query are literal characters, not LIKE wildcards.
        base = base.where(func.lower(Issue.title).contains(q.lower(), autoescape=True))
    stmt = page(base, Issue.id, after, limit)
    return split_page(list(session.scalars(stmt)), limit, lambda i: i.id)


def get_many(session: Session, org_id: int, project_id: int, issue_ids: list[int]) -> list[Issue]:
    """Live issues of one project in the org among `issue_ids` (missing ids are left out)."""
    return list(
        session.scalars(
            select(Issue).where(
                Issue.org_id == org_id,
                Issue.project_id == project_id,
                Issue.id.in_(issue_ids),
                Issue.deleted_at.is_(None),
            )
        )
    )


def labelled(label_id: int) -> Select[tuple[int]]:
    """Ids of the issues that carry a label (callers have checked the label's org)."""
    return select(IssueLabel.issue_id).where(IssueLabel.label_id == label_id)
