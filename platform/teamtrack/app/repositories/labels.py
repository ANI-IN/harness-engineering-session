from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import IssueLabel, Label
from app.repositories.common import page, split_page


def get(session: Session, org_id: int, label_id: int) -> Label | None:
    return session.scalar(select(Label).where(Label.org_id == org_id, Label.id == label_id))


def get_by_name(session: Session, org_id: int, name: str) -> Label | None:
    """Case-insensitive lookup: label names are unique per org regardless of case."""
    return session.scalar(
        select(Label).where(Label.org_id == org_id, func.lower(Label.name) == name.lower())
    )


def list_page(
    session: Session, org_id: int, after: int | None, limit: int
) -> tuple[list[Label], int | None]:
    stmt = page(select(Label).where(Label.org_id == org_id), Label.id, after, limit)
    return split_page(list(session.scalars(stmt)), limit, lambda label: label.id)


def add(session: Session, org_id: int, name: str, color: str) -> Label:
    label = Label(org_id=org_id, name=name, color=color)
    session.add(label)
    session.flush()
    return label


def remove(session: Session, label: Label) -> None:
    """Delete a label and take it off every issue."""
    session.execute(delete(IssueLabel).where(IssueLabel.label_id == label.id))
    session.delete(label)
    session.flush()


def link(session: Session, issue_id: int, label_id: int) -> None:
    """Put a label on an issue (seed data; services use Issue.labels)."""
    session.add(IssueLabel(issue_id=issue_id, label_id=label_id))
    session.flush()
