from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ProjectMember
from app.repositories.common import page, split_page


def get(session: Session, project_id: int, user_id: int) -> ProjectMember | None:
    return session.get(ProjectMember, (project_id, user_id))


def list_page(
    session: Session, project_id: int, after: int | None, limit: int
) -> tuple[list[ProjectMember], int | None]:
    """Members of a project the caller already resolved within its org."""
    base = select(ProjectMember).where(ProjectMember.project_id == project_id)
    stmt = page(base, ProjectMember.user_id, after, limit)
    return split_page(list(session.scalars(stmt)), limit, lambda m: m.user_id)


def add(session: Session, project_id: int, user_id: int) -> ProjectMember:
    member = ProjectMember(project_id=project_id, user_id=user_id)
    session.add(member)
    session.flush()
    return member


def remove(session: Session, member: ProjectMember) -> None:
    session.delete(member)
    session.flush()
