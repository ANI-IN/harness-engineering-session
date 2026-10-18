from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User
from app.repositories.common import page, split_page


def get_any(session: Session, user_id: int) -> User | None:
    """Unscoped lookup, used only to resolve an auth token to its user."""
    return session.get(User, user_id)


def get(session: Session, org_id: int, user_id: int) -> User | None:
    return session.scalar(select(User).where(User.org_id == org_id, User.id == user_id))


def get_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email))


def list_page(
    session: Session, org_id: int, after: int | None, limit: int
) -> tuple[list[User], int | None]:
    stmt = page(select(User).where(User.org_id == org_id), User.id, after, limit)
    return split_page(list(session.scalars(stmt)), limit, lambda u: u.id)


def add(session: Session, org_id: int, email: str, name: str, role: str) -> User:
    user = User(org_id=org_id, email=email, name=name, role=role)
    session.add(user)
    session.flush()
    return user
