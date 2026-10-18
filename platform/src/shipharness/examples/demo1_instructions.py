"""Constructed example for section 1 (instructions + the R1 house rule), `make example-1`.

What it demonstrates: the instructions layer puts the map (AGENTS.md) and the docs in the
workspace, and records which ones the agent opens. Here the scripted agent opens the map and the
list conventions, but not docs/SECURITY.md, and ships org-wide search (F1) with a query that has no
org filter: GET /issues returns the issues of every org, and the board shows the other org's cards
(screen 2: the cards marked "other org"). The referee's real R1 check reports the new violation.

This is a constructed example: the steps below are scripted, no model runs, and it costs $0. It is
never counted with the real runs.
"""

# ruff: noqa: E501 - the patch below quotes TeamTrack source lines as they are
from __future__ import annotations

from shipharness.examples.base import Scenario, finish, patch, read
from shipharness.runner.model import Step

# The mistake: `search` selects every live issue; it never filters on org_id (house rule R1). The
# board then lists the search results, so the other org's cards appear on the board as well.
LEAK_PATCH = """\
diff --git a/app/api/issues.py b/app/api/issues.py
--- a/app/api/issues.py
+++ b/app/api/issues.py
@@ -25,6 +25,16 @@ def list_project_issues(
     return to_page(rows, next_after, IssueOut.model_validate)


+@router.get("/issues", response_model=Page[IssueOut])
+def search_issues(
+    params: PageParams = Depends(page_params),
+    actor: Actor = Depends(current_actor),
+    db: Session = Depends(get_db),
+) -> Page[IssueOut]:
+    rows, next_after = issues.search(db, actor, decode_cursor(params.cursor), params.limit)
+    return to_page(rows, next_after, IssueOut.model_validate)
+
+
 @router.post("/projects/{project_id}/issues", response_model=IssueOut, status_code=201)
 def create_issue(
     project_id: Id,
diff --git a/app/repositories/issues.py b/app/repositories/issues.py
--- a/app/repositories/issues.py
+++ b/app/repositories/issues.py
@@ -53,3 +53,12 @@ def add(
 def list_all_legacy(session: Session, offset: int, limit: int) -> list[Issue]:
     \"\"\"LEGACY (used only by /v1/issues). Not tenant-scoped: do not use or copy this function.\"\"\"
     return list(session.scalars(select(Issue).order_by(Issue.id).offset(offset).limit(limit)))
+
+
+def search(session: Session, after: int | None, limit: int) -> tuple[list[Issue], int | None]:
+    \"\"\"Live issues for the org-wide search, newest first.\"\"\"
+    stmt = select(Issue).where(Issue.deleted_at.is_(None))
+    if after is not None:
+        stmt = stmt.where(Issue.id < after)
+    stmt = stmt.order_by(Issue.id.desc()).limit(limit + 1)
+    return split_page(list(session.scalars(stmt)), limit, lambda i: i.id)
diff --git a/app/services/issues.py b/app/services/issues.py
--- a/app/services/issues.py
+++ b/app/services/issues.py
@@ -116,3 +116,10 @@ def delete(session: Session, actor: Actor, issue_id: int) -> None:
     _touch(issue)
     audit.record(session, actor, "issue.delete", "issue", issue.id)
     session.commit()
+
+
+def search(
+    session: Session, actor: Actor, after: int | None = None, limit: int = 20
+) -> tuple[list[Issue], int | None]:
+    \"\"\"Feature 1: Org-wide issue search. One list instead of one per project.\"\"\"
+    return issues_repo.search(session, after, limit)
diff --git a/app/web/routes.py b/app/web/routes.py
--- a/app/web/routes.py
+++ b/app/web/routes.py
@@ -70,6 +70,16 @@ def _all_issues(db: Session, actor: Actor, project_id: int) -> list[Any]:
     return collected


+def _org_issues(db: Session, actor: Actor) -> list[Any]:
+    \"\"\"Every issue from the org-wide search, so the board shows one list for the org.\"\"\"
+    rows, after = issues.search(db, actor, None, 100)
+    collected = list(rows)
+    while after is not None:
+        rows, after = issues.search(db, actor, after, 100)
+        collected.extend(rows)
+    return collected
+
+
 @router.get("/login", response_class=HTMLResponse)
 def login_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
     return _render(request, "login.html", None, db, demo_users=DEMO_USERS)
@@ -103,7 +113,7 @@ def project_board(project_id: Id, request: Request, db: Session = Depends(get_db
     project = projects.get(db, actor, project_id)
     all_projects, _ = projects.list_page(db, actor, None, 100)
     columns: dict[str, list[Any]] = {status: [] for status in STATUSES}
-    for issue in _all_issues(db, actor, project.id):
+    for issue in _org_issues(db, actor):
         columns.setdefault(issue.status, []).append(issue)
     return _render(
         request, "board.html", actor, db, project=project, projects=all_projects, columns=columns
"""


def steps() -> list[Step]:
    return [
        read("AGENTS.md"),  # the map
        read("docs/design-docs/api-conventions.md"),  # one linked document (not docs/SECURITY.md)
        patch(LEAK_PATCH),
        finish(
            "done",
            "Added GET /issues (org-wide search with cursor pagination) and showed "
            "the search results on the board.",
        ),
        finish("done", "Test phase: no new tests."),
    ]


SCENARIO = Scenario(
    section="demo-1",
    feature="F1",
    title="reads the map and one document, then ships a search query without the org filter",
    demonstrates="the referee's check of House rule 1: Tenant isolation reports the cross-org "
    "leak, and the board shows the other org's cards",
    steps=steps,
)
