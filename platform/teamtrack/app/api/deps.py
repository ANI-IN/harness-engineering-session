"""Request dependencies: database session, the authenticated actor, role checks."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Path, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.services import auth
from app.services.context import Actor
from app.services.errors import Forbidden

# Path ids must fit SQLite INTEGER; larger values are a 422 validation error, never a 500.
MAX_ID = 2**63 - 1
Id = Annotated[int, Path(ge=1, le=MAX_ID)]

_bearer = HTTPBearer(auto_error=False, description="Demo token from POST /auth/login")


def get_db(request: Request) -> Iterator[Session]:
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def current_actor(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Actor:
    header = f"Bearer {credentials.credentials}" if credentials else None
    return auth.authenticate(db, header)


def require_writer(actor: Actor = Depends(current_actor)) -> Actor:
    if not actor.can_write:
        raise Forbidden("viewers cannot change data")
    return actor


def require_admin(actor: Actor = Depends(current_actor)) -> Actor:
    if not actor.is_admin:
        raise Forbidden("admin role required")
    return actor
