from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import User
from app.repositories import users as users_repo
from app.services import audit
from app.services.context import Actor
from app.services.errors import Conflict, NotFound


def get(session: Session, actor: Actor, user_id: int) -> User:
    user = users_repo.get(session, actor.org_id, user_id)
    if user is None:
        raise NotFound("user not found")
    return user


def list_page(
    session: Session, actor: Actor, after: int | None, limit: int
) -> tuple[list[User], int | None]:
    return users_repo.list_page(session, actor.org_id, after, limit)


def create(
    session: Session, actor: Actor, email: str, name: str, role: str, *, commit: bool = True
) -> User:
    email = email.strip().lower()
    if users_repo.get_by_email(session, email) is not None:
        raise Conflict("a user with this email already exists")
    user = users_repo.add(session, actor.org_id, email, name, role)
    audit.record(session, actor, "user.create", "user", user.id)
    if commit:
        session.commit()
    return user


def update(session: Session, actor: Actor, user_id: int, changes: dict[str, object]) -> User:
    user = get(session, actor, user_id)
    for field in ("name", "role"):
        if changes.get(field) is not None:
            setattr(user, field, changes[field])
    audit.record(session, actor, "user.update", "user", user.id)
    session.commit()
    return user
