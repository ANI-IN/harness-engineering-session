"""Comments on issues (F2): create, list oldest first, delete (author or admin)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import Id, current_actor, get_db, require_writer
from app.api.pagination import Page, PageParams, decode_cursor, page_params, to_page
from app.services import comments, idempotency
from app.services.context import Actor

router = APIRouter(tags=["comments"])


class CommentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=5000)


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: int
    issue_id: int
    author_id: int
    body: str
    created_at: datetime


@router.get("/issues/{issue_id}/comments", response_model=Page[CommentOut])
def list_comments(
    issue_id: Id,
    params: PageParams = Depends(page_params),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> Page[CommentOut]:
    rows, next_after = comments.list_page(
        db, actor, issue_id, decode_cursor(params.cursor), params.limit
    )
    return to_page(rows, next_after, CommentOut.model_validate)


@router.post("/issues/{issue_id}/comments", response_model=CommentOut, status_code=201)
def create_comment(
    issue_id: Id,
    body: CommentIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    actor: Actor = Depends(require_writer),
    db: Session = Depends(get_db),
) -> JSONResponse:
    def create() -> dict[str, object]:
        comment = comments.create(db, actor, issue_id, body.body, commit=False)
        return CommentOut.model_validate(comment).model_dump(mode="json")

    endpoint = f"POST /issues/{issue_id}/comments"
    status, payload = idempotency.run_once(
        db, actor, idempotency_key, endpoint, body.model_dump(), create
    )
    return JSONResponse(payload, status_code=status)


@router.delete("/comments/{comment_id}", status_code=204)
def delete_comment(
    comment_id: Id, actor: Actor = Depends(require_writer), db: Session = Depends(get_db)
) -> Response:
    comments.delete(db, actor, comment_id)
    return Response(status_code=204)
