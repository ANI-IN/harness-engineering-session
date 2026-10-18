"""Layer hook interface and composition. The bare arm is Harness([])."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, get_args

from shipharness.events import EventBus
from shipharness.harness.decisions import HarnessDecision, LayerName
from shipharness.runner.models import AgentRunSpec, Phase, SessionResult, ToolCall, ToolResult
from shipharness.sandbox.base import Sandbox

LAYER_ORDER: tuple[LayerName, ...] = get_args(LayerName)
_REGISTRY: dict[str, type[BaseLayer]] = {}


@dataclass
class LayerContext:
    """Mutable view of the run passed to every hook."""

    spec: AgentRunSpec
    phase: Phase
    session_index: int
    turn: int
    workspace: Path
    sandbox: Sandbox
    bus: EventBus | None = None
    state: dict[str, Any] = field(default_factory=dict)  # per-run scratch space for layers
    # Seconds of harness work left under HARNESS_TIMEOUT_S (None = no limit). The loop sets it;
    # layers fit their own commands (gate, baseline) inside it.
    time_left: Callable[[], float | None] = field(default=lambda: None)


class BaseLayer:
    """No-op implementation of every hook. Layers override what they need."""

    name: ClassVar[LayerName]

    def prepare_workspace(self, ctx: LayerContext) -> list[HarnessDecision]:
        return []

    def context_prefix(self, ctx: LayerContext) -> list[str]:
        return []

    def before_tool(self, ctx: LayerContext, call: ToolCall) -> HarnessDecision:
        return HarnessDecision.allow(self.name)

    def after_tool(
        self, ctx: LayerContext, call: ToolCall, result: ToolResult
    ) -> list[HarnessDecision]:
        return []

    def on_wrapup(self, ctx: LayerContext) -> str | None:
        return None

    def on_session_end(self, ctx: LayerContext, result: SessionResult) -> list[HarnessDecision]:
        return []

    def on_session_start(self, ctx: LayerContext) -> list[str]:
        return []

    def on_claim_done(self, ctx: LayerContext) -> HarnessDecision | None:
        return None

    def on_phase_end(self, ctx: LayerContext) -> list[HarnessDecision]:
        return []


def register_layer(cls: type[BaseLayer]) -> type[BaseLayer]:
    """Class decorator used by layer modules to make a layer available by name."""
    _REGISTRY[cls.name] = cls
    return cls


def parse_layers(value: str) -> frozenset[LayerName]:
    """`none`, `all`, a comma list (`state,scope`), or removals from all (`-verify,-state`)."""
    text = value.strip().lower()
    if text in ("", "none"):
        return frozenset()
    if text == "all":
        return frozenset(LAYER_ORDER)
    items = [item.strip() for item in text.split(",") if item.strip()]
    removals = [item[1:] for item in items if item.startswith("-")]
    additions = [item for item in items if not item.startswith("-")]
    unknown = [name for name in removals + additions if name not in LAYER_ORDER]
    if unknown:
        raise ValueError(f"unknown layer(s): {', '.join(unknown)}; choose from {LAYER_ORDER}")
    if removals and additions:
        raise ValueError("use either a list of layers or removals from all, not both")
    if removals:
        return frozenset(name for name in LAYER_ORDER if name not in removals)
    return frozenset(additions)  # type: ignore[arg-type]


class Harness:
    """Runs the hooks of its layers in the fixed order instructions, state, scope, verify."""

    def __init__(self, layers: Sequence[BaseLayer]) -> None:
        self.layers = sorted(layers, key=lambda layer: LAYER_ORDER.index(layer.name))

    @classmethod
    def from_names(
        cls,
        names: frozenset[LayerName],
        registry: Mapping[str, type[BaseLayer]] | None = None,
        **kwargs: Any,
    ) -> Harness:
        if registry is None:
            # The layer modules register themselves on import; the live path (CLI, A/B, experiments)
            # never imports them, so load them here before resolving names.
            import shipharness.harness.layers  # noqa: F401
        available = _REGISTRY if registry is None else registry
        missing = [name for name in names if name not in available]
        if missing:
            raise ValueError(f"layer(s) not available yet: {', '.join(sorted(missing))}")
        return cls([available[name](**kwargs) for name in names])

    @property
    def names(self) -> frozenset[LayerName]:
        return frozenset(layer.name for layer in self.layers)

    # -- publishing ----------------------------------------------------------------------------

    @staticmethod
    def _publish(ctx: LayerContext, decision: HarnessDecision) -> HarnessDecision:
        if ctx.bus is None or decision.kind == "allow":
            return decision
        run_id, arm = ctx.spec.run_id, ctx.spec.arm
        ctx.bus.publish("harness_decision", decision, run_id=run_id, arm=arm)
        if decision.kind in ("block", "revert"):
            ctx.bus.publish(
                "blocked",
                {
                    "phase": ctx.phase,
                    "paths": decision.paths,
                    "action": "reject_patch" if decision.kind == "block" else "revert",
                    "reason": decision.message,
                },
                run_id=run_id,
                arm=arm,
            )
        return decision

    def _publish_all(
        self, ctx: LayerContext, decisions: list[HarnessDecision]
    ) -> list[HarnessDecision]:
        return [self._publish(ctx, d) for d in decisions]

    # -- hooks ------------------------------------------------------------------------------------

    def prepare_workspace(self, ctx: LayerContext) -> list[HarnessDecision]:
        return self._publish_all(
            ctx, [d for layer in self.layers for d in layer.prepare_workspace(ctx)]
        )

    def context_prefix(self, ctx: LayerContext) -> list[str]:
        return [block for layer in self.layers for block in layer.context_prefix(ctx) if block]

    def before_tool(self, ctx: LayerContext, call: ToolCall) -> HarnessDecision:
        for layer in self.layers:
            decision = layer.before_tool(ctx, call)
            if decision.kind == "block":
                return self._publish(ctx, decision)
        return HarnessDecision.allow()

    def after_tool(
        self, ctx: LayerContext, call: ToolCall, result: ToolResult
    ) -> list[HarnessDecision]:
        return self._publish_all(
            ctx, [d for layer in self.layers for d in layer.after_tool(ctx, call, result)]
        )

    def wrapup_text(self, ctx: LayerContext) -> str | None:
        parts = [text for layer in self.layers if (text := layer.on_wrapup(ctx))]
        return "\n\n".join(parts) if parts else None

    def on_session_end(self, ctx: LayerContext, result: SessionResult) -> list[HarnessDecision]:
        return self._publish_all(
            ctx, [d for layer in self.layers for d in layer.on_session_end(ctx, result)]
        )

    def on_session_start(self, ctx: LayerContext) -> list[str]:
        return [block for layer in self.layers for block in layer.on_session_start(ctx) if block]

    def on_claim_done(self, ctx: LayerContext) -> HarnessDecision | None:
        verdicts = [d for layer in self.layers if (d := layer.on_claim_done(ctx)) is not None]
        for decision in verdicts:
            if decision.kind == "gate_fail":
                return self._publish(ctx, decision)
        return self._publish(ctx, verdicts[-1]) if verdicts else None

    def on_phase_end(self, ctx: LayerContext) -> list[HarnessDecision]:
        return self._publish_all(ctx, [d for layer in self.layers for d in layer.on_phase_end(ctx)])
