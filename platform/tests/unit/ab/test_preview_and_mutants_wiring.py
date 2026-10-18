"""Integration wiring: board previews per arm in run_ab, and referee-set mutants by mutant set."""

from __future__ import annotations

import dataclasses
import threading
from pathlib import Path
from typing import Any

import pytest

from shipharness.ab import runtime as runtime_module
from shipharness.ab.demo import ABTask, run_ab
from shipharness.ab.mutants import load_referee_mutants
from shipharness.config import Settings
from shipharness.events import EventBus
from shipharness.layout import find_repo_root
from shipharness.runner.models import AgentRunSpec

from .test_demo import LINE, Clients, make_deps

REPO = find_repo_root(Path(__file__))


# --- referee-set mutants ---------------------------------------------------------------------


def test_load_referee_mutants_by_module_name() -> None:
    mutants = load_referee_mutants("app.services.issues", REPO)
    assert mutants
    assert {m.set for m in mutants} == {"referee"}


def test_load_referee_mutants_accepts_several_names_and_paths() -> None:
    one = load_referee_mutants("app.services.issues", REPO)
    two = load_referee_mutants(
        "app.services.issues, teamtrack/mutants/app.repositories.issues.jsonl", REPO
    )
    assert len(two) > len(one)
    assert {m.set for m in two} == {"referee"}


def test_unknown_mutant_set_is_an_error() -> None:
    with pytest.raises(ValueError, match="no-such-module"):
        load_referee_mutants("no-such-module", REPO)


def test_empty_mutant_set_loads_nothing() -> None:
    assert load_referee_mutants("", REPO) == []


def test_run_ab_loads_referee_mutants_for_the_task(course_repo: Path, tmp_path: Path) -> None:
    expected = load_referee_mutants("app.services.issues", REPO)
    deps = make_deps(course_repo, tmp_path, Clients(), mutant_source_repo=REPO)
    task = dataclasses.replace(ABTask.from_dataset_line(LINE), mutant_set="app.services.issues")
    result = run_ab(task, frozenset({"instructions"}), deps)
    for arm_run in result.arms.values():
        assert arm_run.record.mutants_total == len(expected)  # all survive: no shipped tests


def test_missing_mutant_set_scores_zero_instead_of_aborting(
    course_repo: Path, tmp_path: Path
) -> None:
    deps = make_deps(course_repo, tmp_path, Clients(), mutant_source_repo=REPO)
    task = dataclasses.replace(ABTask.from_dataset_line(LINE), mutant_set="not-built-yet")
    result = run_ab(task, frozenset({"instructions"}), deps)
    assert {a.record.mutants_total for a in result.arms.values()} == {0}


# --- board previews --------------------------------------------------------------------------


class RecordingPreview:
    instances: list[RecordingPreview] = []

    def __init__(self, arm: str, spec: AgentRunSpec) -> None:
        self.arm, self.spec = arm, spec
        self.calls: list[str] = []
        self.stopped = False
        RecordingPreview.instances.append(self)

    def start_server(self) -> None:
        self.calls.append("start_server")

    def run(self, stop: threading.Event) -> int:
        self.calls.append("run")
        self.stopped = stop.wait(5)
        return 0


def test_run_ab_starts_one_preview_per_arm_with_its_spec(course_repo: Path, tmp_path: Path) -> None:
    RecordingPreview.instances.clear()

    def factory(arm: str, bus: EventBus, spec: AgentRunSpec) -> RecordingPreview:
        return RecordingPreview(arm, spec)

    deps = make_deps(course_repo, tmp_path, Clients(), preview_factory=factory)
    run_ab(ABTask.from_dataset_line(LINE), frozenset({"instructions"}), deps)
    arms = {p.arm for p in RecordingPreview.instances}
    assert arms == {"bare", "harness"}
    for preview in RecordingPreview.instances:
        assert preview.calls[0] == "start_server"
        assert preview.spec.arm == preview.arm


def test_runtime_previews_use_the_referee_image_and_the_arm_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    made: list[dict[str, Any]] = []
    policies: list[Any] = []

    class FakeDocker:
        def __init__(
            self,
            policy: Any,
            image: str,
            workspace: Path,
            bus: Any,
            run_id: str,
            arm: str,
            **kw: Any,
        ) -> None:
            made.append({"image": image, "workspace": workspace, "arm": arm})
            policies.append(policy)

        def start(self) -> str:
            return "c1"

        def stop(self) -> None:
            return None

    monkeypatch.setattr(runtime_module, "DockerSandbox", FakeDocker)
    settings = Settings(
        _env_file=None,
        sandbox_mode="docker",
        runs_dir=tmp_path / "runs",
        exports_dir=tmp_path / "exports",
    )
    deps = runtime_module.build_runtime(settings, project="t").ab_deps(None)
    assert deps.preview_factory is not None
    spec = AgentRunSpec(
        run_id="r-1",
        arm="bare",
        feature_id="F4",
        checkpoint="m1-s4-start",
        ticket_text="t",
        model="m",
        reasoning_effort="low",
        workspace=tmp_path / "ws",
    )
    with EventBus(tmp_path / "runs" / "ab-1" / "events.jsonl", ab_id="ab-1") as bus:
        handle = deps.preview_factory("bare", bus, spec)
    assert made == [
        {"image": settings.sandbox_image_referee, "workspace": tmp_path / "ws", "arm": "bare"}
    ]
    assert handle.preview.run_dir == tmp_path / "runs" / "ab-1"
    assert handle.capture_conflict is True  # F4 shows the two-tab edit conflict
    # The preview only reads the arm workspace: it can never change what the arm ships.
    assert [p.workspace_read_only for p in policies] == [True]


def test_no_previews_when_unsandboxed(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, sandbox_mode="none", runs_dir=tmp_path / "runs")
    deps = runtime_module.build_runtime(settings, project="t").ab_deps(None)
    assert deps.preview_factory is None


# --- swap test, replay, and experiments use the task's mutant set too ---------------------------


def test_swap_and_replay_referee_loads_the_task_mutant_set(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from shipharness.ab.recorded import RecordedDeps, _referee

    task = dataclasses.replace(ABTask.from_dataset_line(LINE), mutant_set="app.services.issues")
    deps = RecordedDeps(
        course_repo=REPO,
        referee_sandbox_factory=lambda *a: None,  # type: ignore[arg-type,return-value]
        runs_dir=tmp_path / "runs",
        exports_dir=tmp_path / "exports",
    )
    ab = SimpleNamespace(task=task, seed=1, export_ref=lambda: None)
    referee = _referee(ab, deps, tmp_path, None)  # type: ignore[arg-type]
    assert len(referee.deps.mutants) == len(load_referee_mutants("app.services.issues", REPO))


def test_experiment_referee_loads_the_task_mutant_set(course_repo: Path, tmp_path: Path) -> None:
    from shipharness.ab.experiments import ArmExperiment, ExperimentPlan

    deps = make_deps(course_repo, tmp_path, Clients(), mutant_source_repo=REPO)
    plan = ExperimentPlan(dataset="d", k=1, harness_layers=frozenset())
    task = dataclasses.replace(ABTask.from_dataset_line(LINE), mutant_set="app.services.issues")
    referee = ArmExperiment("bare", plan, deps, [])._referee(task)
    assert len(referee.deps.mutants) == len(load_referee_mutants("app.services.issues", REPO))


# --- failure paths: a broken preview or referee container never loses the run ------------------


def test_a_preview_that_fails_to_start_does_not_stop_the_ab(
    course_repo: Path, tmp_path: Path
) -> None:
    def factory(arm: str, bus: EventBus, spec: AgentRunSpec) -> Any:
        raise RuntimeError("container did not start")

    deps = make_deps(course_repo, tmp_path, Clients(), preview_factory=factory)
    result = run_ab(ABTask.from_dataset_line(LINE), frozenset({"instructions"}), deps)
    assert set(result.arms) == {"bare", "harness"}


def test_previews_are_stopped_when_an_arm_raises(course_repo: Path, tmp_path: Path) -> None:
    RecordingPreview.instances.clear()

    def factory(arm: str, bus: EventBus, spec: AgentRunSpec) -> RecordingPreview:
        return RecordingPreview(arm, spec)

    def broken_clients(arm: str) -> Any:
        raise RuntimeError("no model client")

    deps = make_deps(course_repo, tmp_path, Clients(), preview_factory=factory)
    deps.client_factory = broken_clients
    with pytest.raises(RuntimeError):
        run_ab(ABTask.from_dataset_line(LINE), frozenset({"instructions"}), deps)
    assert RecordingPreview.instances
    assert all(p.stopped for p in RecordingPreview.instances)


def test_preview_handle_stops_its_container_when_the_server_fails() -> None:
    class Preview:
        def start_server(self) -> None:
            raise RuntimeError("no /health within 60 s")

    class Box:
        stopped = False

        def stop(self) -> None:
            Box.stopped = True

    handle = runtime_module.PreviewHandle(Preview(), Box(), capture_conflict=False)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError):
        handle.start_server()
    assert Box.stopped is True


def test_referee_container_that_fails_to_start_gives_a_verdict_not_a_crash(
    course_repo: Path, tmp_path: Path
) -> None:
    from shipharness.sandbox import FakeSandbox

    class NoStart(FakeSandbox):
        def start(self) -> str:
            raise RuntimeError("docker: daemon not running")

    deps = make_deps(course_repo, tmp_path, Clients(), referee_sandbox_factory=lambda *a: NoStart())
    result = run_ab(ABTask.from_dataset_line(LINE), frozenset({"instructions"}), deps)
    assert {a.record.passed_primary for a in result.arms.values()} == {False}
    assert (result.run_dir / "ab.json").is_file()
