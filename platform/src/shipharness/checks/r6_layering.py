"""R6 layering: `app.api` (and the web board) never import `app.db`.

The import-linter contract comes from the adapter, never from the build: an arm could weaken the
build's own `.importlinter`. Each broken import chain is one finding.
"""

from __future__ import annotations

import re
import tempfile
import time
from pathlib import Path

from shipharness.checks._http import adapter_for
from shipharness.checks._proc import run_python, tail
from shipharness.checks.base import CheckContext, CheckResult, Finding, make_result, register_check

_LINT = (
    "import sys; from importlinter.cli import lint_imports_command; "
    "sys.argv = ['lint-imports'] + sys.argv[1:]; lint_imports_command()"
)
_CHAIN = re.compile(r"^-\s+(\S+\s+->\s+\S+(?:\s+->\s+\S+)*)", re.MULTILINE)


def broken_chains(output: str) -> list[str]:
    return sorted({re.sub(r"\s+", " ", m.group(1)) for m in _CHAIN.finditer(output)})


@register_check
class LayeringCheck:
    name = "r6_layering"
    rule = "R6"

    def run(self, build_dir: Path, ctx: CheckContext) -> CheckResult:
        started = time.monotonic()
        contract = adapter_for(ctx).layering_contract()
        with tempfile.TemporaryDirectory(prefix="shipharness-r6-") as tmp:
            config = Path(tmp) / "importlinter.ini"
            config.write_text(contract, encoding="utf-8")
            ctx.progress(0, 1, "House rule 6 import-linter")
            proc = run_python(["-c", _LINT, "--config", str(config), "--no-cache"], build_dir)
        ctx.progress(1, 1, "House rule 6 import-linter")
        findings: list[Finding] = []
        if proc.returncode != 0:
            output = proc.stdout + "\n" + proc.stderr
            chains = broken_chains(output)
            for chain in chains:
                findings.append(
                    Finding(
                        rule="R6",
                        severity="violation",
                        detail_key=chain,
                        detail=f"forbidden import: {chain}",
                    )
                )
            if not chains:
                findings.append(
                    Finding(
                        rule="R6",
                        severity="error",
                        detail_key="lint_failed",
                        detail=f"import-linter exited {proc.returncode}: {tail(output)}",
                    )
                )
        return make_result(self.name, findings, total_probes=1, started=started)
