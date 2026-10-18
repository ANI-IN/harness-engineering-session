"""Two sessions through the real runner loop with a scripted model, the state and scope layers, and
LocalSandbox (UNSANDBOXED: only this test's own fixture code runs) on a temporary git repo."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from shipharness.config import DEFAULT_PRICES_FILE, Prices, Settings
from shipharness.cost import Caps, CostTracker
from shipharness.events import EventBus, read_events
from shipharness.harness.base import Harness
from shipharness.harness.scope.layer import ScopeLayer
from shipharness.harness.state.layer import StateLayer
from shipharness.runner.loop import RunOptions, run_agent
from shipharness.runner.model import ScriptedModelClient, tool_step
from shipharness.runner.prompts import NEUTRAL_RESUME
from shipharness.sandbox import LocalSandbox, default_policy
from shipharness.tracing import NullTracer

from ..harness_scope.helpers import make_spec, patch_for

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@x"]


def git_out(ws: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=ws, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    ws = tmp_path / "ws"
    (ws / "app" / "api").mkdir(parents=True)
    (ws / "tests" / "visible").mkdir(parents=True)
    (ws / "app" / "api" / "issues.py").write_text("issues = 1\n", encoding="utf-8")
    (ws / "app" / "models.py").write_text("models = 1\n", encoding="utf-8")
    (ws / "tests" / "visible" / "test_ok.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    subprocess.run([*GIT, "init", "-q"], cwd=ws, check=True)
    subprocess.run([*GIT, "add", "."], cwd=ws, check=True)
    subprocess.run([*GIT, "commit", "-qm", "checkpoint"], cwd=ws, check=True)
    return ws


def test_two_sessions_hand_off_resume_and_set_passes(repo: Path, tmp_path: Path) -> None:
    steps = [
        # session 1 (4 turns, stopped by the turn budget)
        tool_step("apply_patch", patch=patch_for("app/api/issues.py", "issues = 1", "issues = 2")),
        tool_step(
            "run",
            command="python -c \"open('app/models.py','w').write('hacked')\"",
            timeout_s=None,
        ),
        tool_step("apply_patch", patch=patch_for("feature_list.json", "{", "[")),
        tool_step(
            "run", command="git -c user.name=a -c user.email=a@x commit -qam wip", timeout_s=None
        ),
        # session 2 (resumed with an empty context)
        tool_step("read_file", path="progress.md", start_line=None, max_lines=None),
        tool_step("finish", claim="done", summary="issues updated; visible tests pass"),
    ]
    client = ScriptedModelClient(steps)
    spec = make_spec(repo, phases=("build",), session_budget=[4, 4])
    tracker = CostTracker(
        Prices.load(DEFAULT_PRICES_FILE),
        Caps(run=0.20, review=0.04, session=2.5, batch=2.5, experiment=25.0),
        tmp_path / "ledger.jsonl",
        session_id="test",
    )
    sandbox = LocalSandbox(default_policy(Settings(_env_file=None)), repo, None, "r-1", "harness")
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id="ab-1") as bus:
        result = run_agent(
            spec,
            Harness([StateLayer(), ScopeLayer()]),
            sandbox,
            bus,
            tracker,
            NullTracer(),
            client,
            RunOptions(wrapup_turns=2, sleep=lambda _s: None, tool_log_dir=tmp_path / "logs"),
        )
    events = list(read_events(log))

    assert result.status == "completed", result.error
    assert [s.ended_by for s in result.sessions] == ["turn_budget", "claim_done"]

    # prefix blocks, wrap-up, and resume text
    prefix = json.dumps(client.inputs[0][0])
    assert "## Getting up to speed" in prefix and "## Scope" in prefix
    assert json.dumps(client.inputs[4][0]) == prefix  # byte-stable across sessions
    wrapup = json.dumps(client.inputs[2])
    assert "session-handoff.md" in wrapup and "Notes from the agent" in wrapup
    resume = json.dumps(client.inputs[4])
    assert NEUTRAL_RESUME in resume and "Its machine summary" in resume
    assert "app/api/issues.py" in resume
    assert not any(i.get("type") == "function_call" for i in client.inputs[4])

    # scope: blocked patch and reverted run change
    blocked = [e.data for e in events if e.type == "blocked"]
    assert [b["action"] for b in blocked] == ["revert", "reject_patch"]
    assert blocked[0]["paths"] == ["app/models.py"]
    assert blocked[1]["paths"] == ["feature_list.json"]
    assert (repo / "app" / "models.py").read_text(encoding="utf-8") == "models = 1\n"
    assert (repo / "app" / "api" / "issues.py").read_text(encoding="utf-8") == "issues = 2\n"

    # state: handoff and a consistent progress log
    stops = [
        e.data for e in events if e.type == "harness_decision" and e.data["kind"] == "session_stop"
    ]
    assert [s["data"]["session_index"] for s in stops] == [1, 2]
    handoff = (repo / "session-handoff.md").read_text(encoding="utf-8")
    assert "end of session 2" in handoff and "passed=1 failed=0 errors=0" in handoff
    log_lines = (
        (repo / "progress.md").read_text(encoding="utf-8").split("## Session log")[1].split("\n")
    )
    entries = [line for line in log_lines if line.startswith("- Session")]
    first, second = result.sessions
    assert entries[0].startswith(
        f"- Session 1 (build): start {first.start_sha[:7]}, end {first.end_sha[:7]}, "
        "ended by turn_budget after 4 turns. 1 files changed"
    )
    assert entries[1].startswith(
        f"- Session 2 (build): start {second.start_sha[:7]}, end {second.end_sha[:7]}, "
        "ended by claim_done after 2 turns."
    )
    assert len(entries) == 2

    # evidence-gated passes (verify off: visible tests in the sandbox) and exec plan completion
    feature = json.loads((repo / "feature_list.json").read_text(encoding="utf-8"))["features"][0]
    assert feature["passes"] is True and feature["evidence"]["visible"] == "1/1"
    assert (repo / "docs/exec-plans/completed/F3.md").is_file()
    assert not (repo / "docs/exec-plans/active/F3.md").exists()

    # every harness write is committed; the tree is clean at the end
    authors = git_out(repo, "log", "--format=%an %s").splitlines()
    assert sum(1 for a in authors if a.startswith("shipharness ")) == 6
    assert git_out(repo, "status", "--porcelain") == ""
