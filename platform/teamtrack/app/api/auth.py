from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_actor, get_db
from app.api.schemas import LoginIn, LoginOut, OrgOut, UserOut
from app.services import auth, orgs, users
from app.services.context import Actor

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=LoginOut)
def login(body: LoginIn, db: Session = Depends(get_db)) -> LoginOut:
    token, user = auth.login(db, body.email)
    return LoginOut(token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)) -> UserOut:
    return UserOut.model_validate(users.get(db, actor, actor.user_id))


@router.get("/orgs/current", response_model=OrgOut, tags=["orgs"])
def current_org(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)) -> OrgOut:
    return OrgOut.model_validate(orgs.current(db, actor))
