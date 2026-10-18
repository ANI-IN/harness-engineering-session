"""Labels (F7): org-wide labels and the labels on each issue."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.db.models import Issue, Label
from app.repositories import issues as issues_repo
from app.repositories import labels as labels_repo
from app.repositories import projects as projects_repo
from app.services import audit
from app.services.context import Actor
from app.services.errors import Conflict, Invalid, NotFound

COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def get(session: Session, actor: Actor, label_id: int) -> Label:
    label = labels_repo.get(session, actor.org_id, label_id)
    if label is None:
        raise NotFound("label not found")
    return label


def _issue(session: Session, actor: Actor, issue_id: int) -> Issue:
    """A live issue in an active project of the caller's org; anything else is a 404."""
    issue = issues_repo.get(session, actor.org_id, issue_id)
    if issue is None or projects_repo.get(session, actor.org_id, issue.project_id) is None:
        raise NotFound("issue not found")
    return issue


def _validate(name: object = None, color: object = None) -> None:
    if name is not None and not (isinstance(name, str) and 1 <= len(name) <= 50):
        raise Invalid("name must be 1 to 50 characters")
    if color is not None and not (isinstance(color, str) and COLOR.match(color)):
        raise Invalid("color must look like #rrggbb")


def _check_unique(session: Session, actor: Actor, name: str, label_id: int | None = None) -> None:
    existing = labels_repo.get_by_name(session, actor.org_id, name)
    if existing is not None and existing.id != label_id:
        raise Conflict(f"a label named {name!r} already exists", code="label_exists")


def list_page(
    session: Session, actor: Actor, after: int | None, limit: int
) -> tuple[list[Label], int | None]:
    return labels_repo.list_page(session, actor.org_id, after, limit)


def create(session: Session, actor: Actor, name: str, color: str, *, commit: bool = True) -> Label:
    _validate(name, color)
    _check_unique(session, actor, name)
    label = labels_repo.add(session, actor.org_id, name, color)
    audit.record(session, actor, "label.create", "label", label.id)
    if commit:
        session.commit()
    return label


def update(session: Session, actor: Actor, label_id: int, changes: dict[str, object]) -> Label:
    label = get(session, actor, label_id)
    _validate(changes.get("name"), changes.get("color"))
    if changes.get("name") is not None:
        _check_unique(session, actor, str(changes["name"]), label.id)
        label.name = str(changes["name"])
    if changes.get("color") is not None:
        label.color = str(changes["color"])
    audit.record(session, actor, "label.update", "label", label.id)
    session.commit()
    return label


def delete(session: Session, actor: Actor, label_id: int) -> None:
    label = get(session, actor, label_id)
    audit.record(session, actor, "label.delete", "label", label.id)
    labels_repo.remove(session, label)
    session.commit()


def attach(session: Session, actor: Actor, issue_id: int, label_id: int) -> Issue:
    """Put a label on an issue. A label the issue already has changes nothing."""
    issue = _issue(session, actor, issue_id)
    label = get(session, actor, label_id)
    if label in issue.labels:
        return issue
    issue.labels.append(label)
    audit.record(session, actor, "issue.label_add", "issue", issue.id)
    session.commit()
    return issue


def detach(session: Session, actor: Actor, issue_id: int, label_id: int) -> None:
    issue = _issue(session, actor, issue_id)
    label = get(session, actor, label_id)
    if label not in issue.labels:
        raise NotFound("the issue does not have this label")
    issue.labels.remove(label)
    audit.record(session, actor, "issue.label_remove", "issue", issue.id)
    session.commit()
