from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from structlog.testing import capture_logs

from shipharness.events import (
    EVENT_DATA_MODELS,
    Event,
    EventBus,
    RunLogLocked,
    SkippedLine,
    read_events,
    replay,
)

CONTRACT_EVENT_TYPES = {
    "run_start",
    "sandbox_start",
    "sandbox_usage",
    "sandbox_denied",
    "turn",
    "tool_call",
    "tool_result",
    "harness_decision",
    "blocked",
    "session_stop",
    "session_resume",
    "test_proposed",
    "test_filter_result",
    "check_progress",
    "check_result",
    "mutant_result",
    "reviewer_output",
    "gate_result",
    "claim",
    "primary_verdict",
    "verdict",
    "cost",
    "screenshot",
    "trace_link",
    "run_end",
}


def tool_call_data(n: int) -> dict[str, object]:
    return {"call_id": f"c{n}", "name": "read_file", "target": f"app/file{n}.py"}


def test_every_contract_event_type_has_a_data_model() -> None:
    assert set(EVENT_DATA_MODELS) == CONTRACT_EVENT_TYPES


def test_seq_starts_at_one_and_increments(tmp_path: Path) -> None:
    with EventBus(tmp_path / "events.jsonl", ab_id="ab-1") as bus:
        first = bus.publish("tool_call", tool_call_data(1), run_id="r-1", arm="bare")
        second = bus.publish("tool_call", tool_call_data(2), run_id="r-1", arm="bare")
    assert (first.seq, second.seq) == (1, 2)


def test_published_event_round_trips_through_the_log(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id="ab-1") as bus:
        sent = bus.publish("tool_call", tool_call_data(1), run_id="r-1", arm="harness")
    [read] = list(read_events(log))
    assert read == sent
    assert read.ab_id == "ab-1"
    assert read.recorded is False


def test_invalid_data_is_rejected_and_nothing_is_written(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id=None) as bus, pytest.raises(ValidationError):
        bus.publish("tool_call", {"call_id": "c1"}, run_id="r-1", arm="bare")
    assert list(read_events(log)) == []


def test_unknown_event_type_is_rejected(tmp_path: Path) -> None:
    with EventBus(tmp_path / "events.jsonl", ab_id=None) as bus, pytest.raises(ValueError):
        bus.publish("not_a_type", {}, run_id=None, arm=None)  # type: ignore[arg-type]


def test_read_events_after_seq(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id=None) as bus:
        for n in range(5):
            bus.publish("tool_call", tool_call_data(n), run_id="r-1", arm="bare")
    assert [e.seq for e in read_events(log, after_seq=3)] == [4, 5]


def test_second_bus_on_same_log_is_rejected(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id=None), pytest.raises(RunLogLocked):
        EventBus(log, ab_id=None)


def test_bus_reopened_after_close_continues_seq(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    with EventBus(log, ab_id=None) as bus:
        bus.publish("tool_call", tool_call_data(1), run_id="r-1", arm="bare")
    with EventBus(log, ab_id=None) as bus:
        again = bus.publish("tool_call", tool_call_data(2), run_id="r-1", arm="bare")
    assert again.seq == 2


def test_listeners_receive_each_event(tmp_path: Path) -> None:
    seen: list[Event] = []
    with EventBus(tmp_path / "events.jsonl", ab_id=None) as bus:
        bus.add_listener(seen.append)
        bus.publish("tool_call", tool_call_data(1), run_id="r-1", arm="bare")
    assert [e.type for e in seen] == ["tool_call"]


def test_replay_marks_events_recorded_and_keeps_content(tmp_path: Path) -> None:
    source = tmp_path / "original.jsonl"
    with EventBus(source, ab_id="ab-1") as bus:
        bus.publish("tool_call", tool_call_data(1), run_id="r-1", arm="bare")
        bus.publish(
            "claim",
            {"phase": "build", "claim": "done", "summary": "ok", "gate_id": None},
            run_id="r-1",
            arm="bare",
        )
    target = tmp_path / "replay.jsonl"
    with EventBus(target, ab_id="ab-1") as bus:
        replay(source, bus)
    original, replayed = list(read_events(source)), list(read_events(target))
    assert [e.type for e in replayed] == [e.type for e in original]
    assert [e.data for e in replayed] == [e.data for e in original]
    assert all(e.recorded for e in replayed)


SECRET = "AGENT-TEXT-DO-NOT-LOG"


def log_with_bad_lines(tmp_path: Path) -> Path:
    """Events 1..3 with an invalid-JSON line and an invalid-event line between them, and a
    partial (unterminated) last line still being written."""
    source = tmp_path / "source.jsonl"
    with EventBus(source, ab_id=None) as bus:
        for n in range(3):
            bus.publish("tool_call", tool_call_data(n), run_id="r-1", arm="bare")
    one, two, three = source.read_bytes().splitlines(keepends=True)
    log = tmp_path / "run-x" / "events.jsonl"
    log.parent.mkdir()
    bad_json = f'{{"note": "{SECRET}"\n'.encode()
    bad_event = f'{{"v": 1, "seq": 9, "type": "{SECRET}"}}\n'.encode()
    log.write_bytes(one + bad_json + two + bad_event + three + three[:15])
    return log


def test_read_events_skips_malformed_lines_and_reports_them(tmp_path: Path) -> None:
    log = log_with_bad_lines(tmp_path)
    skipped: list[SkippedLine] = []
    with capture_logs() as logs:
        assert [e.seq for e in read_events(log, skipped=skipped)] == [1, 2, 3]
    assert [(s.line, s.reason) for s in skipped] == [(2, "invalid JSON"), (4, "invalid event")]
    warnings = [r for r in logs if r["log_level"] == "warning"]
    assert [(w["run_id"], w["line"]) for w in warnings] == [("run-x", 2), ("run-x", 4)]
    assert all(SECRET not in repr(record) for record in logs)


def test_read_events_rejects_event_data_that_does_not_fit_its_type(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    log.write_text(
        '{"v": 1, "ab_id": null, "run_id": null, "arm": null, "seq": 1, "ts": "t", '
        '"type": "turn", "data": {"turn": "x"}, "recorded": false}\n',
        encoding="utf-8",
    )
    skipped: list[SkippedLine] = []
    assert list(read_events(log, skipped=skipped)) == []
    assert [s.reason for s in skipped] == ["invalid event data"]


def test_bus_opens_a_log_with_a_malformed_line(tmp_path: Path) -> None:
    log = log_with_bad_lines(tmp_path)
    log.write_bytes(log.read_bytes().rsplit(b"\n", 1)[0] + b"\n")  # drop the partial line
    with EventBus(log, ab_id=None) as bus:
        again = bus.publish("tool_call", tool_call_data(4), run_id="r-1", arm="bare")
    assert again.seq == 4


def test_replay_counts_skipped_lines(tmp_path: Path) -> None:
    source = log_with_bad_lines(tmp_path)
    target = tmp_path / "replay.jsonl"
    skipped: list[SkippedLine] = []
    with capture_logs() as logs, EventBus(target, ab_id=None) as bus:
        assert replay(source, bus, skipped=skipped) == 3
    assert len(skipped) == 2
    [summary] = [r for r in logs if r["event"] == "replay skipped malformed run-log lines"]
    assert summary["skipped"] == 2
    assert [e.seq for e in read_events(target)] == [1, 2, 3]
