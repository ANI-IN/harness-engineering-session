"""The console shows the run profile in every screen header, and a single-arm run (`make show-N`,
harness in action) is labelled as such instead of waiting for a bare arm that never starts."""

from __future__ import annotations

from pathlib import Path

from shipharness.ab.score import REFEREE_VERSION
from shipharness.console.report import load_report
from shipharness.console.screens import ScreenContext, ScreenRenderer
from shipharness.console.state import ConsoleState
from shipharness.events import EventBus, read_events
from shipharness.tracing import write_export
from tests.unit.ab.score_fixtures import record


def log_with(tmp_path: Path, arms: list[str], *, profile: str, single_arm: bool) -> Path:
    log = tmp_path / "runs" / "ab-1" / "events.jsonl"
    with EventBus(log, ab_id="ab-1") as bus:
        for arm in arms:
            spec = {"feature_id": "F1", "layers": [], "profile": profile, "single_arm": single_arm}
            bus.publish(
                "run_start",
                {"spec": spec, "policy_summary": ""},
                run_id=f"r-{arm}",
                arm=arm,  # type: ignore[arg-type]
            )
    return log


def render(tmp_path: Path, log: Path, exports: Path | None = None) -> dict[str, str]:
    exports = exports or tmp_path / "exports"
    state = ConsoleState.from_events(read_events(log))
    ctx = ScreenContext("ab-1", state, load_report(exports), str(exports))
    return ScreenRenderer().render_all(ctx)


def test_the_profile_is_known_from_the_run_start_spec(tmp_path: Path) -> None:
    log = log_with(tmp_path, ["bare", "harness"], profile="class", single_arm=False)
    state = ConsoleState.from_events(read_events(log))
    assert (state.profile, state.single_arm) == ("class", False)
    assert ConsoleState().profile is None  # nothing started yet


def test_every_screen_header_shows_the_profile(tmp_path: Path) -> None:
    log = log_with(tmp_path, ["bare", "harness"], profile="class", single_arm=False)
    screens = render(tmp_path, log)
    for key, html in screens.items():
        assert "profile: class" in html, key
        assert "HARNESS IN ACTION" not in html, key


def test_a_single_arm_run_is_labelled_and_the_bare_panel_says_not_run(tmp_path: Path) -> None:
    log = log_with(tmp_path, ["harness"], profile="class", single_arm=True)
    state = ConsoleState.from_events(read_events(log))
    assert state.single_arm is True
    screens = render(tmp_path, log)
    assert all("HARNESS IN ACTION" in html for html in screens.values())
    live = screens["1"]
    assert "Not run (harness in action)" in live
    assert "referee pending" in live  # the harness arm's panel is the normal one


def test_screen_4_says_how_many_single_arm_runs_it_left_out(tmp_path: Path) -> None:
    exports = tmp_path / "exports"
    for i, (arm, single) in enumerate([("bare", False), ("harness", False), ("harness", True)]):
        rec = record(run_id=f"r-{i}", arm=arm, single_arm=single, referee_version=REFEREE_VERSION)
        write_export("scores", rec.run_id, rec, exports)
    log = log_with(tmp_path, ["bare", "harness"], profile="standard", single_arm=False)
    report = render(tmp_path, log, exports)["4"]
    assert "1 single-arm run (harness in action) not compared" in report
