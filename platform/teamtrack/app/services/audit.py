from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AuditEntry
from app.repositories import audit as audit_repo
from app.services.context import Actor


def record(session: Session, actor: Actor, action: str, entity: str, entity_id: int) -> None:
    """Every write adds exactly one audit row (house rule R5)."""
    audit_repo.add(session, actor.org_id, actor.user_id, action, entity, entity_id)


def list_page(
    session: Session, actor: Actor, after: int | None, limit: int
) -> tuple[list[AuditEntry], int | None]:
    return audit_repo.list_page(session, actor.org_id, after, limit)
