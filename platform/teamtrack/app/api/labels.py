"""Labels (F7): manage the org's labels and put them on issues."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import MAX_ID, Id, current_actor, get_db, require_writer
from app.api.pagination import Page, PageParams, decode_cursor, page_params, to_page
from app.api.schemas import IssueOut
from app.services import idempotency, labels
from app.services.context import Actor

router = APIRouter(tags=["labels"])
COLOR_PATTERN = r"^#[0-9a-fA-F]{6}$"


class LabelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=50)
    color: str = Field(pattern=COLOR_PATTERN)


class LabelPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=50)
    color: str | None = Field(default=None, pattern=COLOR_PATTERN)


class LabelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: int
    name: str
    color: str


class IssueLabelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label_id: int = Field(ge=1, le=MAX_ID)


@router.get("/labels", response_model=Page[LabelOut])
def list_labels(
    params: PageParams = Depends(page_params),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> Page[LabelOut]:
    rows, next_after = labels.list_page(db, actor, decode_cursor(params.cursor), params.limit)
    return to_page(rows, next_after, LabelOut.model_validate)


@router.post("/labels", response_model=LabelOut, status_code=201)
def create_label(
    body: LabelIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    actor: Actor = Depends(require_writer),
    db: Session = Depends(get_db),
) -> JSONResponse:
    def create() -> dict[str, object]:
        label = labels.create(db, actor, body.name, body.color, commit=False)
        return LabelOut.model_validate(label).model_dump(mode="json")

    status, payload = idempotency.run_once(
        db, actor, idempotency_key, "POST /labels", body.model_dump(), create
    )
    return JSONResponse(payload, status_code=status)


@router.patch("/labels/{label_id}", response_model=LabelOut)
def update_label(
    label_id: Id,
    body: LabelPatch,
    actor: Actor = Depends(require_writer),
    db: Session = Depends(get_db),
) -> LabelOut:
    return LabelOut.model_validate(labels.update(db, actor, label_id, body.model_dump()))


@router.delete("/labels/{label_id}", status_code=204)
def delete_label(
    label_id: Id, actor: Actor = Depends(require_writer), db: Session = Depends(get_db)
) -> Response:
    labels.delete(db, actor, label_id)
    return Response(status_code=204)


@router.post("/issues/{issue_id}/labels", response_model=IssueOut)
def add_issue_label(
    issue_id: Id,
    body: IssueLabelIn,
    actor: Actor = Depends(require_writer),
    db: Session = Depends(get_db),
) -> IssueOut:
    return IssueOut.model_validate(labels.attach(db, actor, issue_id, body.label_id))


@router.delete("/issues/{issue_id}/labels/{label_id}", status_code=204)
def remove_issue_label(
    issue_id: Id,
    label_id: Id,
    actor: Actor = Depends(require_writer),
    db: Session = Depends(get_db),
) -> Response:
    labels.detach(db, actor, issue_id, label_id)
    return Response(status_code=204)
