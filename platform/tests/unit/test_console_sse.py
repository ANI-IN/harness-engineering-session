from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from shipharness.console.app import LogTail, create_console_app, screen_updates, sse_events
from shipharness.console.screens import ScreenRenderer
from shipharness.events import EventBus

SKIP_MESSAGE = "skipped malformed run-log line"


def write_events(log: Path, count: int) -> None:
    with EventBus(log, ab_id="ab-1") as bus:
        for n in range(count):
            bus.publish(
                "tool_call",
                {"call_id": f"c{n}", "name": "read_file", "target": f"f{n}.py"},
                run_id="r-1",
                arm="bare",
            )


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    write_events(tmp_path / "ab-1" / "events.jsonl", 5)
    return tmp_path


def test_replay_after_last_event_id(runs_dir: Path) -> None:
    async def collect() -> list[dict[str, str]]:
        log = runs_dir / "ab-1" / "events.jsonl"
        return [m async for m in sse_events(log, after_seq=2, follow=False)]

    messages = asyncio.run(collect())
    assert [m["id"] for m in messages] == ["3", "4", "5"]
    assert all(m["event"] == "tool_call" for m in messages)


def test_follow_delivers_events_appended_later_exactly_once(runs_dir: Path) -> None:
    log = runs_dir / "ab-1" / "events.jsonl"

    async def scenario() -> list[str]:
        seen: list[str] = []
        stop = False

        async def consume() -> None:
            async for message in sse_events(
                log, after_seq=2, follow=True, poll_s=0.01, should_stop=lambda: stop
            ):
                seen.append(message["id"])

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.1)
        write_events(log, 1)  # becomes seq 6
        await asyncio.sleep(0.1)
        stop = True
        await asyncio.wait_for(task, timeout=2)
        return seen

    assert asyncio.run(scenario()) == ["3", "4", "5", "6"]


def test_http_stream_honours_last_event_id(runs_dir: Path) -> None:
    client = TestClient(create_console_app(runs_dir))
    response = client.get("/events/ab-1?follow=false", headers={"Last-Event-ID": "2"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "id: 3" in body and "id: 5" in body
    assert "id: 2\r\n" not in body and "id: 2\n" not in body
    assert "event: tool_call" in body


def test_unknown_run_is_404(runs_dir: Path) -> None:
    client = TestClient(create_console_app(runs_dir))
    assert client.get("/events/ab-missing?follow=false").status_code == 404


@pytest.mark.parametrize("bad", ["..", "ab-1..", "a b", "ab%2F..%2Fx"])
def test_run_ids_cannot_escape_the_runs_dir(runs_dir: Path, bad: str) -> None:
    client = TestClient(create_console_app(runs_dir))
    response = client.get(f"/events/{bad}?follow=false")
    streamed = response.headers.get("content-type", "").startswith("text/event-stream")
    assert not (response.status_code == 200 and streamed)


def test_index_page_renders(runs_dir: Path) -> None:
    response = TestClient(create_console_app(runs_dir)).get("/")
    assert response.status_code == 200
    assert "shipharness console" in response.text
    assert "ab-1" in response.text


# --- A malformed run-log line must not stop the live stream --------------------------------------

SECRET = "AGENT-TEXT-DO-NOT-LOG"
NOT_JSON = f'{{"seq": 99, "type": "turn", "data": "{SECRET}"\n'.encode()
UNKNOWN_TYPE = (
    b'{"v": 1, "ab_id": null, "run_id": null, "arm": null, "seq": 50, "ts": "t", '
    b'"type": "' + SECRET.encode() + b'", "data": {}, "recorded": false}\n'
)


def valid_lines(tmp_path: Path, count: int) -> list[bytes]:
    """`count` valid run-log lines (seq 1..count), each ending in a newline."""
    source = tmp_path / "source" / "events.jsonl"
    write_events(source, count)
    return source.read_bytes().splitlines(keepends=True)


def corrupt_run(tmp_path: Path, bad: bytes = NOT_JSON) -> Path:
    """runs/ab-bad/events.jsonl: event 1, a bad line, events 2 and 3."""
    one, two, three = valid_lines(tmp_path, 3)
    log = tmp_path / "runs" / "ab-bad" / "events.jsonl"
    log.parent.mkdir(parents=True)
    log.write_bytes(one + bad + two + three)
    return log


def collect(log: Path, after_seq: int = 0) -> list[str]:
    async def run() -> list[str]:
        return [m["id"] async for m in sse_events(log, after_seq=after_seq, follow=False)]

    return asyncio.run(run())


def skip_warnings(logs: list[dict[str, object]]) -> list[dict[str, object]]:
    return [r for r in logs if r["log_level"] == "warning" and r.get("event") == SKIP_MESSAGE]


def test_malformed_line_between_valid_events_streams_both(tmp_path: Path) -> None:
    assert collect(corrupt_run(tmp_path)) == ["1", "2", "3"]


@pytest.mark.parametrize(
    "bad",
    [
        UNKNOWN_TYPE,
        b'{"v": 1, "seq": 7}\n',  # missing envelope fields
        b'{"v": 1, "ab_id": null, "run_id": null, "arm": null, "seq": "x", "ts": "t", '
        b'"type": "tool_call", "data": {}, "recorded": false}\n',  # wrong type for seq
        b'{"v": 1, "ab_id": null, "run_id": null, "arm": null, "seq": 9, "ts": "t", '
        b'"type": "tool_call", "data": {"call_id": 5}, "recorded": false}\n',  # bad data
        b"[1, 2, 3]\n",
        b"\xff\xfe not utf-8\n",
    ],
    ids=["unknown-type", "missing-fields", "wrong-type", "bad-data", "not-object", "not-utf8"],
)
def test_invalid_event_json_line_is_skipped(tmp_path: Path, bad: bytes) -> None:
    assert collect(corrupt_run(tmp_path, bad)) == ["1", "2", "3"]


def test_resume_after_the_bad_line_delivers_the_rest_exactly_once(tmp_path: Path) -> None:
    log = corrupt_run(tmp_path)
    assert collect(log, after_seq=1) == ["2", "3"]
    client = TestClient(create_console_app(log.parent.parent))
    body = client.get("/events/ab-bad?follow=false", headers={"Last-Event-ID": "1"}).text
    ids = [line for line in body.splitlines() if line.startswith("id: ")]
    assert ids == ["id: 2", "id: 3"]


def test_partial_line_followed_by_its_completion_yields_the_event_once(tmp_path: Path) -> None:
    one, two, three = valid_lines(tmp_path, 3)
    log = tmp_path / "runs" / "ab-p" / "events.jsonl"
    log.parent.mkdir(parents=True)
    log.write_bytes(one + NOT_JSON + two[:20])

    async def scenario() -> list[str]:
        seen: list[str] = []
        stop = False

        async def consume() -> None:
            async for message in sse_events(
                log, follow=True, poll_s=0.01, should_stop=lambda: stop
            ):
                seen.append(message["id"])

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.08)
        with log.open("ab") as handle:
            handle.write(two[20:])
        await asyncio.sleep(0.08)
        with log.open("ab") as handle:
            handle.write(three)
        await asyncio.sleep(0.08)
        stop = True
        await asyncio.wait_for(task, timeout=2)
        return seen

    with capture_logs() as logs:
        assert asyncio.run(scenario()) == ["1", "2", "3"]
    # Only the malformed line is reported; the partial line was held, never skipped.
    assert [w["line"] for w in skip_warnings(logs)] == [2]


def test_log_tail_holds_a_partial_line_until_it_is_complete(tmp_path: Path) -> None:
    one, two = valid_lines(tmp_path, 2)
    log = tmp_path / "events.jsonl"
    log.write_bytes(one + NOT_JSON + two[:10])
    tail = LogTail(log)
    assert [e.seq for e in tail.read()] == [1]
    assert [e.seq for e in tail.read()] == []
    with log.open("ab") as handle:
        handle.write(two[10:])
    assert [e.seq for e in tail.read()] == [2]
    assert [e.seq for e in tail.read()] == []


def test_skipped_line_is_logged_once_without_its_content(tmp_path: Path) -> None:
    log = corrupt_run(tmp_path)

    async def scenario() -> list[str]:
        seen: list[str] = []
        polls = 0

        def stop() -> bool:
            nonlocal polls
            polls += 1
            return polls > 5

        async for message in sse_events(log, follow=True, poll_s=0.01, should_stop=stop):
            seen.append(message["id"])
        return seen

    with capture_logs() as logs:
        assert asyncio.run(scenario()) == ["1", "2", "3"]
    [warning] = skip_warnings(logs)
    assert warning["run_id"] == "ab-bad"
    assert warning["line"] == 2
    assert warning["reason"] == "invalid JSON"
    assert all(SECRET not in repr(record) for record in logs)


def test_unknown_type_reason_does_not_echo_the_type(tmp_path: Path) -> None:
    log = corrupt_run(tmp_path, UNKNOWN_TYPE)
    with capture_logs() as logs:
        assert collect(log) == ["1", "2", "3"]
    [warning] = skip_warnings(logs)
    assert warning["reason"] == "unknown event type"
    assert all(SECRET not in repr(record) for record in logs)


def test_screen_stream_survives_a_malformed_line(tmp_path: Path) -> None:
    log = corrupt_run(tmp_path)
    exports = tmp_path / "exports"
    exports.mkdir()

    async def run() -> list[dict[str, str]]:
        renderer = ScreenRenderer()
        return [m async for m in screen_updates(log, exports, renderer, "ab-bad", follow=False)]

    [message] = asyncio.run(run())
    assert message["id"] == "3"


def test_run_page_renders_despite_a_malformed_line(tmp_path: Path) -> None:
    log = corrupt_run(tmp_path)
    exports = tmp_path / "exports"
    exports.mkdir()
    response = TestClient(create_console_app(log.parent.parent, exports)).get("/run/ab-bad")
    assert response.status_code == 200
