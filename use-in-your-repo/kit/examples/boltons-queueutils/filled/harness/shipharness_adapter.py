"""House-rule adapter for `shipharness check` on boltons-queueutils.

Filled in from the kit template (kit/templates/harness/shipharness_adapter.py). This repository is
a library with no HTTP API and no database, so it keeps R6 (layering, rule BQ1) and the check that
existing tests keep passing. The methods that only R1-R5 and R7 call are deleted
(docs/house-rules.md says why).

    PYTHONPATH=harness uv run --project ~/shipharness shipharness check --app . \
        --adapter shipharness_adapter:HouseRulesAdapter --rules R6,regression \
        --params harness/check-params.json
"""

from __future__ import annotations

# BQ1: a module may import only the modules below it. import-linter counts an import inside
# `try: ... except ImportError:` as an import, so the guarded imports are checked too.
LAYERING_CONTRACT = """\
[importlinter]
root_package = boltons

[importlinter:contract:bq1]
name = BQ1: queueutils, then listutils, then typeutils; never upward
type = layers
layers =
    boltons.queueutils
    boltons.listutils
    boltons.typeutils
"""


class HouseRulesAdapter:
    """Adapter for boltons-queueutils: R6 and existing tests only."""

    def exemptions(self, checkpoint: str) -> dict[str, list[str]]:
        """No exemptions: every finding counts."""
        return {}

    def layering_contract(self) -> str:
        """The import-linter configuration R6 runs (rule BQ1)."""
        return LAYERING_CONTRACT
