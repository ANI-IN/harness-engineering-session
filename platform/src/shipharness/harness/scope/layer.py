"""ScopeLayer (S3): feature_list.json is the only scope; one feature; allowed paths per phase.

- `apply_patch` touching a path outside the phase's allowed paths, or feature_list.json, is
  rejected before anything is written (`block`; the agent sees `BLOCKED: <reason>`).
- After every `run`, `run_visible_tests`, and applied patch, the workspace is compared with a byte
  snapshot taken just before the call; changes outside the allowed paths are restored from the
  snapshot (new files deleted) and reported as `revert` decisions. No git is involved (I-7).
- `passes` is set only by `status.update_status`, with evidence.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from shipharness.datasets.names import feature_label
from shipharness.harness.base import BaseLayer, LayerContext, register_layer
from shipharness.harness.decisions import HarnessDecision
from shipharness.harness.scope import snapshot
from shipharness.harness.scope.features import (
    FEATURE_LIST,
    FEATURE_SCHEMA,
    build_feature,
    write_feature_list,
)
from shipharness.harness.scope.guard import (
    FEATURE_LIST_REASON,
    HARNESS_ONLY,
    PathRules,
    check_paths,
    patch_targets,
)
from shipharness.harness.scope.status import update_status
from shipharness.harness.state.commit import commit_paths
from shipharness.runner.models import Phase, SessionResult, ToolCall, ToolResult

WATCHED_TOOLS = frozenset({"apply_patch", "run", "run_visible_tests"})


@register_layer
class ScopeLayer(BaseLayer):
    name = "scope"

    def __init__(
        self,
        *,
        feature_category: str = "feature",
        feature_description: str | None = None,
        feature_steps: list[str] | None = None,
        now: Callable[[], datetime] | None = None,
        status_test_timeout_s: int = 300,
        **_ignored: Any,
    ) -> None:
        self.feature_category = feature_category
        self.feature_description = feature_description
        self.feature_steps = feature_steps
        self.now = now or (lambda: datetime.now(UTC))
        self.status_test_timeout_s = status_test_timeout_s
        self._feature: dict[str, Any] | None = None
        self._baseline: tuple[str, snapshot.Snapshot] | None = None

    # -- helpers ---------------------------------------------------------------------------------

    def feature(self, ctx: LayerContext) -> dict[str, Any]:
        if self._feature is None:
            self._feature = build_feature(
                ctx.spec, self.feature_category, self.feature_description, self.feature_steps
            )
        return self._feature

    @staticmethod
    def rules(ctx: LayerContext, phase: Phase | None = None) -> PathRules:
        current = phase or ctx.phase
        allowed = ctx.spec.allowed_paths.get(current)
        return PathRules(
            phase=current,
            allowed=list(allowed) if allowed is not None else None,
            state_files="state" in ctx.spec.layers,
        )

    @staticmethod
    def _decisions(
        kind: str, refused: dict[str, list[str]], ctx: LayerContext, verb: str
    ) -> list[HarnessDecision]:
        out = []
        for reason, paths in refused.items():
            harness_only = paths[0] in HARNESS_ONLY
            message = reason if harness_only else f"{', '.join(paths)}: {reason}"
            out.append(
                HarnessDecision(
                    kind=kind,  # type: ignore[arg-type]
                    layer="scope",
                    message=f"{message}; {verb}",
                    paths=paths,
                    data={"phase": ctx.phase},
                )
            )
        return out

    # -- hooks -----------------------------------------------------------------------------------

    def prepare_workspace(self, ctx: LayerContext) -> list[HarnessDecision]:
        write_feature_list(ctx.workspace, self.feature(ctx))
        commit_paths(
            ctx.sandbox,
            [FEATURE_LIST, FEATURE_SCHEMA],
            f"harness: feature list for {ctx.spec.feature_id}",
        )
        decisions = [
            HarnessDecision(
                kind="note",
                layer="scope",
                message=f"feature_list.json written with {ctx.spec.feature_id} (passes: false)",
                paths=[FEATURE_LIST, FEATURE_SCHEMA],
            )
        ]
        for phase in ctx.spec.phases:
            if phase not in ctx.spec.allowed_paths:
                decisions.append(
                    HarnessDecision(
                        kind="note",
                        layer="scope",
                        message=f"no allowed paths given for the {phase} phase; "
                        "only feature_list.json is protected in that phase",
                    )
                )
        return decisions

    def context_prefix(self, ctx: LayerContext) -> list[str]:
        feature = self.feature(ctx)
        lines = [
            "## Scope",
            f"This task has one feature: {feature_label(feature['id'])} "
            f"({feature['description']}). "
            "Work on only this one feature in this session.",
            "The feature list is feature_list.json (read it with read_file). "
            f"{FEATURE_LIST_REASON}: it sets the passes field itself, with evidence, after you "
            'call finish with claim="done" and the checks pass. It is unacceptable to remove or '
            "edit tests because this could lead to missing or buggy functionality.",
            "Files you may change in each phase:",
        ]
        for phase in ctx.spec.phases:
            allowed = ctx.spec.allowed_paths.get(phase)
            listed = ", ".join(allowed) if allowed is not None else "(no list given)"
            lines.append(f"- {phase}: {listed}")
        if "state" in ctx.spec.layers:
            lines.append("- any phase: progress.md, session-handoff.md, docs/exec-plans/**")
        lines.append(
            "A patch that touches any other file is rejected before it is applied. Changes that "
            "a command makes to any other file are reverted after it runs."
        )
        return ["\n".join(lines)]

    def before_tool(self, ctx: LayerContext, call: ToolCall) -> HarnessDecision:
        if call.name not in WATCHED_TOOLS:
            return HarnessDecision.allow(self.name)
        if call.name == "apply_patch":
            targets = patch_targets(str(call.arguments.get("patch", "")))
            refused = check_paths(self.rules(ctx), targets)
            if refused:
                parts = self._decisions("block", refused, ctx, "patch not applied")
                return HarnessDecision(
                    kind="block",
                    layer=self.name,
                    message=" | ".join(d.message for d in parts),
                    paths=sorted({p for d in parts for p in d.paths}),
                    data={"phase": ctx.phase},
                )
        self._baseline = (call.call_id, snapshot.take(ctx.workspace))
        return HarnessDecision.allow(self.name)

    def after_tool(
        self, ctx: LayerContext, call: ToolCall, result: ToolResult
    ) -> list[HarnessDecision]:
        baseline, self._baseline = self._baseline, None
        if call.name not in WATCHED_TOOLS or baseline is None or baseline[0] != call.call_id:
            return []
        before = baseline[1]
        changed = snapshot.changed(before, snapshot.take(ctx.workspace))
        refused = check_paths(self.rules(ctx), changed)
        if not refused:
            return []
        problems = snapshot.restore(ctx.workspace, before, [p for v in refused.values() for p in v])
        decisions = self._decisions("revert", refused, ctx, "change reverted")
        if problems:
            decisions[-1] = decisions[-1].model_copy(
                update={"data": {**decisions[-1].data, "problems": problems}}
            )
        return decisions

    def on_session_end(self, ctx: LayerContext, result: SessionResult) -> list[HarnessDecision]:
        return update_status(
            ctx, result, self.feature(ctx), self.now, test_timeout_s=self.status_test_timeout_s
        )
