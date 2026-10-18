"""StateLayer (S2): initializer step, Getting up to speed, wrap-up, handoff, resume, exec plan.

The initializer step is deterministic harness code rather than a model session: the files are fixed
by the ticket, and A2's two agents differ only in their initial prompt (F-a-52).
"""

from __future__ import annotations

from typing import Any

from shipharness.harness.base import BaseLayer, LayerContext, register_layer
from shipharness.harness.decisions import HarnessDecision
from shipharness.harness.scope import snapshot
from shipharness.harness.state import lifecycle
from shipharness.harness.state.commit import commit_paths
from shipharness.harness.state.files import move_file, write_file
from shipharness.harness.state.templates import exec_plan_path, initial_files
from shipharness.runner.models import SessionResult, ToolCall


@register_layer
class StateLayer(BaseLayer):
    name = "state"

    def __init__(
        self,
        *,
        feature_description: str | None = None,
        feature_steps: list[str] | None = None,
        handoff_test_timeout_s: int = 300,
        **_ignored: Any,
    ) -> None:
        self.feature_description = feature_description
        self.feature_steps = feature_steps
        self.handoff_test_timeout_s = handoff_test_timeout_s
        self._baseline: snapshot.Snapshot | None = None
        self._baseline_session: int | None = None
        self._last_summary = ""
        self._claim_seen: Any = None
        self._plan_moved = False

    def prepare_workspace(self, ctx: LayerContext) -> list[HarnessDecision]:
        files = initial_files(ctx.spec, self.feature_description, self.feature_steps)
        for rel, data in files.items():
            write_file(ctx.workspace, rel, data)
        commit_paths(
            ctx.sandbox, list(files), f"harness: initializer step for {ctx.spec.feature_id}"
        )
        return [
            HarnessDecision(
                kind="note",
                layer=self.name,
                message="initializer step: " + ", ".join(files),
                paths=list(files),
            )
        ]

    def context_prefix(self, ctx: LayerContext) -> list[str]:
        return [lifecycle.getting_up_to_speed(ctx.spec)]

    def before_tool(self, ctx: LayerContext, call: ToolCall) -> HarnessDecision:
        if self._baseline_session != ctx.session_index:  # first tool call of a session
            self._baseline = snapshot.take(ctx.workspace, max_restore_bytes=0)
            self._baseline_session = ctx.session_index
        return HarnessDecision.allow(self.name)

    def on_wrapup(self, ctx: LayerContext) -> str | None:
        return lifecycle.wrapup_text(ctx.spec)

    def on_session_end(self, ctx: LayerContext, result: SessionResult) -> list[HarnessDecision]:
        changed: list[str] = []
        if self._baseline is not None and self._baseline_session == result.index:
            after = snapshot.take(ctx.workspace, max_restore_bytes=0)
            changed = snapshot.changed(self._baseline, after)
        last = ctx.state.get("last_claim")
        claim = ""
        if isinstance(last, dict) and last != self._claim_seen:
            claim = str(last.get("summary", ""))
            self._claim_seen = dict(last)
        decisions, self._last_summary = lifecycle.session_stop(
            ctx, result, changed, claim, self.handoff_test_timeout_s
        )
        self._baseline, self._baseline_session = None, None
        return decisions

    def on_session_start(self, ctx: LayerContext) -> list[str]:
        return [lifecycle.resume_text(self._last_summary, ctx.phase)]

    def on_phase_end(self, ctx: LayerContext) -> list[HarnessDecision]:
        if self._plan_moved or not ctx.state.get("scope.passes_set"):
            return []
        active = exec_plan_path(ctx.spec.feature_id, "active")
        completed = exec_plan_path(ctx.spec.feature_id, "completed")
        if not move_file(ctx.workspace, active, completed):
            return []
        self._plan_moved = True
        commit_paths(
            ctx.sandbox, ["docs/exec-plans"], f"harness: {ctx.spec.feature_id} exec plan completed"
        )
        return [
            HarnessDecision(
                kind="note",
                layer=self.name,
                message=f"exec plan moved to {completed} ({ctx.spec.feature_id} passes)",
                paths=[active, completed],
            )
        ]
