"""R7 migrations: exactly one Alembic head; `alembic upgrade head` works on an empty database."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from shipharness.checks._http import adapter_for
from shipharness.checks._proc import run_python, tail
from shipharness.checks.base import CheckContext, CheckResult, Finding, make_result, register_check


def count_heads(output: str) -> int:
    return sum(1 for line in output.splitlines() if "(head)" in line)


def _finding(key: str, detail: str, severity: str = "violation") -> Finding:
    return Finding(rule="R7", severity=severity, detail_key=key, detail=detail)  # type: ignore[arg-type]


def migration_findings(build_dir: Path, ctx: CheckContext) -> list[Finding]:
    """Shared with the continuity check (S2 component a)."""
    findings: list[Finding] = []
    with tempfile.TemporaryDirectory(prefix="shipharness-r7-", ignore_cleanup_errors=True) as tmp:
        env = adapter_for(ctx).migration_env(Path(tmp) / "fresh.db")
        heads = run_python(["-m", "alembic", "heads"], build_dir, env)
        ctx.progress(1, 2, "House rule 7 alembic heads")
        if heads.returncode != 0:
            detail = f"alembic heads exited {heads.returncode}: {tail(heads.stderr)}"
            findings.append(_finding("heads", detail, "error"))
        elif (n := count_heads(heads.stdout)) != 1:
            findings.append(_finding("heads", f"{n} heads (expected 1): {tail(heads.stdout)}"))
        upgrade = run_python(["-m", "alembic", "upgrade", "head"], build_dir, env)
        ctx.progress(2, 2, "House rule 7 alembic upgrade head")
        if upgrade.returncode != 0:
            detail = f"fresh upgrade head exited {upgrade.returncode}: {tail(upgrade.stderr)}"
            findings.append(_finding("upgrade", detail))
    return findings


@register_check
class MigrationsCheck:
    name = "r7_migrations"
    rule = "R7"

    def run(self, build_dir: Path, ctx: CheckContext) -> CheckResult:
        started = time.monotonic()
        findings = migration_findings(build_dir, ctx)
        return make_result(self.name, findings, total_probes=2, started=started)
