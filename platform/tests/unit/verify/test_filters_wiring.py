"""The verify layer's test-phase hook runs the real filter pipeline (shipharness.filters)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from shipharness.config import Settings
from shipharness.harness.base import LayerContext
from shipharness.harness.verify import testphase
from shipharness.runner.models import AgentRunSpec
from shipharness.sandbox import LocalSandbox, default_policy

MODULE = (
    "def clamp(x, lo, hi):\n    if x < lo:\n        return lo\n"
    "    if x > hi:\n        return hi\n    return x\n"
)
OLD_TEST = "from app.mod import clamp\n\n\ndef test_inside():\n    assert clamp(5, 0, 10) == 5\n"
NEW_TESTS = (
    "from app.mod import clamp\n\n\n"
    "def test_below():\n    assert clamp(-3, 0, 10) == 0\n\n\n"
    "def test_vacuous():\n    clamp(50, 0, 10)\n"
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / "app").mkdir(parents=True)
    (ws / "tests" / "visible").mkdir(parents=True)
    (ws / "app" / "__init__.py").write_text("", encoding="utf-8")
    (ws / "app" / "mod.py").write_text(MODULE, encoding="utf-8")
    (ws / "tests" / "visible" / "test_old.py").write_text(OLD_TEST, encoding="utf-8")
    (ws / "pytest.ini").write_text("[pytest]\npythonpath = .\n", encoding="utf-8")
    return ws


def ctx_for(ws: Path) -> LayerContext:
    spec = AgentRunSpec(
        run_id="r",
        arm="harness",
        feature_id="F1",
        checkpoint="local",
        ticket_text="t",
        model="m",
        reasoning_effort="low",
        workspace=ws,
    )
    sandbox = LocalSandbox(default_policy(Settings(_env_file=None)), ws, None, "r", "harness")
    return LayerContext(
        spec=spec, phase="test", session_index=1, turn=1, workspace=ws, sandbox=sandbox
    )


def test_filters_pipeline_keeps_useful_tests_and_discards_vacuous_ones(workspace: Path) -> None:
    start_shas, start_texts = testphase.snapshot(workspace)
    (workspace / "tests" / "visible" / "test_new.py").write_text(NEW_TESTS, encoding="utf-8")
    candidates, broken = testphase.find_candidates(workspace, start_texts)
    assert broken == {}
    ctx = ctx_for(workspace)
    ctx = LayerContext(
        **{**ctx.__dict__, "spec": ctx.spec.model_copy(update={"workspace": workspace})}
    )
    results = testphase.filters_pipeline(candidates, ctx, start_shas)
    reasons = testphase.discarded_reasons(results)
    kept = {str(r.test_id) for r in results if r.filter == 5 and r.passed}
    assert any(t.endswith("test_below") for t in kept), reasons
    assert any(t.endswith("test_vacuous") for t in reasons), reasons
    vacuous = next(v for k, v in reasons.items() if k.endswith("test_vacuous"))
    assert "assert" in vacuous.lower()


def test_source_edit_in_test_phase_discards_new_tests(workspace: Path) -> None:
    start_shas, start_texts = testphase.snapshot(workspace)
    (workspace / "tests" / "visible" / "test_new.py").write_text(NEW_TESTS, encoding="utf-8")
    (workspace / "app" / "mod.py").write_text(MODULE + "\n# edited\n", encoding="utf-8")
    candidates, _ = testphase.find_candidates(workspace, start_texts)
    results = testphase.filters_pipeline(candidates, ctx_for(workspace), start_shas)
    reasons = testphase.discarded_reasons(results)
    assert reasons and all("source" in r for r in reasons.values() if "assert" not in r.lower()), (
        reasons
    )
    assert sys.executable  # LocalSandbox runs the host interpreter (trusted fixture code)
