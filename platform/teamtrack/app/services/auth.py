"""Demo authentication: a token is `tt-<user id>`. For local demos only; not secure."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import User
from app.repositories import users as users_repo
from app.services.context import Actor
from app.services.errors import Unauthorized

TOKEN_PREFIX = "tt-"


def token_for(user: User) -> str:
    return f"{TOKEN_PREFIX}{user.id}"


def login(session: Session, email: str) -> tuple[str, User]:
    user = users_repo.get_by_email(session, email.strip().lower())
    if user is None:
        raise Unauthorized("unknown email")
    return token_for(user), user


def authenticate(session: Session, authorization: str | None) -> Actor:
    if not authorization or not authorization.startswith("Bearer "):
        raise Unauthorized("missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    raw_id = token.removeprefix(TOKEN_PREFIX) if token.startswith(TOKEN_PREFIX) else ""
    if not raw_id.isdigit():
        raise Unauthorized("invalid token")
    user = users_repo.get_any(session, int(raw_id))
    if user is None:
        raise Unauthorized("invalid token")
    return Actor(user_id=user.id, org_id=user.org_id, role=user.role)
