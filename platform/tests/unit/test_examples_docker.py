"""The demo-3 constructed example in a real container. Run with: pytest -m docker.

Needs the agent image (make images) and the course checkpoint tags. The build phase only: the scope
layer blocks the patch to app/api/middleware.py, the sandbox (network none) denies the package
install, and the in-scope reference change is applied by `git apply` inside the container.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from shipharness.ab.commands import FEATURES_FILE
from shipharness.ab.demo import ABDeps, ABTask, arm_specs, run_arm, section_layers
from shipharness.ab.workspace import app_dir_at, create_arm_workspace, resolve_commit
from shipharness.config import Settings
from shipharness.config.prices import REPO_ROOT
from shipharness.events import EventBus, read_events
from shipharness.examples import SCENARIOS
from shipharness.examples.run import (
    example_cost,
    example_settings,
    example_task,
    scripted_client_factory,
)
from shipharness.sandbox import DockerSandbox, default_policy, render_policy

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed"),
]


def _canonical(feature: str) -> ABTask:
    for line in FEATURES_FILE.read_text(encoding="utf-8").splitlines():
        data = json.loads(line)
        if data["inputs"]["feature_id"] == feature and data["inputs"]["variant"] == "canonical":
            return ABTask.from_dataset_line(data)
    raise AssertionError(feature)


def test_demo_3_blocks_denies_and_applies_in_a_real_container(tmp_path: Path) -> None:
    settings = example_settings(
        Settings(_env_file=None, runs_dir=tmp_path / "runs", exports_dir=tmp_path / "exports")
    )
    scenario = SCENARIOS["demo-3"]
    task = example_task(scenario, _canonical(scenario.feature))
    sha = resolve_commit(REPO_ROOT, task.checkpoint)
    workspace = create_arm_workspace(
        "ab-docker", "harness", REPO_ROOT, sha, base=tmp_path / "ws", label=task.checkpoint
    )
    spec = arm_specs(
        task,
        settings,
        ab_id="ab-docker",
        harness_layers=section_layers(scenario.section),
        workspaces={"harness": workspace},
        run_ids={"harness": "r-docker"},
        constructed=True,
    )["harness"].model_copy(update={"phases": ("build",)})
    policy = default_policy(settings)

    def sandbox_factory(arm, ws, bus, run_id):  # type: ignore[no-untyped-def]
        return DockerSandbox(policy, settings.sandbox_image_agent, ws, bus, run_id, arm)

    def no_referee(*_a: object) -> None:
        raise AssertionError("the referee does not run in this test")

    deps = ABDeps(
        settings=settings,
        course_repo=REPO_ROOT,
        checkpoint_ref=task.checkpoint,
        client_factory=scripted_client_factory(scenario),
        sandbox_factory=sandbox_factory,
        referee_sandbox_factory=no_referee,  # type: ignore[arg-type]
        cost=example_cost(settings, tmp_path / "ledger.jsonl"),
        policy_summary=render_policy(policy),
    )
    run_dir = tmp_path / "runs" / "ab-docker"
    with EventBus(run_dir / "events.jsonl", ab_id="ab-docker") as bus:
        result = run_arm(task, spec, deps, bus, run_dir)
    events = list(read_events(run_dir / "events.jsonl"))

    assert result.status == "completed", result.error
    assert result.cost_usd == 0.0
    [blocked] = [e for e in events if e.type == "blocked"]
    assert blocked.data["paths"] == ["app/api/middleware.py"]
    [denied] = [e for e in events if e.type == "sandbox_denied"]
    assert denied.data["reason_code"] == "network"
    assert "pip install requests" in denied.data["command"]
    applied = [
        e
        for e in events
        if e.type == "tool_result"
        and e.data["ok"]
        and "app/api/issues.py" in e.data["files_changed"]
    ]
    assert applied, "the in-scope change was not applied in the container"
    [claim] = [e for e in events if e.type == "claim"]
    assert claim.data["claim"] == "done"
    original = subprocess.run(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "show",
            f"{sha}:{app_dir_at(REPO_ROOT, sha)}/app/api/middleware.py",
        ],
        capture_output=True,
        check=True,
    ).stdout
    assert (workspace / "app" / "api" / "middleware.py").read_bytes() == original
    assert 'alias="Idempotency-Key"' in (workspace / "app" / "api" / "issues.py").read_text("utf-8")
