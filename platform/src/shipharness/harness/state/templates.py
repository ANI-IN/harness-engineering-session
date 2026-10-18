"""Templates for the initializer step (`assets/`), rendered deterministically from the task."""

from __future__ import annotations

import re
from pathlib import Path

from shipharness.datasets.names import feature_label
from shipharness.harness.scope.features import ticket_steps, ticket_title
from shipharness.runner.models import AgentRunSpec

ASSETS = Path(__file__).parent / "assets"
INIT_SH = "init.sh"
PROGRESS = "progress.md"
HANDOFF = "session-handoff.md"
_FIELD = re.compile(r"\{\{(\w+)\}\}")
_UNSAFE_ID = re.compile(r"[^A-Za-z0-9._-]")


def exec_plan_path(feature_id: str, folder: str = "active") -> str:
    """`docs/exec-plans/<folder>/<feature>.md`."""
    return f"docs/exec-plans/{folder}/{_UNSAFE_ID.sub('_', feature_id) or 'feature'}.md"


def fields(
    spec: AgentRunSpec, description: str | None = None, steps: list[str] | None = None
) -> dict[str, str]:
    title = description or ticket_title(spec.ticket_text) or spec.feature_id
    step_list = steps if steps is not None else (ticket_steps(spec.ticket_text) or [title])
    return {
        "feature_id": spec.feature_id,
        "feature": feature_label(spec.feature_id),
        "description": title,
        "exec_plan": exec_plan_path(spec.feature_id),
        "steps": "\n".join(f"- {step}" for step in step_list),
    }


def render(asset: str, values: dict[str, str]) -> bytes:
    """Fill `{{name}}` fields in one pass; drop walkthrough marker lines; LF line endings."""
    text = (ASSETS / asset).read_text(encoding="utf-8").replace("\r\n", "\n")
    text = "".join(line for line in text.splitlines(keepends=True) if "[walkthrough:" not in line)
    text = _FIELD.sub(lambda m: values.get(m.group(1), m.group(0)), text)
    return text.encode("utf-8")


def initial_files(
    spec: AgentRunSpec, description: str | None = None, steps: list[str] | None = None
) -> dict[str, bytes]:
    values = fields(spec, description, steps)
    return {
        INIT_SH: render("init.sh", values),
        PROGRESS: render("progress.md", values),
        HANDOFF: render("session-handoff.md", values),
        values["exec_plan"]: render("exec-plan.md", values),
    }
