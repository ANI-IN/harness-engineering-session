from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import Id, current_actor, get_db, require_admin
from app.api.pagination import Page, PageParams, decode_cursor, page_params, to_page
from app.api.schemas import MemberAdd, MemberOut
from app.services import members
from app.services.context import Actor

router = APIRouter(prefix="/projects/{project_id}/members", tags=["members"])


@router.get("", response_model=Page[MemberOut])
def list_members(
    project_id: Id,
    params: PageParams = Depends(page_params),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> Page[MemberOut]:
    rows, next_after = members.list_page(
        db, actor, project_id, decode_cursor(params.cursor), params.limit
    )
    return to_page(rows, next_after, MemberOut.model_validate)


@router.post("", response_model=MemberOut, status_code=201)
def add_member(
    project_id: Id,
    body: MemberAdd,
    actor: Actor = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MemberOut:
    return MemberOut.model_validate(members.add(db, actor, project_id, body.user_id))


@router.delete("/{user_id}", status_code=204)
def remove_member(
    project_id: Id,
    user_id: Id,
    actor: Actor = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    members.remove(db, actor, project_id, user_id)
    return Response(status_code=204)
