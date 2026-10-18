"""Fixtures for the instructions layer: a small instructions tree and a layer context."""

from __future__ import annotations

from pathlib import Path

import pytest

from shipharness.events import EventBus
from shipharness.harness.base import LayerContext
from shipharness.runner.models import AgentRunSpec
from shipharness.sandbox import FakeSandbox

SKILL_BODY = "SKILL BODY SENTINEL: never part of the context prefix."
MAP_TEXT = "# AGENTS.md\n\nMap line. Read docs/SECURITY.md before changing access rules.\n"


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def source(tmp_path: Path) -> Path:
    root = tmp_path / "instructions"
    write(
        root,
        "AGENTS.md",
        "<!-- [walkthrough:S9:fixture] start -->\n"
        + MAP_TEXT
        + "<!-- [walkthrough:S9:fixture] end -->\n",
    )
    write(root, "ARCHITECTURE.md", "# Architecture\n")
    write(root, "docs/SECURITY.md", "# Security\n")
    write(root, "docs/references/tool-llms.txt", "tool reference\n")
    write(
        root,
        ".agents/skills/add-endpoint/SKILL.md",
        "---\nname: add-endpoint\ndescription: Add an endpoint the house way.\n---\n\n"
        + SKILL_BODY
        + "\n",
    )
    write(root, ".agents/skills/add-endpoint/references/tests.md", "test notes\n")
    return root


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    write(ws, "docs/HANDBOOK.md", "# Handbook\n")
    write(ws, "app/main.py", "print('app')\n")
    return ws


def make_ctx(workspace: Path, bus: EventBus | None = None) -> LayerContext:
    spec = AgentRunSpec(
        run_id="r-1",
        arm="harness",
        feature_id="F1",
        checkpoint="m1-s1-start",
        ticket_text="t",
        model="m",
        reasoning_effort="low",
        workspace=workspace,
    )
    return LayerContext(
        spec=spec,
        phase="build",
        session_index=1,
        turn=1,
        workspace=workspace,
        sandbox=FakeSandbox(),
        bus=bus,
    )
