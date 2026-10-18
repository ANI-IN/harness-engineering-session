"""Seeded violations: small edits to a TeamTrack copy that break exactly one house rule each."""

from __future__ import annotations

import shutil
from pathlib import Path

from shipharness.layout import find_repo_root

REPO = find_repo_root(Path(__file__))
TEAMTRACK = REPO / "platform" / "teamtrack"
_IGNORE = shutil.ignore_patterns("__pycache__", "*.db", ".referee", ".pytest_cache")


def _ignore(directory: str, names: list[str]) -> set[str]:
    """Like an arm or referee build: no hidden tests and no reference code (each test adds the
    hidden tests it needs)."""
    skipped = set(_IGNORE(directory, names))
    here = Path(directory).resolve()
    if here == TEAMTRACK.resolve():
        skipped |= {"reference"} & set(names)
    elif here == (TEAMTRACK / "tests").resolve():
        skipped |= {"hidden"} & set(names)
    return skipped


def copy_teamtrack(dest: Path) -> Path:
    shutil.copytree(TEAMTRACK, dest, ignore=_ignore)
    return dest


def edit(build: Path, relative: str, old: str, new: str) -> None:
    """Replace one exact snippet in a build file; fails loudly if the snippet moved."""
    path = build / relative
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{old!r} not found exactly once in {relative}"
    path.write_text(text.replace(old, new), encoding="utf-8")


LEAKY_ROUTER = """\
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services import legacy

router = APIRouter(tags=["leaky"])


@router.get("/issues/{issue_id}/raw")
def raw_issue(issue_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    for row in legacy.list_issues(db, 0, 500):
        if row.id == issue_id:
            return {"id": row.id, "org_id": row.org_id, "title": row.title}
    return {}
"""


def add_router(build: Path, module: str, source: str) -> None:
    (build / "app" / "api" / f"{module}.py").write_text(source, encoding="utf-8")
    edit(
        build,
        "app/main.py",
        "from app.api import audit, auth, health, issues, legacy_v1, members, projects, users",
        f"from app.api import audit, auth, health, issues, legacy_v1, members, projects, users\n"
        f"from app.api import {module}",
    )
    edit(
        build,
        "app/main.py",
        "    app.include_router(board.router)",
        f"    app.include_router({module}.router)\n    app.include_router(board.router)",
    )


def r1_unauthenticated_leak(build: Path) -> Path:
    """An agent-added endpoint with no authentication and no tenant filter."""
    add_router(build, "leaky", LEAKY_ROUTER)
    return build


def r2_viewers_can_write(build: Path) -> Path:
    edit(build, "app/api/deps.py", "    if not actor.can_write:", "    if False:")
    return build


def r3_bad_error_envelope(build: Path) -> Path:
    edit(
        build,
        "app/api/errors.py",
        'content={"error": {"code": code, "message": message}}',
        'content={"detail": message}',
    )
    return build


BARE_LIST_ROUTER = """\
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import current_actor, get_db
from app.api.schemas import ProjectOut
from app.services import projects
from app.services.context import Actor

router = APIRouter(tags=["archive"])


@router.get("/projects-archive", response_model=list[ProjectOut])
def list_archive(
    offset: int = Query(default=0, ge=0),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> list[ProjectOut]:
    rows, _ = projects.list_page(db, actor, None, 100)
    return [ProjectOut.model_validate(r) for r in rows][offset:]
"""


def r3_bare_list(build: Path) -> Path:
    """A new list endpoint copying the legacy pattern: bare array and offset pagination."""
    add_router(build, "archive", BARE_LIST_ROUTER)
    return build


def r4_no_idempotency_on_projects(build: Path) -> Path:
    edit(
        build,
        "app/api/projects.py",
        "    status, payload = idempotency.run_once(\n"
        '        db, actor, idempotency_key, "POST /projects", body.model_dump(), create\n'
        "    )",
        "    status, payload = idempotency.run_once(\n"
        '        db, actor, None, "POST /projects", body.model_dump(), create\n'
        "    )",
    )
    return build


def r5_no_audit(build: Path) -> Path:
    edit(
        build,
        "app/services/audit.py",
        "    audit_repo.add(session, actor.org_id, actor.user_id, action, entity, entity_id)",
        "    return None",
    )
    return build


def r6_api_imports_db(build: Path) -> Path:
    edit(
        build,
        "app/api/health.py",
        "from __future__ import annotations\n",
        "from __future__ import annotations\n\nfrom app.db import models  # noqa: F401\n",
    )
    return build


MIGRATION = '''\
"""{doc}"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "{rev}"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
{body}


def downgrade() -> None:
    pass
'''


def add_migration(build: Path, rev: str, body: str) -> None:
    text = MIGRATION.format(doc=f"seeded {rev}", rev=rev, body=body)
    (build / "migrations" / "versions" / f"{rev}.py").write_text(text, encoding="utf-8")


def r7_two_heads(build: Path) -> Path:
    create = '    op.create_table("comments", sa.Column("id", sa.Integer, primary_key=True))'
    add_migration(build, "0002_comments", create)
    add_migration(build, "0002_comments_again", create)
    return build


def r7_broken_upgrade(build: Path) -> Path:
    add_migration(build, "0002_broken", '    op.execute("THIS IS NOT SQL")')
    return build


def board_shows_other_orgs(build: Path) -> Path:
    edit(
        build,
        "app/web/routes.py",
        "    for issue in _all_issues(db, actor, project.id):",
        "    from app.services import legacy\n\n"
        "    for issue in _all_issues(db, actor, project.id) + legacy.list_issues(db, 0, 500):",
    )
    return build
