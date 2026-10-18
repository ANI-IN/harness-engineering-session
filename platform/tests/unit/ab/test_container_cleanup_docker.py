"""A timed-out harness run leaves no container behind (real container runtime; pytest -m docker).

The `make show-4` case: harness arm alone, class profile, F4 with its board preview, ended by the
agent time limit. A scripted model client keeps the agent busy, so no model is called. Needs the
agent and referee images (shipharness-agent:1, shipharness-referee:1).
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from shipharness.ab.demo import ABTask, run_ab, section_layers
from shipharness.ab.runtime import build_runtime
from shipharness.config import Settings, profiles
from shipharness.layout import find_repo_root
from shipharness.runner.model import ScriptedModelClient, tool_step

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed"),
]

REPO = find_repo_root(Path(__file__))
DATASET = REPO / "platform" / "datasets" / "teamtrack-features-v1.jsonl"


def _f4_task() -> ABTask:
    for line in DATASET.read_text(encoding="utf-8").splitlines():
        inputs = json.loads(line)["inputs"] if line.strip() else {}
        if inputs.get("feature_id") == "F4" and inputs.get("variant") == "canonical":
            return ABTask.from_dataset_line(json.loads(line))
    raise AssertionError("no canonical F4 task in the dataset")


def _containers_mounting(root: Path) -> list[str]:
    """Names of the containers (running or not) with a bind mount under `root`."""
    ids = subprocess.run(
        ["docker", "ps", "-aq", "--no-trunc"], capture_output=True, text=True, check=True
    ).stdout.split()
    if not ids:
        return []
    found = subprocess.run(["docker", "inspect", *ids], capture_output=True, text=True, check=False)
    containers = json.loads(found.stdout or "[]")  # a container removed meanwhile is skipped
    return [
        c["Name"]
        for c in containers
        if any(str(m.get("Source", "")).startswith(str(root)) for m in c.get("Mounts", []))
    ]


def test_a_timed_out_harness_run_leaves_no_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(
        _env_file=None,
        sandbox_mode="docker",
        langsmith_tracing=False,
        runs_dir=tmp_path / "runs",
        exports_dir=tmp_path / "exports",
        run_timeout_s=20,
    )
    for image in (settings.sandbox_image_agent, settings.sandbox_image_referee):
        inspect = subprocess.run(["docker", "image", "inspect", image], capture_output=True)
        if inspect.returncode != 0:
            pytest.skip(f"image {image} is not built")
    monkeypatch.chdir(tmp_path)  # the cost ledger is written relative to the working directory
    # The class profile sets a 420 s agent time limit (change of 2026-10-17); keep this test's 20 s
    # limit so the scripted agent (60 x 5 s) is still stopped by it.
    monkeypatch.setitem(profiles.PROFILES["class"], "run_timeout_s", 20)
    runtime = build_runtime(settings, project="t", profile="class")
    busy = [tool_step("run", command="sleep 5", timeout_s=None) for _ in range(60)]
    runtime = dataclasses.replace(runtime, client_factory=lambda arm: ScriptedModelClient(busy))
    task = _f4_task()
    deps = runtime.ab_deps(task.checkpoint, reviewer=False, workspace_base=tmp_path / "ws")
    assert deps.preview_factory is not None  # the board preview runs, as in class
    result = run_ab(task, section_layers("demo-4"), deps, arms=("harness",))
    assert result.arms["harness"].result.status == "ABORTED: timeout"
    assert _containers_mounting(tmp_path) == []
