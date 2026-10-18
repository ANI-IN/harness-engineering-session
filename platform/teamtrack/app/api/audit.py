from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.api.pagination import Page, PageParams, decode_cursor, page_params, to_page
from app.api.schemas import AuditOut
from app.services import audit
from app.services.context import Actor

router = APIRouter(tags=["audit"])


@router.get("/audit", response_model=Page[AuditOut])
def list_audit(
    params: PageParams = Depends(page_params),
    actor: Actor = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Page[AuditOut]:
    rows, next_after = audit.list_page(db, actor, decode_cursor(params.cursor), params.limit)
    return to_page(rows, next_after, AuditOut.model_validate)
