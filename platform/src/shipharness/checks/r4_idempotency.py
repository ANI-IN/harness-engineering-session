"""R4 idempotent creates: the same Idempotency-Key with the same body leaves exactly one record.

Every create endpoint (a POST that documents 201, or answers 201) gets the same request twice
with the same key. Records are counted per table in the build's SQLite database, so the check
does not trust the response: a second request that adds rows to any non-bookkeeping table is a
"duplicate". Where the endpoint documents the Idempotency-Key header, the replay must also return
the first response ("replay_mismatch" otherwise). Exempt endpoints are reported as info.
"""

from __future__ import annotations

import time
from pathlib import Path

from shipharness.checks._http import (
    Target,
    apply_exemptions,
    excerpt,
    json_body,
    open_target,
    path_for,
    table_counts,
)
from shipharness.checks.base import CheckContext, CheckResult, Finding, make_result, register_check
from shipharness.checks.discovery import Endpoint

KEY_PREFIX = "shipharness-r4"


def _documents_201(t: Target, e: Endpoint) -> bool:
    op = t.app.openapi().get("paths", {}).get(e.path, {}).get("post", {})
    return "201" in op.get("responses", {})


def _added(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    return {k: v - before.get(k, 0) for k, v in after.items() if v > before.get(k, 0)}


def _finding(e: Endpoint, key: str, detail: str) -> Finding:
    return Finding(rule="R4", severity="violation", endpoint=e.label, detail_key=key, detail=detail)


def probe(
    t: Target, e: Endpoint, n: int, ids: dict[str, int], headers: dict[str, str]
) -> tuple[Finding | None, bool]:
    """(finding or None, whether the endpoint is a create endpoint)."""
    ignore = t.adapter.bookkeeping_tables
    path, body = path_for(e, ids), t.body(e, ids)
    sent = {**headers, "Idempotency-Key": f"{KEY_PREFIX}-{n}"}
    first = t.send("POST", path, body, sent)
    middle = table_counts(t.db_path, ignore)
    if first.status_code != 201 and not _documents_201(t, e):
        return None, False  # not a create endpoint
    if not 200 <= first.status_code < 300:
        detail = f"first POST {path} -> {first.status_code}; not tested {excerpt(first)}"
        untested = Finding(
            rule="R4", severity="info", endpoint=e.label, detail_key="untested", detail=detail
        )
        return untested, True
    second = t.send("POST", path, body, sent)
    extra = _added(middle, table_counts(t.db_path, ignore))
    if extra:
        rows = ", ".join(f"{table} +{count}" for table, count in sorted(extra.items()))
        return _finding(e, "duplicate", f"same key twice on {path}: second POST added {rows}"), True
    replay_differs = (second.status_code, json_body(second)) != (
        first.status_code,
        json_body(first),
    )
    if e.accepts_idempotency_key and replay_differs:
        detail = (
            f"replay on {path} -> {second.status_code}, first was {first.status_code} "
            f"{excerpt(second)}"
        )
        return _finding(e, "replay_mismatch", detail), True
    return None, True


@register_check
class IdempotencyCheck:
    name = "r4_idempotency"
    rule = "R4"

    def run(self, build_dir: Path, ctx: CheckContext) -> CheckResult:
        started = time.monotonic()
        findings: list[Finding] = []
        tested = 0
        with open_target(build_dir, ctx) as t:
            home, _other = t.adapter.orgs()
            ids, admin = t.adapter.ids(home), t.adapter.headers(home, "admin")
            posts = [e for e in t.endpoints if e.method == "POST"]
            for n, e in enumerate(posts, start=1):
                finding, is_create = probe(t, e, n, ids, admin)
                tested += int(is_create)
                if finding is not None:
                    findings.append(finding)
                ctx.progress(n, len(posts), f"House rule 4 probes {n}/{len(posts)}")
        return make_result(
            self.name, apply_exemptions(findings, ctx), total_probes=tested, started=started
        )
