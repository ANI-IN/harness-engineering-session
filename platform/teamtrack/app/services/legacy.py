"""LEGACY service for /v1/issues. Kept for an old client; scheduled for removal.

Do not copy this pattern: it is not scoped to the caller's organization (see docs/HANDBOOK.md,
"Legacy /v1 API").
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Issue
from app.repositories import issues as issues_repo


def list_issues(session: Session, offset: int, limit: int) -> list[Issue]:
    return issues_repo.list_all_legacy(session, offset, limit)
