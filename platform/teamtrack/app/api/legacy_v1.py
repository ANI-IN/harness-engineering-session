"""LEGACY /v1 API. Do not copy.

This handler predates tenant isolation and is kept only for one old reporting client. It is not
scoped to the caller's organization, uses offset pagination, and returns a bare array instead of
the {items, next_cursor} envelope. New endpoints must follow docs/HANDBOOK.md instead.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import current_actor, get_db
from app.api.schemas import IssueOut
from app.services import legacy
from app.services.context import Actor

router = APIRouter(prefix="/v1", tags=["legacy"])


@router.get("/issues", response_model=list[IssueOut], deprecated=True)
def list_issues_v1(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> list[IssueOut]:
    return [IssueOut.model_validate(row) for row in legacy.list_issues(db, offset, limit)]
