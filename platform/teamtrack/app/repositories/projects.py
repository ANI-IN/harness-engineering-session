from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Project
from app.repositories.common import page, split_page


def get(session: Session, org_id: int, project_id: int) -> Project | None:
    """Active (not archived) project in the org."""
    return session.scalar(
        select(Project).where(
            Project.org_id == org_id, Project.id == project_id, Project.archived_at.is_(None)
        )
    )


def get_by_key(session: Session, org_id: int, key: str) -> Project | None:
    return session.scalar(select(Project).where(Project.org_id == org_id, Project.key == key))


def list_page(
    session: Session, org_id: int, after: int | None, limit: int
) -> tuple[list[Project], int | None]:
    base = select(Project).where(Project.org_id == org_id, Project.archived_at.is_(None))
    stmt = page(base, Project.id, after, limit)
    return split_page(list(session.scalars(stmt)), limit, lambda p: p.id)


def add(session: Session, org_id: int, name: str, key: str) -> Project:
    project = Project(org_id=org_id, name=name, key=key)
    session.add(project)
    session.flush()
    return project
