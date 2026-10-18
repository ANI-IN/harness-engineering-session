"""R8 soft delete: a soft-deleted issue never appears in a list and never resolves by id.

Discovers endpoints from the app's OpenAPI schema (like R1-R5), soft-deletes some of the home org's
issues through the adapter, and probes every endpoint as the home org's admin:

- `deleted_list`: a GET endpoint that does not address one issue returns 2xx with a deleted
  issue's marker in the body;
- `deleted_path`: an endpoint that addresses one issue (`{issue_id}`, or `{id}` right after an
  `issues` segment), called with a deleted issue's id, returns anything other than 404;
- `deleted_body`: a write endpoint that does not address one issue but takes `issue_id` in its JSON
  body succeeds (2xx) when the body names a deleted issue.

Severity is "leak" when a 2xx body contains a deleted issue's marker, else "violation". The
`detail_key` is exactly the probe kind above, so findings match across runs for baseline deltas.
"""

from __future__ import annotations

import dataclasses
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shipharness.checks._http import Target, apply_exemptions, open_target
from shipharness.checks.base import CheckContext, CheckResult, Finding, make_result, register_check
from shipharness.checks.discovery import Endpoint
from shipharness.checks.payloads import fill_path

DEFAULT_ADAPTER = "a4_verification.adapter:TeamTrackSoftDeleteAdapter"
KINDS = ("deleted_list", "deleted_path", "deleted_body")


@dataclass(frozen=True)
class Probe:
    endpoint: Endpoint
    kind: str  # one of KINDS
    path: str  # the filled path, e.g. "/issues/1"
    body: Any = None  # JSON body, or None
    params: dict[str, Any] = dataclasses.field(default_factory=dict)  # query parameters


def issue_param(endpoint: Endpoint) -> str | None:
    """The path parameter that addresses one issue, or None.

    `{issue_id}` anywhere in the path, or a parameter without a resource name (`{id}`) whose
    closest literal segment before it is `issues`. `{project_id}` or `{user_id}` never count.
    """
    previous = ""
    for segment in endpoint.path.split("/"):
        if not (segment.startswith("{") and segment.endswith("}")):
            if segment:
                previous = segment
            continue
        name = segment[1:-1]
        if name == "issue_id":
            return name
        if not name.endswith("_id") and previous == "issues":
            return name
    return None


def plan(t: Target, ids: dict[str, int], deleted: list[int]) -> list[Probe]:
    """Every probe for one build, lists first (they read before any write can change a row).

    - one `deleted_list` probe per GET endpoint where `issue_param` is None: path filled from
      `ids` (`shipharness.checks.payloads.fill_path`), required query parameters from
      `t.payloads.query(endpoint, ids)`;
    - one `deleted_path` probe per endpoint (any method) where `issue_param` is not None: that
      parameter set to `deleted[0]`, other parameters from `ids`, body from `t.body(endpoint, ...)`;
    - one `deleted_body` probe per write endpoint where `issue_param` is None and the generated body
      has an `issue_id` key: the body built with `issue_id` set to `deleted[0]`.
    """
    target = deleted[0]
    with_target = {**ids, "issue_id": target}
    lists: list[Probe] = []
    bodies: list[Probe] = []
    paths: list[Probe] = []
    for e in t.endpoints:
        param = issue_param(e)
        if param is not None:
            values = {**with_target, param: target}
            path = fill_path(e.path, values)
            paths.append(
                Probe(e, "deleted_path", path, t.body(e, values), t.payloads.query(e, values))
            )
        elif e.method == "GET":
            lists.append(
                Probe(e, "deleted_list", fill_path(e.path, ids), None, t.payloads.query(e, ids))
            )
        elif e.is_write:
            body = t.body(e, with_target)
            if isinstance(body, dict) and body.get("issue_id") == target:
                path = fill_path(e.path, ids)
                bodies.append(Probe(e, "deleted_body", path, body, t.payloads.query(e, ids)))
    return lists + bodies + paths


def judge(probe: Probe, status: int, text: str, markers: dict[int, str]) -> Finding | None:
    """Compare one response with what R8 requires; return a Finding or None.

    `markers` maps each deleted issue id to its marker text (adapter `deleted_marker`).
    """
    ok = 200 <= status < 300
    shown = sorted(issue_id for issue_id, marker in markers.items() if marker in text)
    leaked = ok and bool(shown)
    target = next(iter(markers))
    e = probe.endpoint
    where = f"{e.method} {probe.path} -> {status}"
    if probe.kind == "deleted_list":
        if not leaked:
            return None
        detail = (
            f"{where} lists soft-deleted issue(s) {shown}; add `deleted_at IS NULL` to the "
            "query (HANDBOOK: deleted issues are hidden from lists)"
        )
    elif probe.kind == "deleted_path":
        if status == 404:
            return None
        detail = (
            f"{where} for soft-deleted issue {target} (expected 404); load the issue with the "
            "live-issue lookup (repositories/issues.get), never by primary key alone"
        )
    else:
        if not ok:
            return None
        detail = (
            f"{where} with soft-deleted issue {target} in the body (expected 404); resolve "
            "body ids with the live-issue lookup"
        )
    return Finding(
        rule="R8",
        severity="leak" if leaked else "violation",
        endpoint=e.label,
        detail_key=probe.kind,
        detail=detail,
    )


def _with_adapter(ctx: CheckContext) -> CheckContext:
    """Use the soft-delete adapter unless the caller named one (`--adapter` or params)."""
    if ctx.params.get("adapter"):
        return ctx
    return dataclasses.replace(ctx, params={**ctx.params, "adapter": DEFAULT_ADAPTER})


def _setup_error(name: str, detail: str, started: float) -> CheckResult:
    finding = Finding(rule="R8", severity="error", detail_key="setup", detail=detail)
    return make_result(name, [finding], total_probes=0, started=started)


@register_check
class SoftDeleteCheck:
    name = "r8_soft_delete"
    rule = "R8"

    def run(self, build_dir: Path, ctx: CheckContext) -> CheckResult:
        started = time.monotonic()
        ctx = _with_adapter(ctx)
        findings: list[Finding] = []
        with open_target(build_dir, ctx) as t:
            if not hasattr(t.adapter, "soft_delete"):
                return _setup_error(self.name, "adapter has no soft_delete(app, org)", started)
            home, _other = t.adapter.orgs()
            deleted = t.adapter.soft_delete(t.app, home)
            if not deleted:
                return _setup_error(self.name, "soft_delete returned no ids", started)
            markers = {issue_id: t.adapter.deleted_marker(issue_id) for issue_id in deleted}
            admin = t.adapter.headers(home, "admin")
            probes = plan(t, t.adapter.ids(home), deleted)
            for done, probe in enumerate(probes, start=1):
                e = probe.endpoint
                response = t.send(e.method, probe.path, probe.body, admin, probe.params or None)
                finding = judge(probe, response.status_code, response.text, markers)
                if finding is not None:
                    findings.append(finding)
                ctx.progress(done, len(probes), f"R8 probes {done}/{len(probes)}")
        return make_result(
            self.name, apply_exemptions(findings, ctx), total_probes=len(probes), started=started
        )
