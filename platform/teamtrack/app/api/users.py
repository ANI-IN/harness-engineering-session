from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import Id, current_actor, get_db, require_admin
from app.api.pagination import Page, PageParams, decode_cursor, page_params, to_page
from app.api.schemas import UserCreate, UserOut, UserPatch
from app.services import idempotency, users
from app.services.context import Actor

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=Page[UserOut])
def list_users(
    params: PageParams = Depends(page_params),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> Page[UserOut]:
    rows, next_after = users.list_page(db, actor, decode_cursor(params.cursor), params.limit)
    return to_page(rows, next_after, UserOut.model_validate)


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    body: UserCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    actor: Actor = Depends(require_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    def create() -> dict[str, object]:
        user = users.create(db, actor, body.email, body.name, body.role, commit=False)
        return UserOut.model_validate(user).model_dump(mode="json")

    status, payload = idempotency.run_once(
        db, actor, idempotency_key, "POST /users", body.model_dump(), create
    )
    return JSONResponse(payload, status_code=status)


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: Id, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)
) -> UserOut:
    return UserOut.model_validate(users.get(db, actor, user_id))


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: Id,
    body: UserPatch,
    actor: Actor = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    return UserOut.model_validate(users.update(db, actor, user_id, body.model_dump()))
