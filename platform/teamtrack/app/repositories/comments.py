from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Comment
from app.repositories.common import page, split_page


def get(session: Session, org_id: int, comment_id: int) -> Comment | None:
    return session.scalar(select(Comment).where(Comment.org_id == org_id, Comment.id == comment_id))


def list_for_issue(
    session: Session, org_id: int, issue_id: int, after: int | None, limit: int
) -> tuple[list[Comment], int | None]:
    """Comments of one issue, oldest first (ascending id)."""
    base = select(Comment).where(Comment.org_id == org_id, Comment.issue_id == issue_id)
    stmt = page(base, Comment.id, after, limit)
    return split_page(list(session.scalars(stmt)), limit, lambda c: c.id)


def add(session: Session, org_id: int, issue_id: int, author_id: int, body: str) -> Comment:
    comment = Comment(org_id=org_id, issue_id=issue_id, author_id=author_id, body=body)
    session.add(comment)
    session.flush()
    return comment


def remove(session: Session, comment: Comment) -> None:
    session.delete(comment)
    session.flush()
