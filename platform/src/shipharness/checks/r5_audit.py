"""R5 audit: every successful write adds exactly one audit row; a refused write adds none."""

from __future__ import annotations

import time
from pathlib import Path

from shipharness.checks._http import apply_exemptions, open_target, path_for
from shipharness.checks.base import CheckContext, CheckResult, Finding, make_result, register_check


@register_check
class AuditCheck:
    name = "r5_audit"
    rule = "R5"

    def run(self, build_dir: Path, ctx: CheckContext) -> CheckResult:
        started = time.monotonic()
        findings: list[Finding] = []
        with open_target(build_dir, ctx) as t:
            home, _other = t.adapter.orgs()
            ids, admin = t.adapter.ids(home), t.adapter.headers(home, "admin")
            writes = [e for e in t.endpoints if e.is_write]
            for done, e in enumerate(writes, start=1):
                path = path_for(e, ids)
                before = t.adapter.audit_count(t.app, home)
                status = t.send(e.method, path, t.body(e, ids), admin).status_code
                delta = t.adapter.audit_count(t.app, home) - before
                expected = 1 if 200 <= status < 300 else 0
                if delta != expected:
                    key = "missing" if delta < expected else "extra"
                    findings.append(
                        Finding(
                            rule="R5",
                            severity="violation",
                            endpoint=e.label,
                            detail_key=key,
                            detail=f"{e.method} {path} -> {status}: {delta} audit rows "
                            f"(expected {expected})",
                        )
                    )
                ctx.progress(done, len(writes), f"House rule 5 probes {done}/{len(writes)}")
        return make_result(
            self.name, apply_exemptions(findings, ctx), total_probes=len(writes), started=started
        )
