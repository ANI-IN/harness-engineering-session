"""Issue watchers (F6): watch and unwatch, list an issue's watchers, list what I watch."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import Id, current_actor, get_db, require_admin, require_writer
from app.api.pagination import Page, PageParams, decode_cursor, page_params, to_page
from app.api.schemas import IssueOut
from app.services import watchers
from app.services.context import Actor

router = APIRouter(tags=["watchers"])


class WatcherOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    created_at: datetime


@router.get("/issues/{issue_id}/watchers", response_model=Page[WatcherOut])
def list_watchers(
    issue_id: Id,
    params: PageParams = Depends(page_params),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> Page[WatcherOut]:
    rows, next_after = watchers.list_page(
        db, actor, issue_id, decode_cursor(params.cursor), params.limit
    )
    return to_page(rows, next_after, WatcherOut.model_validate)


@router.put("/issues/{issue_id}/watchers/me", status_code=204)
def watch_issue(
    issue_id: Id, actor: Actor = Depends(require_writer), db: Session = Depends(get_db)
) -> Response:
    watchers.watch(db, actor, issue_id)
    return Response(status_code=204)


@router.delete("/issues/{issue_id}/watchers/me", status_code=204)
def unwatch_issue(
    issue_id: Id, actor: Actor = Depends(require_writer), db: Session = Depends(get_db)
) -> Response:
    watchers.unwatch(db, actor, issue_id)
    return Response(status_code=204)


@router.put("/issues/{issue_id}/watchers/{user_id}", status_code=204)
def add_watcher(
    issue_id: Id,
    user_id: Id,
    actor: Actor = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    watchers.watch(db, actor, issue_id, user_id)
    return Response(status_code=204)


@router.delete("/issues/{issue_id}/watchers/{user_id}", status_code=204)
def remove_watcher(
    issue_id: Id,
    user_id: Id,
    actor: Actor = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    watchers.unwatch(db, actor, issue_id, user_id)
    return Response(status_code=204)


@router.get("/me/watching", response_model=Page[IssueOut])
def my_watched_issues(
    params: PageParams = Depends(page_params),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> Page[IssueOut]:
    rows, next_after = watchers.watching(db, actor, decode_cursor(params.cursor), params.limit)
    return to_page(rows, next_after, IssueOut.model_validate)
