"""Your tests for R8. Write each test before the code it checks, and see it fail first.

Run: uv run python -m pytest -q section-4-verification/assignment/starter/tests
(from the repository root, with this starter folder on PYTHONPATH; see the README, "How to test").
"""

from __future__ import annotations

from a4_verification.r8_soft_delete import issue_param

from shipharness.checks.discovery import Endpoint


def endpoint(method: str, path: str) -> Endpoint:
    params = [s[1:-1] for s in path.split("/") if s.startswith("{")]
    return Endpoint(
        method=method,
        path=path,
        operation_id=f"{method.lower()}_{path}",
        path_params=params,
        is_write=method != "GET",
        requires_auth=True,
        accepts_idempotency_key=False,
        has_body=method in ("POST", "PUT", "PATCH"),
    )


def test_issue_id_parameter_addresses_an_issue() -> None:
    assert issue_param(endpoint("GET", "/issues/{issue_id}")) == "issue_id"


# TODO(A4-8): add your own tests (at least 8 in tests/ in total), for example:
#   - `{id}` right after `issues` addresses an issue; `{project_id}` does not;
#   - judge() on each probe kind: 404 passes, 200 with a marker is a "leak", 204 is a "violation";
#   - plan() puts list probes first and builds a body probe only when the body has `issue_id`;
#   - the check on a TeamTrack copy with one seeded violation of your own.
