"""Every container an A/B starts (arm, referee, board preview) is stopped by the time run_ab
returns or raises, however the arm ends. Bug 2026-10-17: after `make show-4` (harness arm alone,
class profile, F4, ended by the agent time limit) the harness arm's board preview container was
still running an hour later: its F4 conflict capture outlasted the 10 s join, and the process
exited before the preview thread reached its own stop."""

from __future__ import annotations

import dataclasses
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from shipharness.ab import demo
from shipharness.ab.demo import ABTask, run_ab
from shipharness.ab.runtime import PreviewHandle
from shipharness.config.profiles import apply_profile
from shipharness.cost import Usage
from shipharness.events import EventBus
from shipharness.harness.base import LayerContext
from shipharness.harness.decisions import HarnessDecision
from shipharness.runner.model import tool_step
from shipharness.runner.models import AgentRunSpec
from shipharness.sandbox import FakeSandbox

from .test_demo import LINE, Clients, FakeInstructions, make_deps
from .test_referee import Factory, all_green


class Box(FakeSandbox):
    """stop() also ends an exec waiting on the container, as `docker rm -f` does."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.removed = threading.Event()

    def stop(self) -> None:
        super().stop()
        self.removed.set()


class SlowConflictPreview:
    """A board preview whose last capture (the F4 two-tab conflict view) outlasts the join."""

    def __init__(self, sandbox: Box) -> None:
        self.sandbox = sandbox

    def start_server(self) -> None:
        return None

    def run(self, stop: threading.Event) -> int:
        stop.wait()
        return 0

    def capture(self, view: str = "board") -> None:
        self.sandbox.removed.wait(30)  # `docker exec` returns once the container is gone


class SlowLayer(FakeInstructions):
    def prepare_workspace(self, ctx: LayerContext) -> list[HarnessDecision]:
        time.sleep(0.05)  # past HARNESS_TIMEOUT_S
        return super().prepare_workspace(ctx)


class BrokenLayer(FakeInstructions):
    def prepare_workspace(self, ctx: LayerContext) -> list[HarnessDecision]:
        raise RuntimeError("gate baseline failed")


class Broken(Box):
    def start(self) -> str:
        raise RuntimeError("docker run failed")


PRICEY = Usage(input_tokens=1000, output_tokens=500_000)

# How the arm ends -> (settings overrides, Clients kwargs, layer class, arm sandbox class, status)
ENDINGS: dict[str, tuple[dict[str, Any], dict[str, Any], type, type, str | None]] = {
    "agent-time-limit": ({"run_timeout_s": 0}, {}, FakeInstructions, Box, "ABORTED: timeout"),
    "harness-time-limit": ({"harness_timeout_s": 0.001}, {}, SlowLayer, Box, "ABORTED: timeout"),
    "cost-cap": (
        {},
        {
            arm: [tool_step("list_dir", path=".", depth=None, usage=PRICEY)]
            for arm in ("bare", "harness")
        },
        FakeInstructions,
        Box,
        "ABORTED: cap",
    ),
    "sandbox-error": ({}, {}, FakeInstructions, Broken, "ERROR"),
    "harness-work-raises": ({}, {}, BrokenLayer, Box, None),
    "completed": ({}, {}, FakeInstructions, Box, "completed"),
}


def run_tracked(
    course_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ending: str,
    arms: tuple[str, ...],
    **deps_kw: Any,
) -> tuple[demo.ABResult | BaseException, list[Box], list[Box], list[Box]]:
    """run_ab on the class profile, every container recorded: (result or exception, arm boxes,
    referee boxes, preview boxes)."""
    monkeypatch.setattr(demo, "PREVIEW_JOIN_S", 0.2, raising=False)
    overrides, clients_kw, layer, arm_box, _status = ENDINGS[ending]
    agent: list[Box] = []
    previews: list[Box] = []
    referee = Factory(all_green())
    referee_boxes: list[Box] = []

    def sandbox_factory(arm: str, ws: Path, bus: EventBus, run_id: str) -> Box:
        agent.append(arm_box())
        return agent[-1]

    def referee_factory(build: Path, mounts: list[Any], arm: str) -> Box:
        box = Box(referee(build, mounts, arm).script)
        referee_boxes.append(box)
        return box

    def preview_factory(arm: str, bus: EventBus, spec: AgentRunSpec) -> PreviewHandle:
        box = Box()
        box.start()  # as the runtime's preview factory does
        previews.append(box)
        return PreviewHandle(SlowConflictPreview(box), box, capture_conflict=True)  # type: ignore[arg-type]

    deps = make_deps(
        course_repo,
        tmp_path,
        Clients(**clients_kw),
        sandbox_factory=sandbox_factory,
        referee_sandbox_factory=referee_factory,
        preview_factory=preview_factory,
        layer_registry={"instructions": layer},
        profile="class",
        **deps_kw,
    )
    deps.settings = apply_profile(deps.settings, "class").model_copy(update=overrides)
    task = dataclasses.replace(ABTask.from_dataset_line(LINE), feature_id="F4")
    try:
        layers = frozenset({"instructions"})
        outcome: demo.ABResult | BaseException = run_ab(task, layers, deps, arms=arms)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001 - the test checks the containers either way
        outcome = exc
    return outcome, agent, referee_boxes, previews


def leaked(*groups: list[Box]) -> list[Box]:
    return [box for group in groups for box in group if box.started and not box.stopped]


@pytest.mark.parametrize("arms", [("harness",), ("bare", "harness")], ids=["harness-only", "ab"])
@pytest.mark.parametrize("ending", list(ENDINGS))
def test_no_container_outlives_run_ab(
    course_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ending: str,
    arms: tuple[str, ...],
) -> None:
    outcome, agent, referee, previews = run_tracked(
        course_repo, tmp_path, monkeypatch, ending, arms
    )
    assert not isinstance(outcome, BaseException), outcome
    expected = ENDINGS[ending][4]
    if expected is not None:
        assert outcome.arms["harness"].result.status == expected
    assert len(previews) == len(arms)
    assert referee, "the referee ran in a container"
    assert leaked(agent, referee, previews) == []


def test_the_show_4_leak_preview_is_stopped_on_the_agent_time_limit(
    course_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exact 2026-10-17 case: harness arm alone, class profile, F4, agent time limit."""
    outcome, _agent, _referee, [preview] = run_tracked(
        course_repo, tmp_path, monkeypatch, "agent-time-limit", ("harness",)
    )
    assert not isinstance(outcome, BaseException), outcome
    assert outcome.arms["harness"].result.status == "ABORTED: timeout"
    assert preview.stopped  # before the fix: still running when run_ab returned


def test_containers_are_stopped_when_run_ab_raises(
    course_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_client(arm: str) -> Any:
        raise RuntimeError("no model client")

    outcome, agent, referee, previews = run_tracked(
        course_repo, tmp_path, monkeypatch, "completed", ("harness",), client_factory=no_client
    )
    assert isinstance(outcome, RuntimeError)
    assert previews and agent
    # The referee baseline thread finishes (and stops its container) before run_ab raises.
    assert referee and leaked(agent, referee, previews) == []


def test_preview_handle_close_stops_the_container() -> None:
    box = Box()
    box.start()
    handle = PreviewHandle(SlowConflictPreview(box), box, capture_conflict=False)  # type: ignore[arg-type]
    handle.close()
    assert box.stopped
