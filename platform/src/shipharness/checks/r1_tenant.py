"""R1 tenant isolation: as the home org, point every endpoint at the other org's ids.

Every discovered endpoint and method is probed, including endpoints without authentication (only
the public allowlist is skipped). Expectations:

- the other org's id in a path parameter: 404 (any other status is a violation);
- no path parameter: a 2xx must not contain the other org's data;
- the home org's path with the other org's ids in the body: must not succeed (2xx);
- no credentials at all: must not succeed (2xx).

A violation whose 2xx body contains another org's data is reported with severity "leak".
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shipharness.checks._http import (
    Target,
    apply_exemptions,
    excerpt,
    json_body,
    open_target,
    path_for,
)
from shipharness.checks.base import CheckContext, CheckResult, Finding, make_result, register_check
from shipharness.checks.discovery import Endpoint


@dataclass(frozen=True)
class Probe:
    endpoint: Endpoint
    kind: str  # foreign_path | foreign_param:<name> | no_path | foreign_body | anonymous
    path: str
    body: Any
    headers: dict[str, str]


def plan(t: Target, home: str, other: str) -> list[Probe]:
    own, foreign = t.adapter.ids(home), t.adapter.ids(other)
    as_home = t.adapter.headers(home, "admin")
    probes: list[Probe] = []
    for e in t.endpoints:
        if e.path_params:
            probes.append(
                Probe(e, "foreign_path", path_for(e, foreign), t.body(e, foreign), as_home)
            )
            if len(e.path_params) > 1:
                for name in e.path_params:
                    mixed = {**own, name: foreign.get(name, foreign.get("user_id", 0))}
                    path = path_for(e, mixed)
                    probes.append(Probe(e, f"foreign_param:{name}", path, t.body(e, own), as_home))
        else:
            probes.append(Probe(e, "no_path", e.path, t.body(e, foreign), as_home))
        body = t.body(e, foreign)
        if isinstance(body, dict) and any(k in foreign and k not in e.path_params for k in body):
            probes.append(Probe(e, "foreign_body", path_for(e, own), body, as_home))
        probes.append(Probe(e, "anonymous", path_for(e, foreign), t.body(e, foreign), {}))
    return probes


# [walkthrough:S4:probe] start
def judge(probe: Probe, response: Any, t: Target, home: str, other: str) -> Finding | None:
    """Compare one response with what tenant isolation requires."""
    status, body = response.status_code, json_body(response)
    ok = 200 <= status < 300
    leaked = ok and (
        t.adapter.is_foreign(body, other)
        or (probe.kind == "anonymous" and t.adapter.is_foreign(body, home))
    )
    if probe.kind in ("foreign_path",) or probe.kind.startswith("foreign_param:"):
        failed = status != 404
    else:  # no_path, foreign_body, anonymous: success itself is the failure (no_path: only leaks)
        failed = leaked if probe.kind == "no_path" else ok
    if not failed:
        return None
    return Finding(
        rule="R1",
        severity="leak" if leaked else "violation",
        endpoint=probe.endpoint.label,
        detail_key=probe.kind,
        detail=f"{probe.kind}: {probe.endpoint.method} {probe.path} -> {status} "
        f"{excerpt(response)}",
    )


def probe_all(t: Target, ctx: CheckContext) -> tuple[list[Finding], int]:
    home, other = t.adapter.orgs()
    probes = plan(t, home, other)
    findings: list[Finding] = []
    for done, probe in enumerate(probes, start=1):
        e = probe.endpoint
        response = t.send(e.method, probe.path, probe.body, probe.headers)
        finding = judge(probe, response, t, home, other)
        if finding is not None:
            findings.append(finding)
        ctx.progress(done, len(probes), f"House rule 1 probes {done}/{len(probes)}")
    return findings, len(probes)


# [walkthrough:S4:probe] end


@register_check
class TenantIsolationCheck:
    name = "r1_tenant"
    rule = "R1"

    def run(self, build_dir: Path, ctx: CheckContext) -> CheckResult:
        started = time.monotonic()
        with open_target(build_dir, ctx) as t:
            findings, total = probe_all(t, ctx)
        return make_result(
            self.name, apply_exemptions(findings, ctx), total_probes=total, started=started
        )
