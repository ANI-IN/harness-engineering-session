from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import Project
from app.repositories import members as members_repo
from app.repositories import projects as projects_repo
from app.services import audit
from app.services.context import Actor
from app.services.errors import Conflict, NotFound


def get(session: Session, actor: Actor, project_id: int) -> Project:
    project = projects_repo.get(session, actor.org_id, project_id)
    if project is None:
        raise NotFound("project not found")
    return project


def list_page(
    session: Session, actor: Actor, after: int | None, limit: int
) -> tuple[list[Project], int | None]:
    return projects_repo.list_page(session, actor.org_id, after, limit)


def create(session: Session, actor: Actor, name: str, key: str, *, commit: bool = True) -> Project:
    if projects_repo.get_by_key(session, actor.org_id, key) is not None:
        raise Conflict(f"project key {key} is already used in this organization")
    project = projects_repo.add(session, actor.org_id, name, key)
    members_repo.add(session, project.id, actor.user_id)
    audit.record(session, actor, "project.create", "project", project.id)
    if commit:
        session.commit()
    return project


def update(session: Session, actor: Actor, project_id: int, changes: dict[str, object]) -> Project:
    project = get(session, actor, project_id)
    if changes.get("name") is not None:
        project.name = str(changes["name"])
    audit.record(session, actor, "project.update", "project", project.id)
    session.commit()
    return project


def archive(session: Session, actor: Actor, project_id: int) -> None:
    project = get(session, actor, project_id)
    project.archived_at = utcnow()
    audit.record(session, actor, "project.archive", "project", project.id)
    session.commit()
