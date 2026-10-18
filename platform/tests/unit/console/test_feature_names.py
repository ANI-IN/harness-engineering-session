"""The console names the feature as "Feature N: <name>": the run header on every screen, the
run-start line, and the A/B report rows. A control task (no course name) shows its code."""

from __future__ import annotations

from pathlib import Path

from shipharness.console.report import load_report
from shipharness.console.screens import ScreenContext, ScreenRenderer
from shipharness.console.state import ConsoleState, summarise
from shipharness.events import EventBus, read_events
from tests.unit.console.fixture_log import build_fixture_exports


def log_for(tmp_path: Path, feature: str) -> Path:
    log = tmp_path / "runs" / "ab-1" / "events.jsonl"
    with EventBus(log, ab_id="ab-1") as bus:
        for arm in ("bare", "harness"):
            bus.publish(
                "run_start",
                {"spec": {"feature_id": feature, "layers": []}, "policy_summary": ""},
                run_id=f"r-{arm}",
                arm=arm,  # type: ignore[arg-type]
            )
    return log


def render(tmp_path: Path, log: Path, exports: Path) -> dict[str, str]:
    state = ConsoleState.from_events(read_events(log))
    ctx = ScreenContext("ab-1", state, load_report(exports), str(exports))
    return ScreenRenderer().render_all(ctx)


def test_every_screen_header_shows_the_feature_with_its_plain_name(tmp_path: Path) -> None:
    log = log_for(tmp_path, "F4")
    state = ConsoleState.from_events(read_events(log))
    assert (state.feature, state.feature_label) == (
        "F4",
        "Feature 4: Version checks on issue edits",
    )
    assert ConsoleState().feature_label is None  # nothing started yet
    for key, html in render(tmp_path, log, tmp_path / "exports").items():
        assert "Feature 4: Version checks on issue edits" in html, key


def test_a_feature_without_a_plain_name_shows_its_code(tmp_path: Path) -> None:
    screens = render(tmp_path, log_for(tmp_path, "C2"), tmp_path / "exports")
    assert all('<span class="badge feature">C2</span>' in html for html in screens.values())


def test_the_run_start_line_names_the_feature(tmp_path: Path) -> None:
    [event, *_] = read_events(log_for(tmp_path, "F6"))
    assert summarise(event) == "run start Feature 6: Watchers"


def test_the_report_rows_name_the_feature(tmp_path: Path) -> None:
    exports = build_fixture_exports(tmp_path / "exports")
    report = render(tmp_path, log_for(tmp_path, "F1"), exports)["4"]
    assert "Feature 1: Org-wide issue search · s1 · bare" in report
    assert "Feature 3: Safe retries for issue creation · s3 · harness" in report
