"""The live wrapper: it puts the learner's layer in place of the course state layer, and its
`--forced-stops` mode writes the evidence of the required live step. No model calls: the model run
is replaced by a SYNTHETIC TEST FIXTURE (tests/a2_live_fixture.py)."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

ASSIGNMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSIGNMENT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import a2_live_fixture as fx  # noqa: E402
from a2_scenario import live_evidence as le  # noqa: E402

from shipharness.harness.base import Harness, register_layer  # noqa: E402
from shipharness.harness.state.layer import StateLayer  # noqa: E402

spec = importlib.util.spec_from_file_location("a2_run_live", ASSIGNMENT / "live" / "run_live.py")
assert spec is not None and spec.loader is not None
run_live = importlib.util.module_from_spec(spec)
sys.modules["a2_run_live"] = run_live
spec.loader.exec_module(run_live)


@pytest.fixture
def restore_registry():
    yield
    register_layer(StateLayer)


@pytest.fixture
def impl(tmp_path: Path) -> Path:
    folder = tmp_path / "my-a2"
    shutil.copytree(ASSIGNMENT / "starter" / "a2_state", folder / "a2_state")
    return folder


def test_install_registers_the_learner_layer_as_state(restore_registry: None) -> None:
    layer = run_live.install(ASSIGNMENT / "starter")
    harness = Harness.from_names(frozenset({"state"}), feature_description="x", feature_steps=[])
    assert type(harness.layers[0]) is layer
    assert layer.__name__ == "ResumableStateLayer"


def test_a_command_or_forced_stops_is_required(restore_registry: None) -> None:
    with pytest.raises(SystemExit):
        run_live.main(["--impl", str(ASSIGNMENT / "starter")])


def test_forced_stops_writes_the_evidence_the_grader_checks(impl: Path, tmp_path: Path) -> None:
    runs, exports = tmp_path / "runs", tmp_path / "exports"
    seen: list[list[str]] = []

    def fake_run(command: list[str]) -> tuple[int, str]:
        seen.append(command)
        fx.write_run(runs, exports)
        return 0, fx.output_text()

    argv = ["--impl", str(impl), "--forced-stops"]
    code = run_live.forced_stops(
        impl, argv=argv, runner=fake_run, runs_dir=runs, exports_dir=exports
    )
    assert code == 0
    assert seen and seen[0][0] == "ab" and le.LIVE_EXAMPLE_ID in seen[0]
    assert le.validate(impl) == []
    command = (impl / "live" / "command.txt").read_text(encoding="utf-8")
    assert "run_live.py" in command and "--forced-stops" in command
    assert (impl / "live" / "output.txt").read_text(encoding="utf-8") == fx.output_text()
    # paid evidence is never overwritten
    again = run_live.forced_stops(
        impl, argv=argv, runner=fake_run, runs_dir=runs, exports_dir=exports
    )
    assert again == 2 and len(seen) == 1


def test_forced_stops_without_an_ab_id_keeps_the_output_and_fails(
    impl: Path, tmp_path: Path
) -> None:
    code = run_live.forced_stops(
        impl,
        argv=["--impl", str(impl), "--forced-stops"],
        runner=lambda command: (1, "x OPENAI_API_KEY is missing\n"),
        runs_dir=tmp_path / "runs",
        exports_dir=tmp_path / "exports",
    )
    assert code == 1
    assert "OPENAI_API_KEY" in (impl / "live" / "output.txt").read_text(encoding="utf-8")
    assert not (impl / "live" / "summary.json").exists()


def test_the_live_step_gives_the_harness_enough_time_for_four_sessions() -> None:
    # Each session end runs the visible suite for the handoff; with the default 120 s harness limit
    # the four-session live step was cut in session 3 (2026-10-17, 142 s of harness work).
    env = run_live.child_env({"PATH": "/usr/bin"})
    assert env["HARNESS_TIMEOUT_S"] == "600"
    assert env["PYTHONUNBUFFERED"] == "1"
    assert run_live.child_env({"HARNESS_TIMEOUT_S": "900"})["HARNESS_TIMEOUT_S"] == "900"


def test_the_live_step_gives_each_session_enough_agent_time() -> None:
    # Attempt 3 (2026-10-18): each session's start-up calls took about 225 s of the standard
    # 300 s agent limit, so session 3 ended by timeout instead of its turn budget. A caller's
    # value is kept.
    assert run_live.child_env({})["RUN_TIMEOUT_S"] == "900"
    assert run_live.child_env({"RUN_TIMEOUT_S": "420"})["RUN_TIMEOUT_S"] == "420"
