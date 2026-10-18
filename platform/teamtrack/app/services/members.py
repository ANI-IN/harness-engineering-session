from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import ProjectMember
from app.repositories import members as members_repo
from app.repositories import users as users_repo
from app.services import audit, projects
from app.services.context import Actor
from app.services.errors import Conflict, Invalid, NotFound


def list_page(
    session: Session, actor: Actor, project_id: int, after: int | None, limit: int
) -> tuple[list[ProjectMember], int | None]:
    project = projects.get(session, actor, project_id)
    return members_repo.list_page(session, project.id, after, limit)


def add(session: Session, actor: Actor, project_id: int, user_id: int) -> ProjectMember:
    project = projects.get(session, actor, project_id)
    if users_repo.get(session, actor.org_id, user_id) is None:
        raise Invalid("user must belong to your organization", code="invalid_user")
    if members_repo.get(session, project.id, user_id) is not None:
        raise Conflict("user is already a member of this project")
    member = members_repo.add(session, project.id, user_id)
    audit.record(session, actor, "member.add", "project", project.id)
    session.commit()
    return member


def remove(session: Session, actor: Actor, project_id: int, user_id: int) -> None:
    project = projects.get(session, actor, project_id)
    member = members_repo.get(session, project.id, user_id)
    if member is None:
        raise NotFound("membership not found")
    members_repo.remove(session, member)
    audit.record(session, actor, "member.remove", "project", project.id)
    session.commit()
