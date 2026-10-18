"""Import every built-in check module so the registry is complete (heavy imports stay lazy)."""

from __future__ import annotations

import importlib

BUILTIN_MODULES = (
    "r1_tenant",
    "r2_roles",
    "r3_conventions",
    "r4_idempotency",
    "r5_audit",
    "r6_layering",
    "r7_migrations",
    "pytest_checks",
    "diff_scope",
    "continuity",
    "board",
)
# Rule ids (machine ids, `shipharness check --rules R1,R2`); people read them through
# `shipharness.datasets.names.rule_label`: "House rule 1: Tenant isolation".
RULE_LABELS = {
    "r1_tenant": "R1",
    "r2_roles": "R2",
    "r3_conventions": "R3",
    "r4_idempotency": "R4",
    "r5_audit": "R5",
    "r6_layering": "R6",
    "r7_migrations": "R7",
    "regression": "regression",
    "hidden_tests": "hidden",
    "diff_scope": "scope",
    "flakiness": "flaky",
    "continuity": "continuity",
    "board": "board",
}


def load_builtin_checks() -> None:
    for module in BUILTIN_MODULES:
        importlib.import_module(f"shipharness.checks.{module}")
