"""The referee and the verify gate send every check parameter under the name the checks read."""

from __future__ import annotations

from pathlib import Path

from shipharness.ab.referee import Referee, RefereeDeps, RefereeTask
from shipharness.checks import params as P
from shipharness.harness.base import LayerContext
from shipharness.harness.verify.layer import VerifyLayer
from shipharness.runner.models import AgentRunSpec
from shipharness.sandbox import FakeSandbox


def referee(tmp_path: Path) -> Referee:
    task = RefereeTask(
        feature_id="F1",
        checkpoint="m1-s1-start",
        ticket_text="t",
        hidden_test_ids=["tests/hidden/f1/test_list.py::test_cursor"],
        allowed_paths={"build": ["app/api/issues.py"], "test": ["tests/visible/**"]},
    )
    deps = RefereeDeps(
        course_repo=tmp_path,
        checkpoint_ref=None,
        sandbox_factory=lambda *a: FakeSandbox(),
        exports_dir=tmp_path / "exports",
        base_dir=tmp_path / "ref",
        seed=1,
    )
    return Referee(task, deps)


def test_referee_params_use_the_names_the_checks_read(tmp_path: Path) -> None:
    params = referee(tmp_path)._params(
        {"run_log": "/referee-in/events.jsonl", "session_patches": []},
        changed_files=["app/api/issues.py", "tests/visible/test_new.py"],
        shipped_files=["tests/visible/test_new.py"],
        shipped_ids=["tests/visible/test_new.py::test_ok"],
        test_phase_files=["app/api/issues.py"],
        existing_ids=["tests/visible/test_old.py::test_a"],
    )
    assert params[P.REGRESSION_EXPECTED] == ["tests/visible/test_old.py::test_a"]
    assert params[P.HIDDEN_TESTS] == ["tests/hidden/f1/test_list.py::test_cursor"]
    assert params[P.SHIPPED_TESTS] == ["tests/visible/test_new.py::test_ok"]
    assert params[P.CHANGED_FILES] == ["app/api/issues.py", "tests/visible/test_new.py"]
    assert params[P.PHASE_FILES] == {"test": ["app/api/issues.py"]}
    assert params[P.ALLOWED_PATHS]["build"] == ["app/api/issues.py"]
    assert P.HARNESS_ARTIFACTS in params and P.FLAKY_RUNS in params


def test_gate_params_use_the_names_the_checks_read(tmp_path: Path) -> None:
    layer = VerifyLayer(baseline_json="{}")
    (tmp_path / "tests" / "visible").mkdir(parents=True)
    (tmp_path / "tests" / "visible" / "test_a.py").write_text("def test_a(): pass\n")
    spec = AgentRunSpec(
        run_id="r",
        arm="harness",
        feature_id="F1",
        checkpoint="m1-s1-start",
        ticket_text="t",
        model="m",
        reasoning_effort="low",
        workspace=tmp_path,
        allowed_paths={"build": ["app/api/issues.py"]},
    )
    ctx = LayerContext(
        spec=spec, phase="build", session_index=1, turn=1, workspace=tmp_path, sandbox=FakeSandbox()
    )
    layer.prepare_workspace(ctx)
    params = layer._params(ctx)
    assert params[P.REGRESSION_TARGETS] == ["tests/visible/test_a.py"]
    assert params[P.ALLOWED_PATHS] == {"build": ["app/api/issues.py"]}


def test_check_modules_read_only_declared_names() -> None:
    import re

    source = Path(P.__file__).parent
    read: set[str] = set()
    for path in source.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        read |= set(re.findall(r'ctx\.params\.get\("([a-z_0-9]+)"', text))
        if "p = ctx.params" in text:  # a local alias for the check params
            read |= set(re.findall(r'\bp\.get\("([a-z_0-9]+)"', text))
    assert read, "scan found no params reads"
    assert read <= set(P.ALL_NAMES), sorted(read - set(P.ALL_NAMES))
