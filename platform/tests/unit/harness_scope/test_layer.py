"""ScopeLayer: feature_list.json, blocked patches, reverted run changes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shipharness.events import EventBus, read_events
from shipharness.harness.base import Harness
from shipharness.harness.scope.layer import ScopeLayer
from shipharness.runner.models import ToolResult
from shipharness.sandbox import ExecResult, FakeSandbox

from .helpers import call, make_ctx, patch_for


def seeded(tmp_path: Path):  # type: ignore[no-untyped-def]
    ws = tmp_path / "ws"
    (ws / "app" / "api").mkdir(parents=True)
    (ws / "app" / "api" / "issues.py").write_text("issues = 1\n", encoding="utf-8")
    (ws / "app" / "models.py").write_text("models = 1\n", encoding="utf-8")
    return ws


def ok(call_id: str = "c1") -> ToolResult:
    return ToolResult(call_id=call_id, ok=True, output="exit=0\n")


# --- feature_list.json -------------------------------------------------------------------------


def test_prepare_writes_one_feature_with_passes_false_and_commits(tmp_path: Path) -> None:
    sandbox = FakeSandbox()
    ctx = make_ctx(seeded(tmp_path), sandbox)
    ScopeLayer().prepare_workspace(ctx)
    data = json.loads((ctx.workspace / "feature_list.json").read_text(encoding="utf-8"))
    assert data["$schema"] == "./feature_list.schema.json"
    assert len(data["features"]) == 1
    feature = data["features"][0]
    assert feature == {
        "id": "F3",
        "category": "feature",
        "description": "Idempotency keys on create-issue",
        "steps": [
            "POST /projects/{id}/issues with Idempotency-Key twice returns the same issue",
            "A different key creates a second issue",
        ],
        "passes": False,
        "evidence": None,
        "testedAt": None,
    }
    assert (ctx.workspace / "feature_list.schema.json").is_file()
    commits = [c for c in sandbox.commands if "commit" in c]
    assert len(commits) == 1 and "feature_list.json" in commits[0]


def test_feature_list_matches_its_schema(tmp_path: Path) -> None:
    jsonschema_rs = pytest.importorskip("jsonschema_rs")  # installed with schemathesis
    ctx = make_ctx(seeded(tmp_path))
    ScopeLayer().prepare_workspace(ctx)
    schema = json.loads((ctx.workspace / "feature_list.schema.json").read_text(encoding="utf-8"))
    data = json.loads((ctx.workspace / "feature_list.json").read_text(encoding="utf-8"))
    validator = jsonschema_rs.validator_for(schema)
    assert validator.is_valid(data)
    passed = json.loads(json.dumps(data))
    passed["features"][0].update(
        passes=True,
        testedAt="2026-10-16T12:00:00Z",
        evidence={"gate_id": "g", "commit": "c", "visible": "1/1", "existing": "1/1", "checks": []},
    )
    assert validator.is_valid(passed)
    data["features"][0]["passes"] = "yes"
    assert not validator.is_valid(data)


def test_feature_fields_can_come_from_the_task(tmp_path: Path) -> None:
    ctx = make_ctx(seeded(tmp_path))
    layer = ScopeLayer(feature_category="api", feature_description="Idem", feature_steps=["s1"])
    layer.prepare_workspace(ctx)
    feature = json.loads((ctx.workspace / "feature_list.json").read_text(encoding="utf-8"))[
        "features"
    ][0]
    assert (feature["category"], feature["description"], feature["steps"]) == (
        "api",
        "Idem",
        ["s1"],
    )


def test_unknown_constructor_kwargs_are_ignored() -> None:
    ScopeLayer(instructions_dir="x", gate_checks=["r1"])


def test_context_prefix_is_stable_and_states_the_scope(tmp_path: Path) -> None:
    ctx = make_ctx(seeded(tmp_path))
    layer = ScopeLayer()
    first = layer.context_prefix(ctx)
    ctx.phase, ctx.session_index, ctx.turn = "test", 2, 5
    assert layer.context_prefix(ctx) == first
    text = "\n".join(first)
    assert "one feature: Feature 3: Safe retries for issue creation" in text
    assert "app/api/issues.py" in text and "tests/visible/**" in text
    assert "It is unacceptable to remove or edit tests" in text
    assert "feature_list.json is written only by the harness" in text


# --- apply_patch -----------------------------------------------------------------------------


def test_patch_outside_the_allowed_paths_is_blocked_with_a_reason(tmp_path: Path) -> None:
    ctx = make_ctx(seeded(tmp_path))
    decision = ScopeLayer().before_tool(
        ctx, call("apply_patch", patch=patch_for("app/models.py", "models = 1", "models = 2"))
    )
    assert decision.kind == "block"
    assert decision.paths == ["app/models.py"]
    assert "app/models.py" in decision.message and "build phase" in decision.message


def test_patch_inside_the_allowed_paths_is_allowed(tmp_path: Path) -> None:
    ctx = make_ctx(seeded(tmp_path))
    decision = ScopeLayer().before_tool(
        ctx, call("apply_patch", patch=patch_for("app/api/issues.py", "issues = 1", "issues = 2"))
    )
    assert decision.kind == "allow"


def test_patch_to_feature_list_is_blocked(tmp_path: Path) -> None:
    ctx = make_ctx(seeded(tmp_path))
    layer = ScopeLayer()
    layer.prepare_workspace(ctx)
    decision = layer.before_tool(
        ctx, call("apply_patch", patch=patch_for("feature_list.json", "x", "y"))
    )
    assert decision.kind == "block"
    assert "feature_list.json is written only by the harness" in decision.message


def test_one_bad_hunk_blocks_the_whole_patch(tmp_path: Path) -> None:
    ctx = make_ctx(seeded(tmp_path))
    patch = patch_for("app/api/issues.py", "issues = 1", "issues = 2") + patch_for(
        "app/new_module.py", None, "x = 1"
    )
    decision = ScopeLayer().before_tool(ctx, call("apply_patch", patch=patch))
    assert decision.kind == "block" and decision.paths == ["app/new_module.py"]


def test_blocked_patch_reaches_the_agent_and_the_event_log(tmp_path: Path) -> None:
    from shipharness.runner.tools import ToolBox

    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id=None) as bus:
        ctx = make_ctx(seeded(tmp_path), bus=bus)
        harness = Harness([ScopeLayer()])
        box = ToolBox(
            ctx.workspace,
            ctx.sandbox,
            bus,
            "r-1",
            "harness",
            guard=lambda c: harness.before_tool(ctx, c),
        )
        result = box.execute(
            call("apply_patch", patch=patch_for("app/models.py", "models = 1", "models = 2"))
        )
    assert result.ok is False and result.output.startswith("BLOCKED: ")
    assert "app/models.py" in result.output
    blocked = [e for e in read_events(log) if e.type == "blocked"]
    assert blocked[0].data["action"] == "reject_patch"
    assert blocked[0].data["paths"] == ["app/models.py"]


def test_test_phase_blocks_source_edits(tmp_path: Path) -> None:
    ctx = make_ctx(seeded(tmp_path))
    ctx.phase = "test"
    decision = ScopeLayer().before_tool(
        ctx, call("apply_patch", patch=patch_for("app/api/issues.py", "issues = 1", "issues = 2"))
    )
    assert decision.kind == "block" and "test phase" in decision.message


# --- run: revert without git -------------------------------------------------------------------


def run_command(layer: ScopeLayer, ctx, mutate, call_id: str = "c1"):  # type: ignore[no-untyped-def]
    run_call = call("run", call_id=call_id, command="python make_changes.py", timeout_s=None)
    assert layer.before_tool(ctx, run_call).kind == "allow"
    mutate(ctx.workspace)
    return layer.after_tool(ctx, run_call, ok(call_id))


def test_run_changes_outside_the_allowed_paths_are_reverted(tmp_path: Path) -> None:
    ctx = make_ctx(seeded(tmp_path))
    layer = ScopeLayer()

    def mutate(ws: Path) -> None:
        (ws / "app" / "models.py").write_text("models = 2\n", encoding="utf-8")
        (ws / "app" / "api" / "issues.py").write_text("issues = 2\n", encoding="utf-8")
        (ws / "scratch.py").write_text("tmp\n", encoding="utf-8")

    decisions = run_command(layer, ctx, mutate)
    assert (ctx.workspace / "app" / "models.py").read_text(encoding="utf-8") == "models = 1\n"
    assert not (ctx.workspace / "scratch.py").exists()
    assert (ctx.workspace / "app" / "api" / "issues.py").read_text(encoding="utf-8") == (
        "issues = 2\n"
    )
    assert [d.kind for d in decisions] == ["revert"]
    assert decisions[0].paths == ["app/models.py", "scratch.py"]
    assert "build phase" in decisions[0].message


def test_run_change_to_feature_list_is_reverted(tmp_path: Path) -> None:
    ctx = make_ctx(seeded(tmp_path))
    layer = ScopeLayer()
    layer.prepare_workspace(ctx)
    original = (ctx.workspace / "feature_list.json").read_bytes()

    def mutate(ws: Path) -> None:
        (ws / "feature_list.json").write_text('{"features": []}', encoding="utf-8")

    decisions = run_command(layer, ctx, mutate)
    assert (ctx.workspace / "feature_list.json").read_bytes() == original
    assert decisions[0].message.startswith("feature_list.json is written only by the harness")


def test_deleting_feature_list_is_reverted(tmp_path: Path) -> None:
    ctx = make_ctx(seeded(tmp_path))
    layer = ScopeLayer()
    layer.prepare_workspace(ctx)
    original = (ctx.workspace / "feature_list.json").read_bytes()
    run_command(layer, ctx, lambda ws: (ws / "feature_list.json").unlink())
    assert (ctx.workspace / "feature_list.json").read_bytes() == original


def test_revert_is_published_as_blocked_revert(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id=None) as bus:
        ctx = make_ctx(seeded(tmp_path), bus=bus)
        harness = Harness([ScopeLayer()])
        run_call = call("run", command="touch x", timeout_s=None)
        harness.before_tool(ctx, run_call)
        (ctx.workspace / "x").write_text("", encoding="utf-8")
        harness.after_tool(ctx, run_call, ok())
    blocked = [e for e in read_events(log) if e.type == "blocked"]
    assert blocked[0].data["action"] == "revert" and blocked[0].data["paths"] == ["x"]


def test_after_tool_without_a_matching_baseline_reverts_nothing(tmp_path: Path) -> None:
    ctx = make_ctx(seeded(tmp_path))
    layer = ScopeLayer()
    layer.before_tool(ctx, call("run", call_id="first", command="true", timeout_s=None))
    (ctx.workspace / "harness_wrote_this.txt").write_text("x\n", encoding="utf-8")
    other = call("run", call_id="second", command="true", timeout_s=None)
    assert layer.after_tool(ctx, other, ok("second")) == []
    assert (ctx.workspace / "harness_wrote_this.txt").exists()


def test_run_visible_tests_changes_are_also_checked(tmp_path: Path) -> None:
    ctx = make_ctx(seeded(tmp_path))
    layer = ScopeLayer()
    tests_call = call("run_visible_tests", selector=None)
    layer.before_tool(ctx, tests_call)
    (ctx.workspace / "teamtrack.db").write_bytes(b"sqlite")
    decisions = layer.after_tool(ctx, tests_call, ok())
    assert decisions[0].kind == "revert" and not (ctx.workspace / "teamtrack.db").exists()


def test_read_only_tools_take_no_snapshot(tmp_path: Path) -> None:
    ctx = make_ctx(seeded(tmp_path))
    layer = ScopeLayer()
    read = call("read_file", path="app/models.py", start_line=None, max_lines=None)
    assert layer.before_tool(ctx, read).kind == "allow"
    (ctx.workspace / "scratch.py").write_text("x\n", encoding="utf-8")
    assert layer.after_tool(ctx, read, ok()) == []


def test_state_files_may_be_edited_when_the_state_layer_is_on(tmp_path: Path) -> None:
    ctx = make_ctx(seeded(tmp_path))
    layer = ScopeLayer()
    decisions = run_command(
        layer, ctx, lambda ws: (ws / "progress.md").write_text("# Progress\n", encoding="utf-8")
    )
    assert decisions == []
    ctx_bare = make_ctx(tmp_path / "ws2", layers=frozenset({"scope"}))
    decisions = run_command(
        ScopeLayer(),
        ctx_bare,
        lambda ws: (ws / "progress.md").write_text("# Progress\n", encoding="utf-8"),
    )
    assert decisions[0].kind == "revert"


def test_missing_allow_list_is_noted_and_does_not_restrict(tmp_path: Path) -> None:
    ctx = make_ctx(seeded(tmp_path), allowed_paths={"build": ["app/**"]})
    layer = ScopeLayer()
    notes = layer.prepare_workspace(ctx)
    assert any(d.kind == "note" and "test" in d.message for d in notes)
    ctx.phase = "test"
    decision = layer.before_tool(
        ctx, call("apply_patch", patch=patch_for("anything.py", None, "x = 1"))
    )
    assert decision.kind == "allow"


def test_sandbox_is_never_asked_to_run_git_for_a_revert(tmp_path: Path) -> None:
    sandbox = FakeSandbox(default=ExecResult(exit_code=0, output="", duration_ms=1))
    ctx = make_ctx(seeded(tmp_path), sandbox)
    layer = ScopeLayer()
    run_command(layer, ctx, lambda ws: (ws / "scratch.py").write_text("x\n", encoding="utf-8"))
    assert sandbox.commands == []
