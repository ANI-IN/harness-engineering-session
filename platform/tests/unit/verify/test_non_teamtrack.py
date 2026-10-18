"""The verify layer on a repository that is not TeamTrack: tests in tests/, no Alembic.

Each test here fails on the behaviour seen in the boltons worked example run of 2026-10-17
(r-20261017-095514-ac8f1c): the gate ran tests/visible, ran `alembic heads` on a repository
without migrations, and the test-phase filters looked only inside tests/visible. The TeamTrack
tests check that a TeamTrack-shaped workspace behaves as before.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shipharness.harness.base import LayerContext
from shipharness.harness.verify.layer import PREFIX, VerifyLayer, has_migrations
from shipharness.runner.models import AgentRunSpec
from shipharness.sandbox import ExecResult, FakeSandbox

from .fakes import fail, ok

QUEUEUTILS = "def first(items):\n    return items[0]\n"
EXISTING_TEST = (
    "from boltons.queueutils import first\n\n\ndef test_first():\n    assert first([1]) == 1\n"
)
NEW_TESTS = """from boltons.queueutils import first


def test_first_of_two():
    assert first([3, 4]) == 3


def test_vacuous():
    first([1])
"""


def boltons_like(root: Path) -> Path:
    """A small library: the module in boltons/, its tests in tests/, no alembic.ini."""
    (root / "boltons").mkdir(parents=True)
    (root / "boltons" / "__init__.py").write_text("", encoding="utf-8")
    (root / "boltons" / "queueutils.py").write_text(QUEUEUTILS, encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_queueutils.py").write_text(EXISTING_TEST, encoding="utf-8")
    return root


def teamtrack_like(root: Path) -> Path:
    (root / "migrations" / "versions").mkdir(parents=True)
    (root / "alembic.ini").write_text("[alembic]\nscript_location = migrations\n", "utf-8")
    (root / "tests" / "visible").mkdir(parents=True)
    (root / "tests" / "visible" / "test_old.py").write_text("def test_old():\n    assert 1\n")
    return root


def spec(ws: Path, **overrides: Any) -> AgentRunSpec:
    base: dict[str, Any] = dict(
        run_id="r-tg",
        arm="harness",
        feature_id="TG-boltons.queueutils",
        checkpoint="testgen",
        ticket_text="Write tests.",
        model="gpt-6-luna",
        reasoning_effort="low",
        layers=frozenset({"verify"}),
        phases=("test",),
        workspace=ws,
    )
    base.update(overrides)
    return AgentRunSpec(**base)


def sandbox_like_the_bug_run() -> FakeSandbox:
    """pytest finds no tests/visible; alembic has no configuration; everything else succeeds."""

    def run(command: str) -> ExecResult:
        if "-m pytest tests/visible" in command:
            return fail(
                "ERROR: file or directory not found: tests/visible\n\nno tests ran in 0.01s"
            )
        if "-m pytest" in command:
            return ok("2 passed in 0.10s\n")
        if command.startswith("alembic"):
            return fail("FAILED: No 'script_location' key found in configuration.")
        if "-m shipharness.checks.runner" in command:
            return fail("the TeamTrack house-rule checks do not apply here")
        return ok("")

    return FakeSandbox(run)


def ctx_for(ws: Path, sandbox: FakeSandbox, **overrides: Any) -> LayerContext:
    run_spec = spec(ws, **overrides)
    return LayerContext(
        spec=run_spec,
        phase=run_spec.phases[0],
        session_index=1,
        turn=1,
        workspace=ws,
        sandbox=sandbox,
    )


def test_gate_on_a_non_teamtrack_repo_passes_with_its_own_tests_and_no_migrations(
    tmp_path: Path,
) -> None:
    ws = boltons_like(tmp_path / "ws")
    sandbox = sandbox_like_the_bug_run()
    ctx = ctx_for(ws, sandbox, visible_tests_dir="tests")
    layer = VerifyLayer()
    layer.prepare_workspace(ctx)
    decision = layer.on_claim_done(ctx)
    assert decision is not None and decision.kind == "gate_pass", decision
    items = {i["name"]: i for i in ctx.state["verify.gate"]["items"]}
    assert items["visible tests"]["detail"] == "passed=2 failed=0 errors=0"
    assert "skipped: no migrations configured" in items["clean state"]["detail"]
    assert any("python -m pytest tests -q" in c for c in sandbox.commands)
    assert not any(c.startswith("alembic") for c in sandbox.commands)
    # A run without a build phase never runs the house-rule checks, so it needs no baseline.
    assert not any("shipharness.checks.runner" in c for c in sandbox.commands)


def test_an_alembic_ini_the_agent_adds_does_not_turn_the_head_check_on(tmp_path: Path) -> None:
    ws = boltons_like(tmp_path / "ws")
    sandbox = sandbox_like_the_bug_run()
    ctx = ctx_for(ws, sandbox, visible_tests_dir="tests")
    layer = VerifyLayer()
    layer.prepare_workspace(ctx)
    (ws / "alembic.ini").write_text("[alembic]\n", encoding="utf-8")
    decision = layer.on_claim_done(ctx)
    assert decision is not None and decision.kind == "gate_pass"
    assert not any(c.startswith("alembic") for c in sandbox.commands)


def test_teamtrack_workspace_keeps_tests_visible_and_the_head_check(tmp_path: Path) -> None:
    ws = teamtrack_like(tmp_path / "ws")
    sandbox = FakeSandbox(
        {"alembic heads": ok("abc (head)\n"), "cd /tmp/shipharness-gate-": ok("1 passed in 0.1s\n")}
    )
    ctx = ctx_for(ws, sandbox, phases=("build", "test"), checkpoint="m1-s1-start")
    ctx.phase = "test"
    layer = VerifyLayer(baseline_json='{"results": []}')
    layer.prepare_workspace(ctx)
    decision = layer.on_claim_done(ctx)
    assert decision is not None and decision.kind == "gate_pass"
    assert any("python -m pytest tests/visible -q" in c for c in sandbox.commands)
    assert "alembic heads" in sandbox.commands
    assert layer.existing_tests == ["tests/visible/test_old.py"]
    assert layer.context_prefix(ctx) == [PREFIX]


def test_migration_configuration_is_alembic_ini_or_the_migrations_directory(
    tmp_path: Path,
) -> None:
    assert has_migrations(teamtrack_like(tmp_path / "tt")) is True
    assert has_migrations(boltons_like(tmp_path / "bolt")) is False
    versions_only = tmp_path / "versions"
    (versions_only / "migrations" / "versions").mkdir(parents=True)
    assert has_migrations(versions_only) is True
    ini_only = tmp_path / "ini"
    ini_only.mkdir()
    (ini_only / "alembic.ini").write_text("[alembic]\n", encoding="utf-8")
    assert has_migrations(ini_only) is True


def test_prefix_mentions_migration_heads_only_when_the_repo_has_migrations(
    tmp_path: Path,
) -> None:
    ws = boltons_like(tmp_path / "ws")
    ctx = ctx_for(ws, FakeSandbox(), visible_tests_dir="tests")
    layer = VerifyLayer()
    layer.prepare_workspace(ctx)
    [text] = layer.context_prefix(ctx)
    assert "migration head" not in text
    assert "clean state" in text


def test_test_phase_filters_evaluate_new_tests_in_the_runs_test_directory(tmp_path: Path) -> None:
    ws = boltons_like(tmp_path / "ws")
    sandbox = FakeSandbox()
    ctx = ctx_for(ws, sandbox, visible_tests_dir="tests")
    seen: list[str] = []

    def pipeline(cands: list[dict], _ctx: LayerContext, _shas: dict[str, str]) -> list[dict]:
        seen.extend(c["test_id"] for c in cands)
        return [
            {
                "test_id": c["test_id"],
                "filter": 3 if c["test_id"].endswith("vacuous") else 5,
                "passed": not c["test_id"].endswith("vacuous"),
                "reason": "adds no line coverage" if c["test_id"].endswith("vacuous") else "ok",
            }
            for c in cands
        ]

    layer = VerifyLayer(pipeline=pipeline)
    layer.prepare_workspace(ctx)
    layer.context_prefix(ctx)  # first hook of the test phase: snapshot taken here
    new = ws / "tests" / "test_queueutils_generated.py"
    new.write_text(NEW_TESTS, encoding="utf-8")
    [decision] = layer.on_phase_end(ctx)
    assert seen == [
        "tests/test_queueutils_generated.py::test_first_of_two",
        "tests/test_queueutils_generated.py::test_vacuous",
    ]
    assert decision.data["kept"] == ["tests/test_queueutils_generated.py::test_first_of_two"]
    assert decision.data["discarded"] == {
        "tests/test_queueutils_generated.py::test_vacuous": "adds no line coverage"
    }
    assert "test_vacuous" not in new.read_text(encoding="utf-8")
    assert any(c.startswith("git add -A tests &&") for c in sandbox.commands)


def test_teamtrack_test_phase_still_looks_only_in_tests_visible(tmp_path: Path) -> None:
    ws = teamtrack_like(tmp_path / "ws")
    ctx = ctx_for(ws, FakeSandbox(), phases=("build", "test"), checkpoint="m1-s1-start")
    ctx.phase = "test"
    seen: list[str] = []

    def pipeline(cands: list[dict], _ctx: LayerContext, _shas: dict[str, str]) -> list[dict]:
        seen.extend(c["test_id"] for c in cands)
        return [{"test_id": c["test_id"], "filter": 5, "passed": True, "reason": ""} for c in cands]

    layer = VerifyLayer(baseline_json="{}", pipeline=pipeline)
    layer.context_prefix(ctx)
    (ws / "tests" / "test_outside.py").write_text("def test_x():\n    assert 1\n")
    (ws / "tests" / "visible" / "test_new.py").write_text("def test_y():\n    assert 2\n")
    layer.on_phase_end(ctx)
    assert seen == ["tests/visible/test_new.py::test_y"]


def test_ruff_config_is_detected_from_the_checkpoint_workspace(tmp_path: Path) -> None:
    from shipharness.harness.verify.layer import has_ruff_config

    bare = tmp_path / "bare"
    bare.mkdir()
    assert has_ruff_config(bare) is False
    (tmp_path / "toml").mkdir()
    (tmp_path / "toml" / "ruff.toml").write_text("line-length = 100\n", encoding="utf-8")
    assert has_ruff_config(tmp_path / "toml") is True
    (tmp_path / "py").mkdir()
    (tmp_path / "py" / "pyproject.toml").write_text(
        "[tool.ruff]\nline-length = 100\n", encoding="utf-8"
    )
    assert has_ruff_config(tmp_path / "py") is True
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    assert has_ruff_config(tmp_path / "other") is False
