from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import MAX_ID, Id, current_actor, get_db, require_writer
from app.api.pagination import Page, PageParams, decode_cursor, page_params, to_page
from app.api.schemas import (
    AssignIn,
    AuditOut,
    BulkCloseIn,
    BulkCloseOut,
    BulkSkipped,
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
    label_id: int | None = Query(default=None, ge=1, le=MAX_ID),
    params: PageParams = Depends(page_params),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> Page[IssueOut]:
    rows, next_after = issues.list_for_project(
        db, actor, project_id, decode_cursor(params.cursor), params.limit, label_id=label_id
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
    label_id: int | None = Query(default=None, ge=1, le=MAX_ID),
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
        label_id=label_id,
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


@router.post("/projects/{project_id}/issues/bulk-close", response_model=BulkCloseOut)
def bulk_close_issues(
    project_id: Id,
    body: BulkCloseIn,
    actor: Actor = Depends(require_writer),
    db: Session = Depends(get_db),
) -> BulkCloseOut:
    """Close in-progress issues of one project in one atomic request."""
    closed, skipped = issues.bulk_close(db, actor, project_id, body.issue_ids)
    return BulkCloseOut(
        closed=closed, skipped=[BulkSkipped(id=i, reason=reason) for i, reason in skipped]
    )


# Optimistic concurrency (F4): a write may name the version it was based on.
PRECONDITION_RESPONSES: dict[int | str, dict[str, Any]] = {
    412: {"description": "Precondition failed: If-Match does not name the current version"},
}


def if_match_version(
    issue_id: Id,
    if_match: str | None = Header(
        default=None,
        alias="If-Match",
        description='Optional. The ETag from GET /issues/{issue_id}, for example "3"',
    ),
    actor: Actor = Depends(require_writer),
    db: Session = Depends(get_db),
) -> int | None:
    """Runs before the body is validated: 401, 403, 404, then 412, then 422. Without If-Match
    the write is not conditional (None)."""
    return issues.check_if_match(db, actor, issue_id, if_match)


def _with_etag(response: Response, issue: Any) -> IssueOut:
    response.headers["ETag"] = issues.etag(issue)
    return IssueOut.model_validate(issue)


@router.get("/issues/{issue_id}", response_model=IssueOut)
def get_issue(
    issue_id: Id,
    response: Response,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> IssueOut:
    return _with_etag(response, issues.get(db, actor, issue_id))


@router.patch("/issues/{issue_id}", response_model=IssueOut, responses=PRECONDITION_RESPONSES)
def update_issue(
    issue_id: Id,
    body: IssuePatch,
    response: Response,
    version: int | None = Depends(if_match_version),
    actor: Actor = Depends(require_writer),
    db: Session = Depends(get_db),
) -> IssueOut:
    issue = issues.update(db, actor, issue_id, body.model_dump(), expected_version=version)
    return _with_etag(response, issue)


@router.post("/issues/{issue_id}/assign", response_model=IssueOut, responses=PRECONDITION_RESPONSES)
def assign_issue(
    issue_id: Id,
    body: AssignIn,
    response: Response,
    version: int | None = Depends(if_match_version),
    actor: Actor = Depends(require_writer),
    db: Session = Depends(get_db),
) -> IssueOut:
    issue = issues.assign(db, actor, issue_id, body.assignee_id, expected_version=version)
    return _with_etag(response, issue)


@router.post(
    "/issues/{issue_id}/transition", response_model=IssueOut, responses=PRECONDITION_RESPONSES
)
def transition_issue(
    issue_id: Id,
    body: TransitionIn,
    response: Response,
    version: int | None = Depends(if_match_version),
    actor: Actor = Depends(require_writer),
    db: Session = Depends(get_db),
) -> IssueOut:
    issue = issues.transition(db, actor, issue_id, body.status, expected_version=version)
    return _with_etag(response, issue)


@router.get("/issues/{issue_id}/history", response_model=Page[AuditOut])
def issue_history(
    issue_id: Id,
    params: PageParams = Depends(page_params),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> Page[AuditOut]:
    """The issue's audit entries, oldest first."""
    rows, next_after = issues.history(
        db, actor, issue_id, decode_cursor(params.cursor), params.limit
    )
    return to_page(rows, next_after, AuditOut.model_validate)


@router.delete("/issues/{issue_id}", status_code=204)
def delete_issue(
    issue_id: Id, actor: Actor = Depends(require_writer), db: Session = Depends(get_db)
) -> Response:
    issues.delete(db, actor, issue_id)
    return Response(status_code=204)
