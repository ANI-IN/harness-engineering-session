from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Org
from app.repositories import orgs as orgs_repo
from app.services.context import Actor
from app.services.errors import NotFound


def slugs(session: Session) -> dict[int, str]:
    """Org id -> slug for every org. Used only to label tenant badges on the board."""
    return {org.id: org.slug for org in orgs_repo.list_all(session)}


def current(session: Session, actor: Actor) -> Org:
    org = orgs_repo.get(session, actor.org_id)
    if org is None:
        raise NotFound("organization not found")
    return org
