"""Board routes under /board. Session cookie holds the demo token of the selected user."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.deps import Id, get_db
from app.seed import ACME, GLOBEX
from app.services import auth, comments, issues, orgs, projects
from app.services.context import Actor
from app.services.errors import Forbidden, Unauthorized

COOKIE = "tt_session"
STATIC_DIR = Path(__file__).parent / "static"
STATUSES = ("open", "in_progress", "done")
NEXT_STATUS = {"open": ["in_progress"], "in_progress": ["open", "done"], "done": ["open"]}
DEMO_USERS = [
    f"{role}@{org.slug}.test" for org in (ACME, GLOBEX) for role in ("admin", "member", "viewer")
]

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
router = APIRouter(prefix="/board", include_in_schema=False)


def _actor(request: Request, db: Session) -> Actor | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    try:
        return auth.authenticate(db, f"Bearer {token}")
    except Unauthorized:
        return None


def _to_login() -> RedirectResponse:
    return RedirectResponse("/board/login", status_code=303)


def _render(
    request: Request, name: str, actor: Actor | None, db: Session, **context: Any
) -> HTMLResponse:
    slugs = orgs.slugs(db)
    user_org = slugs.get(actor.org_id, "") if actor else ""
    return templates.TemplateResponse(
        request,
        name,
        {
            "actor": actor,
            "slugs": slugs,
            "user_org": user_org,
            "next_status": NEXT_STATUS,
            "user_email": request.cookies.get("tt_email", ""),
            **context,
        },
    )


def _all_issues(db: Session, actor: Actor, project_id: int) -> list[Any]:
    rows, after = issues.list_for_project(db, actor, project_id, None, 100)
    collected = list(rows)
    while after is not None:
        rows, after = issues.list_for_project(db, actor, project_id, after, 100)
        collected.extend(rows)
    return collected


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    return _render(request, "login.html", None, db, demo_users=DEMO_USERS)


@router.post("/login")
def login(email: str = Form(...), db: Session = Depends(get_db)) -> RedirectResponse:
    token, user = auth.login(db, email)
    response = RedirectResponse("/board", status_code=303)
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax")
    response.set_cookie("tt_email", user.email, samesite="lax")
    return response


@router.get("")
def board_index(request: Request, db: Session = Depends(get_db)) -> Response:
    actor = _actor(request, db)
    if actor is None:
        return _to_login()
    rows, _ = projects.list_page(db, actor, None, 1)
    if not rows:
        return _render(request, "board.html", actor, db, project=None, columns={})
    return RedirectResponse(f"/board/projects/{rows[0].id}", status_code=303)


@router.get("/projects/{project_id}")
def project_board(project_id: Id, request: Request, db: Session = Depends(get_db)) -> Response:
    actor = _actor(request, db)
    if actor is None:
        return _to_login()
    project = projects.get(db, actor, project_id)
    all_projects, _ = projects.list_page(db, actor, None, 100)
    columns: dict[str, list[Any]] = {status: [] for status in STATUSES}
    for issue in _all_issues(db, actor, project.id):
        columns.setdefault(issue.status, []).append(issue)
    return _render(
        request, "board.html", actor, db, project=project, projects=all_projects, columns=columns
    )


@router.post("/projects/{project_id}/issues")
def create_issue(
    project_id: Id,
    request: Request,
    title: str = Form(...),
    priority: str = Form("medium"),
    db: Session = Depends(get_db),
) -> Response:
    actor = _actor(request, db)
    if actor is None:
        return _to_login()
    if not actor.can_write:
        raise Forbidden("viewers cannot change data")
    issues.create(db, actor, project_id, title, "", priority, None)
    return RedirectResponse(f"/board/projects/{project_id}", status_code=303)


@router.get("/issues/{issue_id}")
def issue_detail(issue_id: Id, request: Request, db: Session = Depends(get_db)) -> Response:
    actor = _actor(request, db)
    if actor is None:
        return _to_login()
    issue = issues.get(db, actor, issue_id)
    return _render(
        request, "issue.html", actor, db, issue=issue, comments=_all_comments(db, actor, issue.id)
    )


def _all_comments(db: Session, actor: Actor, issue_id: int) -> list[Any]:
    rows, after = comments.list_page(db, actor, issue_id, None, 100)
    collected = list(rows)
    while after is not None:
        rows, after = comments.list_page(db, actor, issue_id, after, 100)
        collected.extend(rows)
    return collected


@router.post("/issues/{issue_id}/comments")
def add_comment(
    issue_id: Id, request: Request, body: str = Form(...), db: Session = Depends(get_db)
) -> Response:
    actor = _actor(request, db)
    if actor is None:
        return _to_login()
    if not actor.can_write:
        raise Forbidden("viewers cannot change data")
    comments.create(db, actor, issue_id, body)
    return RedirectResponse(f"/board/issues/{issue_id}", status_code=303)


@router.post("/issues/{issue_id}/transition")
def transition(
    issue_id: Id, request: Request, status: str = Form(...), db: Session = Depends(get_db)
) -> Response:
    actor = _actor(request, db)
    if actor is None:
        return _to_login()
    if not actor.can_write:
        raise Forbidden("viewers cannot change data")
    issue = issues.transition(db, actor, issue_id, status)
    if request.headers.get("HX-Request"):
        return _render(request, "_card.html", actor, db, issue=issue)
    return RedirectResponse(f"/board/projects/{issue.project_id}", status_code=303)


@router.post("/issues/{issue_id}/edit")
def edit_issue(
    issue_id: Id,
    request: Request,
    title: str = Form(...),
    priority: str = Form("medium"),
    db: Session = Depends(get_db),
) -> Response:
    actor = _actor(request, db)
    if actor is None:
        return _to_login()
    if not actor.can_write:
        raise Forbidden("viewers cannot change data")
    issues.update(db, actor, issue_id, {"title": title, "priority": priority})
    return RedirectResponse(f"/board/issues/{issue_id}", status_code=303)
