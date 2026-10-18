"""`feature_list.json`: one feature from the task, written by the harness."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from shipharness.harness.state.files import write_file
from shipharness.runner.models import AgentRunSpec

FEATURE_LIST = "feature_list.json"
FEATURE_SCHEMA = "feature_list.schema.json"
SCHEMA_ASSET = Path(__file__).parent / "assets" / FEATURE_SCHEMA
_STEP = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.+?)\s*$")


def ticket_title(ticket: str, limit: int = 200) -> str:
    """First non-empty line of the ticket, without Markdown heading marks."""
    for line in ticket.splitlines():
        text = line.strip().lstrip("#").strip()
        if text:
            return text[:limit]
    return ""


def ticket_steps(ticket: str) -> list[str]:
    """Bullet or numbered lines of the ticket, in order."""
    return [m.group(1) for line in ticket.splitlines() if (m := _STEP.match(line))]


def build_feature(
    spec: AgentRunSpec,
    category: str = "feature",
    description: str | None = None,
    steps: list[str] | None = None,
) -> dict[str, Any]:
    title = description or ticket_title(spec.ticket_text) or spec.feature_id
    return {
        "id": spec.feature_id,
        "category": category,
        "description": title,
        "steps": list(steps) if steps is not None else (ticket_steps(spec.ticket_text) or [title]),
        "passes": False,
        "evidence": None,
        "testedAt": None,
    }


def render(feature: dict[str, Any]) -> bytes:
    document = {"$schema": f"./{FEATURE_SCHEMA}", "features": [feature]}
    return (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def write_feature_list(workspace: Path, feature: dict[str, Any]) -> None:
    """Write both files from the harness's own copy (never from what is on disk)."""
    write_file(workspace, FEATURE_LIST, render(feature))
    write_file(workspace, FEATURE_SCHEMA, SCHEMA_ASSET.read_bytes())
