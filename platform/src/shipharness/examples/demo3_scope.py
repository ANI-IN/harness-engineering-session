"""Constructed example for section 3 (scope and sandbox), `make example-3`.

What it demonstrates: two guard rails the agent cannot talk its way past. The scripted agent first
tries to add the Idempotency-Key handling (F3) to app/api/middleware.py, shared middleware that the
ticket puts out of scope: the scope layer rejects the patch before anything is written (console:
BLOCKED). Then it tries to install a package: the sandbox has no network, so the command is denied
(console: DENIED network). Then it makes the change in the allowed files, commits, and writes the
tests in the test phase.

This is a constructed example: the steps below are scripted, no model runs, and it costs $0. It is
never counted with the real runs. The in-scope code is the course's reference change for F3.
"""

from __future__ import annotations

from shipharness.examples.base import Scenario, commit, finish, patch, reference_patch, run
from shipharness.runner.model import Step

# The out-of-scope attempt (app/api/middleware.py is not in the task's allowed paths).
MIDDLEWARE_PATCH = """\
diff --git a/app/api/middleware.py b/app/api/middleware.py
--- a/app/api/middleware.py
+++ b/app/api/middleware.py
@@ -19,6 +19,9 @@ log = structlog.get_logger("teamtrack.http")
 class RequestIdMiddleware(BaseHTTPMiddleware):
     async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
         request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
+        key = request.headers.get("Idempotency-Key")
+        if key and request.method == "POST":
+            request.state.idempotency_key = key  # replay handled per endpoint
         started = time.perf_counter()
         response = await call_next(request)
         response.headers["X-Request-ID"] = request_id
"""
NETWORK_COMMAND = "pip install requests"  # needs the network; the sandbox has none
BUILD_FILES = ("app/api/issues.py", "app/services/issues.py", "docs/HANDBOOK.md")
TEST_FILES = ("tests/visible/test_issue_idempotency.py",)


def steps() -> list[Step]:
    return [
        patch(MIDDLEWARE_PATCH),  # BLOCKED by the scope layer
        run(NETWORK_COMMAND),  # DENIED by the sandbox (network none)
        patch(reference_patch("F3", BUILD_FILES)),  # the allowed files
        commit("issues: Idempotency-Key on issue creation (House rule 4: Safe retries)"),
        finish(
            "done",
            "POST /projects/{project_id}/issues honours Idempotency-Key through "
            "services.idempotency.run_once; House rule 4: Safe retries updated.",
        ),
        # Test phase: tests only.
        patch(reference_patch("F3", TEST_FILES)),
        commit("tests: idempotent issue creation"),
        finish("done", "Tests for replay, conflict, per-org keys, and the audit log."),
    ]


SCENARIO = Scenario(
    section="demo-3",
    feature="F3",
    title="edits the shared middleware, then installs a package, then works in scope",
    demonstrates="the scope layer blocks the out-of-scope patch and the sandbox denies the "
    "network command",
    steps=steps,
)
