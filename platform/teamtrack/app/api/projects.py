from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import Id, current_actor, get_db, require_admin, require_writer
from app.api.pagination import Page, PageParams, decode_cursor, page_params, to_page
from app.api.schemas import ProjectCreate, ProjectOut, ProjectPatch
from app.services import idempotency, projects
from app.services.context import Actor

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=Page[ProjectOut])
def list_projects(
    params: PageParams = Depends(page_params),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> Page[ProjectOut]:
    rows, next_after = projects.list_page(db, actor, decode_cursor(params.cursor), params.limit)
    return to_page(rows, next_after, ProjectOut.model_validate)


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    body: ProjectCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    actor: Actor = Depends(require_writer),
    db: Session = Depends(get_db),
) -> JSONResponse:
    def create() -> dict[str, object]:
        project = projects.create(db, actor, body.name, body.key, commit=False)
        return ProjectOut.model_validate(project).model_dump(mode="json")

    status, payload = idempotency.run_once(
        db, actor, idempotency_key, "POST /projects", body.model_dump(), create
    )
    return JSONResponse(payload, status_code=status)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: Id, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)
) -> ProjectOut:
    return ProjectOut.model_validate(projects.get(db, actor, project_id))


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: Id,
    body: ProjectPatch,
    actor: Actor = Depends(require_writer),
    db: Session = Depends(get_db),
) -> ProjectOut:
    return ProjectOut.model_validate(projects.update(db, actor, project_id, body.model_dump()))


@router.delete("/{project_id}", status_code=204)
def archive_project(
    project_id: Id, actor: Actor = Depends(require_admin), db: Session = Depends(get_db)
) -> Response:
    projects.archive(db, actor, project_id)
    return Response(status_code=204)
