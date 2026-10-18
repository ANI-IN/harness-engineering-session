from __future__ import annotations

import re
from pathlib import Path

import pytest

from shipharness.events import EventBus, read_events
from shipharness.harness.base import BaseLayer, Harness, LayerContext, parse_layers
from shipharness.harness.decisions import HarnessDecision
from shipharness.layout import find_repo_root
from shipharness.runner.models import AgentRunSpec, ToolCall
from shipharness.sandbox import FakeSandbox

HARNESS_SRC = find_repo_root(Path(__file__)) / "platform" / "src" / "shipharness" / "harness"


def make_ctx(tmp_path: Path, bus: EventBus | None = None) -> LayerContext:
    spec = AgentRunSpec(
        run_id="r-1",
        arm="harness",
        feature_id="F1",
        checkpoint="m1-s1-start",
        ticket_text="t",
        model="m",
        reasoning_effort="low",
        workspace=tmp_path,
    )
    return LayerContext(
        spec=spec,
        phase="build",
        session_index=1,
        turn=1,
        workspace=tmp_path,
        sandbox=FakeSandbox(),
        bus=bus,
    )


CALL = ToolCall(call_id="c1", name="apply_patch", arguments={"patch": "x"})


class AllowLayer(BaseLayer):
    name = "instructions"

    def context_prefix(self, ctx: LayerContext) -> list[str]:
        return ["MAP"]


class BlockLayer(BaseLayer):
    name = "scope"

    def before_tool(self, ctx: LayerContext, call: ToolCall) -> HarnessDecision:
        return HarnessDecision(kind="block", layer="scope", message="out of scope", paths=["a.py"])

    def context_prefix(self, ctx: LayerContext) -> list[str]:
        return ["SCOPE"]


class GateLayer(BaseLayer):
    name = "verify"

    def on_claim_done(self, ctx: LayerContext) -> HarnessDecision | None:
        return HarnessDecision(kind="gate_fail", layer="verify", message="R1 failed")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("none", set()),
        ("", set()),
        ("all", {"instructions", "state", "scope", "verify"}),
        ("-verify", {"instructions", "state", "scope"}),
        ("-verify,-state", {"instructions", "scope"}),
        ("state,scope", {"state", "scope"}),
    ],
)
def test_parse_layers(value: str, expected: set[str]) -> None:
    assert parse_layers(value) == frozenset(expected)


def test_parse_layers_rejects_unknown_names() -> None:
    with pytest.raises(ValueError, match="memory"):
        parse_layers("instructions,memory")


def test_first_block_wins(tmp_path: Path) -> None:
    harness = Harness([AllowLayer(), BlockLayer()])
    decision = harness.before_tool(make_ctx(tmp_path), CALL)
    assert decision.kind == "block"
    assert decision.message == "out of scope"


def test_layers_run_in_canonical_order(tmp_path: Path) -> None:
    harness = Harness([BlockLayer(), AllowLayer()])
    assert [layer.name for layer in harness.layers] == ["instructions", "scope"]
    assert harness.context_prefix(make_ctx(tmp_path)) == ["MAP", "SCOPE"]


def test_empty_harness_is_a_no_op(tmp_path: Path) -> None:
    harness = Harness([])
    ctx = make_ctx(tmp_path)
    assert harness.before_tool(ctx, CALL).kind == "allow"
    assert harness.context_prefix(ctx) == []
    assert harness.on_claim_done(ctx) is None
    assert harness.wrapup_text(ctx) is None
    assert harness.names == frozenset()


def test_gate_fail_is_returned_from_claim(tmp_path: Path) -> None:
    decision = Harness([GateLayer()]).on_claim_done(make_ctx(tmp_path))
    assert decision is not None and decision.kind == "gate_fail"


def test_decisions_are_published_and_blocks_also_emit_blocked(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id=None) as bus:
        Harness([BlockLayer()]).before_tool(make_ctx(tmp_path, bus), CALL)
    types = [e.type for e in read_events(log)]
    assert types == ["harness_decision", "blocked"]
    blocked = list(read_events(log))[1]
    assert blocked.data == {
        "phase": "build",
        "paths": ["a.py"],
        "action": "reject_patch",
        "reason": "out of scope",
    }


def test_allow_decisions_are_not_published(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id=None) as bus:
        Harness([AllowLayer()]).before_tool(make_ctx(tmp_path, bus), CALL)
    assert list(read_events(log)) == []


def test_from_names_rejects_unregistered_layers() -> None:
    with pytest.raises(ValueError, match="not available"):
        Harness.from_names(frozenset({"verify"}), registry={})


def test_harness_code_never_references_referee_only_material() -> None:
    forbidden = re.compile(r"tests/hidden|teamtrack/reference|#referee|set\s*==\s*[\"']referee")
    offenders = [
        str(path.relative_to(HARNESS_SRC))
        for path in HARNESS_SRC.rglob("*.py")
        if forbidden.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []
