"""Grading criteria for the reviewer (the term of Assignment 3: Scope and sandbox): SECURITY.md
and ARCHITECTURE.md from the harness instruction docs, or the house rules when those files are not
available. The house rules are named as people read them: "House rule 1: Tenant isolation"."""

from __future__ import annotations

from pathlib import Path

from shipharness.config.prices import REPO_ROOT
from shipharness.datasets.names import rule_label
from shipharness.layout import APP_DIR

INSTRUCTIONS_DIR = REPO_ROOT / APP_DIR / "harness" / "instructions"
SOURCES = ("docs/SECURITY.md", "ARCHITECTURE.md")

_RULES = {
    "R1": "Every query on customer data filters by the caller's org; another org's resource "
    "answers 404, never 403; ids in request bodies must belong to the caller's org.",
    "R2": "Viewers never write (403 on every POST, PUT, PATCH, DELETE); admin-only writes stay "
    "admin-only.",
    "R3": 'Lists return {"items", "next_cursor"} with keyset pagination; errors return '
    '{"error": {"code", "message"}}; 201 for creates, 204 for deletes.',
    "R4": "The same Idempotency-Key and body return the first response and create nothing new.",
    "R5": "Every write adds exactly one audit row; reads and replays add none.",
    "R6": "app/api never imports app/db.",
    "R7": "One migration head; upgrade from an empty database works.",
}
DEFAULT_CRITERIA = (
    "House rules (from docs/HANDBOOK.md):\n"
    + "".join(f"- {rule_label(code)}. {text}\n" for code, text in _RULES.items())
    + "Tests must exercise the behaviour of the ticket with real assertions."
)


def grading_criteria(instructions_dir: Path = INSTRUCTIONS_DIR) -> str:
    """Stable text: the same files give the same bytes, for both arms and every review."""
    parts = []
    for rel in SOURCES:
        path = Path(instructions_dir) / rel
        if path.is_file():
            parts.append(f"## {rel}\n\n{path.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(parts) if parts else DEFAULT_CRITERIA
