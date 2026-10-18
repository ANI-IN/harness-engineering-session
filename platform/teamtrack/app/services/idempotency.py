"""Idempotent creates (house rule R4): the same Idempotency-Key returns the first response."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.repositories import idempotency as idempotency_repo
from app.services.context import Actor
from app.services.errors import Conflict


def request_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def run_once(
    session: Session,
    actor: Actor,
    key: str | None,
    endpoint: str,
    payload: dict[str, Any],
    create: Callable[[], dict[str, Any]],
    status_code: int = 201,
) -> tuple[int, dict[str, Any]]:
    """Run `create` at most once per (org, key, endpoint).

    `create` performs the write without committing and returns the response body. A repeated key
    with the same payload returns the stored response; a different payload is a conflict.
    """
    if not key:
        body = create()
        session.commit()
        return status_code, body
    digest = request_hash(payload)
    existing = idempotency_repo.get(session, actor.org_id, key, endpoint)
    if existing is not None:
        if existing.request_hash != digest:
            raise Conflict(
                "Idempotency-Key was already used with a different request body",
                code="idempotency_conflict",
            )
        return existing.status_code, json.loads(existing.response_json)
    body = create()
    idempotency_repo.add(
        session, actor.org_id, key, endpoint, digest, status_code, json.dumps(body, default=str)
    )
    session.commit()
    return status_code, body
