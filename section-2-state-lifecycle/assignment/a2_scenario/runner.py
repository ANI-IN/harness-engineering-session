"""Run one scenario: the real runner loop, a state layer, the test stand-in agent, and LocalSandbox.

LocalSandbox is UNSANDBOXED (commands run on the host with timeouts); that is safe here because
the only commands are the test stand-in agent's fixed ones and the state layer's own. No model,
network, Docker, or keys are used, and the cost tracker only sees the scripted token counts.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import traceback
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from a2_scenario.fixture import make_repo
from a2_scenario.literal_agent import LiteralAgent
from a2_scenario.scenarios import Scenario
from shipharness.config import DEFAULT_PRICES_FILE, Prices, Settings
from shipharness.cost import Caps, CostTracker
from shipharness.events import EventBus
from shipharness.harness.base import BaseLayer, Harness, LayerContext
from shipharness.harness.decisions import HarnessDecision
from shipharness.runner.loop import RunOptions, run_agent
from shipharness.runner.models import AgentRunResult, AgentRunSpec, SessionResult, ToolCall
from shipharness.sandbox import LocalSandbox, default_policy
from shipharness.tracing import NullTracer

LayerFactory = Callable[..., BaseLayer]
PRODUCT_PATHS = ("app", "migrations", "tests")


@dataclass
class ScenarioRun:
    scenario: Scenario
    workspace: Path
    events: Path
    run_id: str
    result: AgentRunResult
    agent: LiteralAgent
    start_tree: str = ""
    stop_trees: dict[int, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def tree(ws: Path) -> str:
    """Git tree id of the working tree (tracked and untracked, minus .gitignore), without touching
    HEAD or the real index: a temporary index file takes the snapshot."""
    index = ws / ".git" / "a2-tree-index"
    env = {**os.environ, "GIT_INDEX_FILE": str(index)}
    try:
        subprocess.run(["git", "add", "-A"], cwd=ws, env=env, check=True, capture_output=True)
        done = subprocess.run(
            ["git", "write-tree"], cwd=ws, env=env, check=True, capture_output=True, text=True
        )
        return done.stdout.strip()
    finally:
        index.unlink(missing_ok=True)


class _Guarded(BaseLayer):
    """Delegates every hook to the learner's layer and keeps the traceback of any exception (the
    runner turns an exception into status ERROR without one)."""

    name = "state"

    def __init__(self, inner: BaseLayer, errors: list[str]) -> None:
        self.inner = inner
        self.errors = errors

    def _call(self, hook: str, *args: Any) -> Any:
        try:
            return getattr(self.inner, hook)(*args)
        except Exception:
            self.errors.append(f"{hook}: {traceback.format_exc()}")
            raise

    def prepare_workspace(self, ctx: LayerContext) -> list[HarnessDecision]:
        return self._call("prepare_workspace", ctx)

    def context_prefix(self, ctx: LayerContext) -> list[str]:
        return self._call("context_prefix", ctx)

    def before_tool(self, ctx: LayerContext, call: ToolCall) -> HarnessDecision:
        return self._call("before_tool", ctx, call)

    def after_tool(self, ctx: LayerContext, call: ToolCall, result: Any) -> list[HarnessDecision]:
        return self._call("after_tool", ctx, call, result)

    def on_wrapup(self, ctx: LayerContext) -> str | None:
        return self._call("on_wrapup", ctx)

    def on_session_end(self, ctx: LayerContext, result: SessionResult) -> list[HarnessDecision]:
        return self._call("on_session_end", ctx, result)

    def on_session_start(self, ctx: LayerContext) -> list[str]:
        return self._call("on_session_start", ctx)

    def on_claim_done(self, ctx: LayerContext) -> HarnessDecision | None:
        return self._call("on_claim_done", ctx)

    def on_phase_end(self, ctx: LayerContext) -> list[HarnessDecision]:
        return self._call("on_phase_end", ctx)


class _RecordingHarness(Harness):
    """Snapshots the working tree when each session starts and when it stops (before the state
    layer writes anything), so the measures can split the work by session."""

    def __init__(self, layers: list[BaseLayer], ws: Path) -> None:
        super().__init__(layers)
        self.ws = ws
        self.start_trees: dict[int, str] = {}
        self.stop_trees: dict[int, str] = {}

    def context_prefix(self, ctx: LayerContext) -> list[str]:
        self.start_trees.setdefault(ctx.session_index, tree(self.ws))
        return super().context_prefix(ctx)

    def on_session_end(self, ctx: LayerContext, result: SessionResult) -> list[HarnessDecision]:
        self.stop_trees[result.index] = tree(self.ws)
        return super().on_session_end(ctx, result)


SCENARIO_ENV = {
    "PYTHONDONTWRITEBYTECODE": "1",  # no __pycache__ in the workspace
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",  # the course venv's pytest plugins add seconds per run
}


@contextlib.contextmanager
def scenario_env() -> Iterator[None]:
    old = {key: os.environ.get(key) for key in SCENARIO_ENV}
    os.environ.update(SCENARIO_ENV)
    try:
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def run_scenario(factory: LayerFactory, scenario: Scenario, root: Path) -> ScenarioRun:
    """Run `scenario` in a new mini repository under `root` (which must be outside the course
    repository, so pytest and Alembic in the workspace never pick up the course's config)."""
    root.mkdir(parents=True, exist_ok=True)
    ws = make_repo(root / "ws")
    feature = scenario.feature
    run_id = f"a2-{scenario.name}"
    errors: list[str] = []
    spec = AgentRunSpec(
        run_id=run_id,
        arm="harness",
        feature_id=feature.id,
        checkpoint="a2-mini",
        ticket_text=feature.ticket(),
        model="gpt-6-luna",
        reasoning_effort="low",
        layers=frozenset({"state"}),
        phases=("build",),
        session_budget=list(scenario.budgets),
        max_output_tokens=200,
        cost_limit_usd=5.0,
        workspace=ws,
    )
    agent = LiteralAgent(feature, scenario.behaviours)
    events = root / "events.jsonl"
    with scenario_env():
        try:
            layer = factory(feature_description=feature.title, feature_steps=feature.step_lines())
        except Exception:
            errors.append(f"creating the layer: {traceback.format_exc()}")
            raise
        harness = _RecordingHarness([_Guarded(layer, errors)], ws)
        tracker = CostTracker(
            Prices.load(DEFAULT_PRICES_FILE),
            Caps(run=5.0, review=1.0, session=50.0, batch=50.0, experiment=50.0),
            root / "ledger.jsonl",
            session_id=run_id,
        )
        sandbox = LocalSandbox(
            default_policy(Settings(_env_file=None)), ws, None, run_id, "harness"
        )
        options = RunOptions(
            wrapup_turns=scenario.wrapup_turns,
            run_timeout_s=900,
            sleep=lambda _s: None,
            tool_log_dir=root / "tool-logs",
            diff_path=root / "diff.patch",
        )
        with EventBus(events, ab_id=None) as bus:
            result = run_agent(spec, harness, sandbox, bus, tracker, NullTracer(), agent, options)
    return ScenarioRun(
        scenario=scenario,
        workspace=ws,
        events=events,
        run_id=run_id,
        result=result,
        agent=agent,
        start_tree=harness.start_trees.get(1, ""),
        stop_trees=dict(harness.stop_trees),
        errors=errors,
    )
