"""continuity (S2 measures). A run fails continuity if any of:

(a) R7 fails: migration heads != 1 or a fresh `alembic upgrade head` fails;
(b) a second migration creates a table that another migration already creates;
(c) >= 30% of the lines added in session 1 are removed in session 2.

Inputs: the build (a, b) and `params.session_patches`, one unified diff per session in order,
each relative to that session's start (written by the host from the run's session SHAs with
`shipharness.runner.git.write_diff`). `params.run_log` (optional) is the run's events.jsonl; when
given, the number of `session_stop` events is reported, counting only `params.run_id`'s events when
set (an A/B writes both arms to one log). Without two patches, (c) is not judged
and `redone_lines_pct` is None.
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path

from shipharness.checks.base import CheckContext, CheckResult, Finding, make_result, register_check
from shipharness.checks.r7_migrations import migration_findings

REDONE_THRESHOLD_PCT = 30.0
_CREATE_TABLE = re.compile(r"""create_table\(\s*["']([A-Za-z0-9_]+)["']""")


def _lines_by_file(diff: str, sign: str) -> dict[str, Counter[str]]:
    """Non-blank added ("+") or removed ("-") lines per file of a unified diff."""
    out: dict[str, Counter[str]] = {}
    current, old = "", ""
    for line in diff.splitlines():
        if line.startswith("--- "):
            old = line[4:].strip()
        elif line.startswith("+++ "):
            new = line[4:].strip()
            current = old if new == "/dev/null" else new
            current = current[2:] if current[:2] in ("a/", "b/") else current
        elif line.startswith(sign) and not line.startswith(sign * 3) and line[1:].strip():
            out.setdefault(current, Counter())[line[1:].strip()] += 1
    return out


def redone_pct(session_1: str, session_2: str) -> float:
    """Share of session-1 added lines that session 2 removes (same file, same text)."""
    added, removed = _lines_by_file(session_1, "+"), _lines_by_file(session_2, "-")
    total = sum(sum(c.values()) for c in added.values())
    if total == 0:
        return 0.0
    redone = sum(
        sum((lines & removed.get(path, Counter())).values()) for path, lines in added.items()
    )
    return round(100.0 * redone / total, 1)


def duplicate_tables(versions: Path) -> dict[str, list[str]]:
    creators: dict[str, list[str]] = {}
    for path in sorted(versions.glob("*.py")) if versions.is_dir() else []:
        for table in set(_CREATE_TABLE.findall(path.read_text(encoding="utf-8", errors="replace"))):
            creators.setdefault(table, []).append(path.name)
    return {t: files for t, files in creators.items() if len(files) > 1}


def _sessions(run_log: str | None, run_id: str | None = None) -> int | None:
    if not run_log or not Path(run_log).exists():
        return None
    count = 0
    for line in Path(run_log).read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
            ours = not run_id or event.get("run_id") == run_id
            count += ours and event.get("type") == "session_stop"
        except (ValueError, AttributeError):
            continue
    return count


def _finding(key: str, detail: str) -> Finding:
    return Finding(rule="continuity", severity="violation", detail_key=key, detail=detail)


@register_check
class ContinuityCheck:
    name = "continuity"
    rule = "continuity"

    def run(self, build_dir: Path, ctx: CheckContext) -> CheckResult:
        started = time.monotonic()
        findings = [
            f.model_copy(update={"rule": "continuity", "detail_key": f"r7:{f.detail_key}"})
            for f in migration_findings(build_dir, ctx)
        ]
        versions = build_dir / str(ctx.params.get("migrations_dir", "migrations/versions"))
        for table, files in sorted(duplicate_tables(versions).items()):
            findings.append(_finding(f"duplicate_table:{table}", f"{table} created by {files}"))
        patches = [Path(p) for p in ctx.params.get("session_patches") or []]
        pct: float | None = None
        if len(patches) >= 2:
            pct = redone_pct(patches[0].read_text("utf-8"), patches[1].read_text("utf-8"))
            if pct >= REDONE_THRESHOLD_PCT:
                detail = f"{pct}% of session-1 added lines removed in session 2"
                findings.append(_finding("redone_lines", detail))
        ctx.progress(1, 1, "continuity")
        metrics: dict[str, float | int | bool | None] = {
            "redone_lines_pct": pct,
            "sessions": _sessions(ctx.params.get("run_log"), ctx.params.get("run_id")),
        }
        return make_result(self.name, findings, total_probes=3, started=started, metrics=metrics)
