from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import MAX_ID, Id, current_actor, get_db, require_writer
from app.api.pagination import Page, PageParams, decode_cursor, page_params, to_page
from app.api.schemas import (
    AssignIn,
    IssueCreate,
    IssueOut,
    IssuePatch,
    Priority,
    Status,
    TransitionIn,
)
from app.services import idempotency, issues
from app.services.context import Actor

router = APIRouter(tags=["issues"])


@router.get("/projects/{project_id}/issues", response_model=Page[IssueOut])
def list_project_issues(
    project_id: Id,
    params: PageParams = Depends(page_params),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> Page[IssueOut]:
    rows, next_after = issues.list_for_project(
        db, actor, project_id, decode_cursor(params.cursor), params.limit
    )
    return to_page(rows, next_after, IssueOut.model_validate)


@router.get("/issues", response_model=Page[IssueOut])
def search_issues(
    status: Status | None = Query(default=None),
    priority: Priority | None = Query(default=None),
    assignee_id: int | None = Query(default=None, ge=1, le=MAX_ID),
    project_id: int | None = Query(default=None, ge=1, le=MAX_ID),
    q: str | None = Query(
        default=None, min_length=1, max_length=100, description="Substring of the title."
    ),
    params: PageParams = Depends(page_params),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> Page[IssueOut]:
    """Issues of the caller's org across its projects; every filter is optional (AND)."""
    rows, next_after = issues.search(
        db,
        actor,
        status=status,
        priority=priority,
        assignee_id=assignee_id,
        project_id=project_id,
        q=q,
        after=decode_cursor(params.cursor),
        limit=params.limit,
    )
    return to_page(rows, next_after, IssueOut.model_validate)


@router.post("/projects/{project_id}/issues", response_model=IssueOut, status_code=201)
def create_issue(
    project_id: Id,
    body: IssueCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    actor: Actor = Depends(require_writer),
    db: Session = Depends(get_db),
) -> JSONResponse:
    def create() -> dict[str, object]:
        issue = issues.create(
            db,
            actor,
            project_id,
            body.title,
            body.description,
            body.priority,
            body.assignee_id,
            commit=False,
        )
        return IssueOut.model_validate(issue).model_dump(mode="json")

    # Keys are scoped per org and per request path, so each project has its own key space.
    endpoint = f"POST /projects/{project_id}/issues"
    status, payload = idempotency.run_once(
        db, actor, idempotency_key, endpoint, body.model_dump(), create
    )
    return JSONResponse(payload, status_code=status)


@router.get("/issues/{issue_id}", response_model=IssueOut)
def get_issue(
    issue_id: Id, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)
) -> IssueOut:
    return IssueOut.model_validate(issues.get(db, actor, issue_id))


@router.patch("/issues/{issue_id}", response_model=IssueOut)
def update_issue(
    issue_id: Id,
    body: IssuePatch,
    actor: Actor = Depends(require_writer),
    db: Session = Depends(get_db),
) -> IssueOut:
    return IssueOut.model_validate(issues.update(db, actor, issue_id, body.model_dump()))


@router.post("/issues/{issue_id}/assign", response_model=IssueOut)
def assign_issue(
    issue_id: Id,
    body: AssignIn,
    actor: Actor = Depends(require_writer),
    db: Session = Depends(get_db),
) -> IssueOut:
    return IssueOut.model_validate(issues.assign(db, actor, issue_id, body.assignee_id))


@router.post("/issues/{issue_id}/transition", response_model=IssueOut)
def transition_issue(
    issue_id: Id,
    body: TransitionIn,
    actor: Actor = Depends(require_writer),
    db: Session = Depends(get_db),
) -> IssueOut:
    return IssueOut.model_validate(issues.transition(db, actor, issue_id, body.status))


@router.delete("/issues/{issue_id}", status_code=204)
def delete_issue(
    issue_id: Id, actor: Actor = Depends(require_writer), db: Session = Depends(get_db)
) -> Response:
    issues.delete(db, actor, issue_id)
    return Response(status_code=204)
