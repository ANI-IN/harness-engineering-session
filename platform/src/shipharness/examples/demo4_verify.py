"""Constructed example for section 4 (verification), `make example-4`.

What it demonstrates: "done" is a claim, and the gate checks it. The scripted agent builds the
service layer of optimistic concurrency (F4: the ETag, the If-Match check, the issue history) and
adds one test of its own with a wrong expectation (it expects the bare version; the ETag is the
version in double quotes). It commits and claims done: the verify gate runs the visible tests in
the sandbox, the test fails, and finish returns "Not accepted" with the failing test (console: gate
pills, gate fail). The agent fixes the test, commits, and claims done again: the gate passes.

This is a constructed example: the steps below are scripted, no model runs, and it costs $0. It is
never counted with the real runs. The service code is the course's reference change for F4 (its
service and repository files only, so the example shows the gate, not the whole feature).
"""

from __future__ import annotations

from shipharness.examples.base import Scenario, commit, finish, patch, reference_patch
from shipharness.runner.model import Step

SERVICE_FILES = ("app/repositories/audit.py", "app/services/audit.py", "app/services/issues.py")
FAILING_TEST = "tests/visible/test_issue_etag.py::test_etag_is_the_quoted_version"

# The agent's own test, with the mistake: the ETag is '"2"' (quoted), not "2".
WRONG_TEST_PATCH = """\
diff --git a/tests/visible/test_issue_etag.py b/tests/visible/test_issue_etag.py
new file mode 100644
--- /dev/null
+++ b/tests/visible/test_issue_etag.py
@@ -0,0 +1,12 @@
+\"\"\"Feature 4: Version checks on issue edits. The ETag is the version in double quotes.\"\"\"
+
+from __future__ import annotations
+
+from types import SimpleNamespace
+
+from app.services.issues import etag
+
+
+def test_etag_is_the_quoted_version() -> None:
+    issue = SimpleNamespace(version=2)
+    assert etag(issue) == "2"
"""
FIX_PATCH = """\
diff --git a/tests/visible/test_issue_etag.py b/tests/visible/test_issue_etag.py
--- a/tests/visible/test_issue_etag.py
+++ b/tests/visible/test_issue_etag.py
@@ -9,4 +9,4 @@ from app.services.issues import etag

 def test_etag_is_the_quoted_version() -> None:
     issue = SimpleNamespace(version=2)
-    assert etag(issue) == "2"
+    assert etag(issue) == '"2"'
"""


def steps() -> list[Step]:
    return [
        patch(reference_patch("F4", SERVICE_FILES) + WRONG_TEST_PATCH),
        commit("issues: ETag, If-Match check, and history in the service layer"),
        # The gate refuses this claim: one visible test fails.
        finish("done", "ETag, If-Match check (412), and issue history in the service layer."),
        patch(FIX_PATCH),
        commit("tests: the ETag is the quoted version"),
        finish("done", "Fixed the expectation in test_issue_etag.py; visible tests pass."),
        finish("done", "Test phase: the test was written in the build phase."),
    ]


SCENARIO = Scenario(
    section="demo-4",
    feature="F4",
    title="claims done while its own test fails, then fixes the test and claims done again",
    demonstrates="the verify gate refuses the first claim with the failing test and accepts the "
    "second",
    steps=steps,
)
