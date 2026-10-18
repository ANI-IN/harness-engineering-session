from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEntry
from app.repositories.common import page, split_page


def add(
    session: Session, org_id: int, actor_id: int, action: str, entity: str, entity_id: int
) -> AuditEntry:
    entry = AuditEntry(
        org_id=org_id, actor_id=actor_id, action=action, entity=entity, entity_id=entity_id
    )
    session.add(entry)
    session.flush()
    return entry


def list_page(
    session: Session, org_id: int, after: int | None, limit: int
) -> tuple[list[AuditEntry], int | None]:
    stmt = page(select(AuditEntry).where(AuditEntry.org_id == org_id), AuditEntry.id, after, limit)
    return split_page(list(session.scalars(stmt)), limit, lambda a: a.id)
