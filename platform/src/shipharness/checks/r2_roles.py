"""R2 roles: every write endpoint (POST/PUT/PATCH/DELETE) called as a viewer must return 403."""

from __future__ import annotations

import time
from pathlib import Path

from shipharness.checks._http import apply_exemptions, excerpt, open_target, path_for
from shipharness.checks.base import CheckContext, CheckResult, Finding, make_result, register_check


@register_check
class RolesCheck:
    name = "r2_roles"
    rule = "R2"

    def run(self, build_dir: Path, ctx: CheckContext) -> CheckResult:
        started = time.monotonic()
        findings: list[Finding] = []
        with open_target(build_dir, ctx) as t:
            home, _other = t.adapter.orgs()
            ids, viewer = t.adapter.ids(home), t.adapter.headers(home, "viewer")
            writes = [e for e in t.endpoints if e.is_write]
            for done, e in enumerate(writes, start=1):
                path = path_for(e, ids)
                response = t.send(e.method, path, t.body(e, ids), viewer)
                if response.status_code != 403:
                    findings.append(
                        Finding(
                            rule="R2",
                            severity="violation",
                            endpoint=e.label,
                            detail_key="status",
                            detail=f"viewer {e.method} {path} -> {response.status_code} "
                            f"(expected 403) {excerpt(response)}",
                        )
                    )
                ctx.progress(done, len(writes), f"House rule 2 probes {done}/{len(writes)}")
        return make_result(
            self.name, apply_exemptions(findings, ctx), total_probes=len(writes), started=started
        )
