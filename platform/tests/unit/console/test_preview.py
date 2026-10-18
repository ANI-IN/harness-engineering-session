"""Host-side board preview orchestrator: runs the capture module through the Sandbox interface,
validates its output, writes PNGs under the run dir, and emits `screenshot` events."""

from __future__ import annotations

import base64
import json
import threading
from pathlib import Path

import pytest

from shipharness.console.board_capture import MARKER, capture_line
from shipharness.console.preview import BoardPreview, CaptureError, parse_capture_output
from shipharness.events import EventBus, read_events
from shipharness.sandbox import ExecResult, FakeSandbox
from tests.unit.console.fixture_log import tiny_png


def ok(output: str) -> ExecResult:
    return ExecResult(exit_code=0, output=output, duration_ms=900)


def good_output(png: bytes | None = None, overlays: list[dict] | None = None) -> str:
    line = capture_line(
        "board",
        "admin@acme.test",
        overlays or [{"issue_id": 21, "mark": "other_org"}],
        png or tiny_png(),
    )
    return "INFO uvicorn noise\n" + line + "\n"


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    return tmp_path / "runs" / "ab-1"


def preview(sandbox: FakeSandbox, run_dir: Path, bus: EventBus) -> BoardPreview:
    return BoardPreview(sandbox, bus, run_dir, run_id="run-bare", arm="bare")


def test_capture_writes_png_and_emits_a_screenshot_event(run_dir: Path) -> None:
    sandbox = FakeSandbox(lambda cmd: ok(good_output()))
    with EventBus(run_dir / "events.jsonl", ab_id="ab-1") as bus:
        event = preview(sandbox, run_dir, bus).capture()
    assert event is not None and event.type == "screenshot"
    assert event.data == {
        "path": "screenshots/bare/board-0001.png",
        "view": "board",
        "as_user": "admin@acme.test",
        "overlays": [{"issue_id": 21, "mark": "other_org"}],
    }
    assert (run_dir / "screenshots" / "bare" / "board-0001.png").read_bytes() == tiny_png()
    assert [e.type for e in read_events(run_dir / "events.jsonl")] == ["screenshot"]
    [command] = sandbox.commands
    assert "python -m shipharness.console.board_capture once" in command
    assert "--user admin@acme.test" in command and "--org acme" in command
    assert "--view board" in command and command.startswith("env HOME=/tmp ")


def test_identical_frames_are_not_written_twice(run_dir: Path) -> None:
    sandbox = FakeSandbox(lambda cmd: ok(good_output()))
    with EventBus(run_dir / "events.jsonl", ab_id="ab-1") as bus:
        p = preview(sandbox, run_dir, bus)
        assert p.capture() is not None
        assert p.capture() is None  # same bytes, same overlays: nothing new to show
    assert len(list((run_dir / "screenshots" / "bare").glob("*.png"))) == 1


def test_changed_frames_get_the_next_number(run_dir: Path) -> None:
    frames = iter([good_output(tiny_png(rgb=(1, 2, 3))), good_output(tiny_png(rgb=(9, 9, 9)))])
    sandbox = FakeSandbox(lambda cmd: ok(next(frames)))
    with EventBus(run_dir / "events.jsonl", ab_id="ab-1") as bus:
        p = preview(sandbox, run_dir, bus)
        p.capture()
        second = p.capture()
    assert second is not None and second.data["path"] == "screenshots/bare/board-0002.png"


def test_conflict_view_is_requested_and_named(run_dir: Path) -> None:
    line = capture_line(
        "conflict", "admin@acme.test", [{"issue_id": 1, "mark": "lost_update"}], tiny_png()
    )
    sandbox = FakeSandbox(lambda cmd: ok(line))
    with EventBus(run_dir / "events.jsonl", ab_id="ab-1") as bus:
        event = preview(sandbox, run_dir, bus).capture("conflict")
    assert event is not None and event.data["path"] == "screenshots/bare/conflict-0001.png"
    assert "--view conflict" in sandbox.commands[0]


@pytest.mark.parametrize(
    ("output", "reason"),
    [
        ("no marker here", "no capture line"),
        (MARKER + "{not json", "not JSON"),
        (
            MARKER + json.dumps({"view": "board", "as_user": "a", "overlays": [], "png_b64": "!!"}),
            "base64",
        ),
        (
            MARKER
            + json.dumps(
                {
                    "view": "board",
                    "as_user": "a",
                    "overlays": [],
                    "png_b64": base64.b64encode(b"GIF89a....").decode(),
                }
            ),
            "PNG",
        ),
        (good_output(overlays=[{"issue_id": 1, "mark": "<script>"}]), "mark"),
        (good_output(overlays=[{"issue_id": "1; rm -rf", "mark": "duplicate"}]), "issue_id"),
        (capture_line("../../etc", "a", [], tiny_png()), "view"),
    ],
)
def test_untrusted_output_is_validated(output: str, reason: str) -> None:
    with pytest.raises(CaptureError, match=reason):
        parse_capture_output(output, max_png_bytes=1_000_000)


def test_oversized_png_is_rejected() -> None:
    with pytest.raises(CaptureError, match="too large"):
        parse_capture_output(good_output(tiny_png(width=200, height=200)), max_png_bytes=100)


def test_failed_or_invalid_captures_emit_nothing_and_keep_the_reason(run_dir: Path) -> None:
    results = iter([ExecResult(exit_code=1, output="Traceback ...", duration_ms=5), ok("garbage")])
    sandbox = FakeSandbox(lambda cmd: next(results))
    with EventBus(run_dir / "events.jsonl", ab_id="ab-1") as bus:
        p = preview(sandbox, run_dir, bus)
        assert p.capture() is None
        assert "exit 1" in p.last_error
        assert p.capture() is None
        assert "no capture line" in p.last_error
    assert list(read_events(run_dir / "events.jsonl")) == []


def test_start_server_runs_detached_then_waits_for_health(run_dir: Path) -> None:
    sandbox = FakeSandbox(lambda cmd: ok(""))
    with EventBus(run_dir / "events.jsonl", ab_id="ab-1") as bus:
        preview(sandbox, run_dir, bus).start_server()
    serve, wait = sandbox.commands
    assert "board_capture serve --app-dir /work --db /tmp/preview.db --port 8000" in serve
    assert serve.rstrip().endswith("&") and "nohup" in serve and "< /dev/null" in serve
    assert "> /tmp/preview-server.log 2>&1" in serve
    assert "board_capture wait --base-url http://127.0.0.1:8000" in wait


def test_start_server_raises_when_the_app_never_answers(run_dir: Path) -> None:
    def script(cmd: str) -> ExecResult:
        if " wait " in cmd:
            return ExecResult(exit_code=1, output="", duration_ms=1)
        if "tail" in cmd:
            return ok("alembic.util.exc.CommandError: Multiple head revisions")
        return ok("")

    with (
        EventBus(run_dir / "events.jsonl", ab_id="ab-1") as bus,
        pytest.raises(CaptureError, match="Multiple head revisions"),
    ):
        preview(FakeSandbox(script), run_dir, bus).start_server()


def test_run_captures_every_interval_until_stopped(run_dir: Path) -> None:
    count = {"n": 0}
    stop = threading.Event()

    def script(cmd: str) -> ExecResult:
        count["n"] += 1
        if count["n"] >= 3:
            stop.set()
        return ok(good_output(tiny_png(rgb=(count["n"], 0, 0))))

    with EventBus(run_dir / "events.jsonl", ab_id="ab-1") as bus:
        emitted = preview(FakeSandbox(script), run_dir, bus).run(stop, interval_s=0.01)
    assert emitted == 3
    assert len(list(read_events(run_dir / "events.jsonl"))) == 3


def test_paths_with_quotes_are_shell_quoted(run_dir: Path) -> None:
    sandbox = FakeSandbox(lambda cmd: ok(good_output()))
    with EventBus(run_dir / "events.jsonl", ab_id="ab-1") as bus:
        BoardPreview(
            sandbox, bus, run_dir, run_id="r", arm="harness", user="o'brien@acme.test"
        ).capture()
    assert "'o'\"'\"'brien@acme.test'" in sandbox.commands[0]
