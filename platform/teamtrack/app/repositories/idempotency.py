from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IdempotencyRecord


def get(session: Session, org_id: int, key: str, endpoint: str) -> IdempotencyRecord | None:
    return session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.org_id == org_id,
            IdempotencyRecord.key == key,
            IdempotencyRecord.endpoint == endpoint,
        )
    )


def add(
    session: Session,
    org_id: int,
    key: str,
    endpoint: str,
    request_hash: str,
    status_code: int,
    response_json: str,
) -> IdempotencyRecord:
    record = IdempotencyRecord(
        org_id=org_id,
        key=key,
        endpoint=endpoint,
        request_hash=request_hash,
        status_code=status_code,
        response_json=response_json,
    )
    session.add(record)
    session.flush()
    return record
