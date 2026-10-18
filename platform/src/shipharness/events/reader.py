"""Read run logs without letting one bad line stop the reader.

A line that is not JSON, or is JSON but not a valid event (unknown type, missing fields, wrong
types, data that does not fit its type), is skipped: the reader logs one warning with the run id,
the line number and a short reason, and goes on with the next line. The warning never quotes the
line, which may hold agent text. A last line with no trailing newline is a line still being
written: it is held back (not skipped) and read again once it is complete.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import structlog
from pydantic import ValidationError

from shipharness.events.models import EVENT_DATA_MODELS, Event

SKIP_MESSAGE = "skipped malformed run-log line"


@dataclass(frozen=True)
class SkippedLine:
    """A run-log line the reader could not use. It carries no line content on purpose."""

    line: int  # 1-based line number in the log
    reason: str


class MalformedLine(ValueError):
    """A complete run-log line that is not a valid event. `reason` never quotes the line."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _reason(exc: ValidationError) -> str:
    errors = exc.errors(include_url=False, include_input=False, include_context=False)
    if any(error["type"] == "json_invalid" for error in errors):
        return "invalid JSON"
    if errors and all(e["loc"] == ("type",) and e["type"] == "literal_error" for e in errors):
        return "unknown event type"
    return "invalid event"


def parse_event_line(raw: bytes | str) -> Event:
    """One complete run-log line to an Event, checking `data` against its type's model.
    Raises MalformedLine with a short reason."""
    try:
        event = Event.model_validate_json(raw)
    except ValidationError as exc:
        raise MalformedLine(_reason(exc)) from None
    try:
        EVENT_DATA_MODELS[event.type].model_validate(event.data)
    except ValidationError:
        raise MalformedLine("invalid event data") from None
    return event


def _note_skipped(path: Path, line: int, reason: str, skipped: list[SkippedLine] | None) -> None:
    structlog.get_logger(__name__).warning(
        SKIP_MESSAGE, run_id=path.parent.name, line=line, reason=reason
    )
    if skipped is not None:
        skipped.append(SkippedLine(line, reason))


def read_events(
    log_path: Path, after_seq: int = 0, *, skipped: list[SkippedLine] | None = None
) -> Iterator[Event]:
    """Yield valid events from a run log with seq > after_seq. Malformed lines are logged and,
    when `skipped` is given, appended to it so a caller can count them."""
    path = Path(log_path)
    if not path.exists():
        return
    with path.open("rb") as handle:
        for number, raw in enumerate(handle, start=1):
            if not raw.endswith(b"\n"):
                break  # partial line still being written
            if not raw.strip():
                continue
            try:
                event = parse_event_line(raw)
            except MalformedLine as exc:
                _note_skipped(path, number, exc.reason, skipped)
                continue
            if event.seq > after_seq:
                yield event


class LogTail:
    """Read only the complete lines appended since the last call (byte offset), so following a
    long run log does not re-parse it on every poll and each malformed line is reported once.
    A partial last line stays unread until its newline arrives."""

    def __init__(self, path: Path, *, skipped: list[SkippedLine] | None = None) -> None:
        self.path = Path(path)
        self.offset = 0
        self.lines = 0  # complete lines consumed so far
        self.skipped = skipped

    def read(self) -> Iterator[Event]:
        try:
            with self.path.open("rb") as handle:
                handle.seek(self.offset)
                chunk = handle.read()
        except FileNotFoundError:
            return
        start = 0
        while (end := chunk.find(b"\n", start)) >= 0:
            raw = chunk[start:end]
            start = end + 1
            self.offset += len(raw) + 1
            self.lines += 1
            if not raw.strip():
                continue
            try:
                event = parse_event_line(raw)
            except MalformedLine as exc:
                _note_skipped(self.path, self.lines, exc.reason, self.skipped)
                continue
            yield event


def follow_events(
    log_path: Path,
    after_seq: int = 0,
    poll_s: float = 0.2,
    stop: Callable[[], bool] | None = None,
) -> Iterator[Event]:
    """Tail a run log, yielding each new event once, until `stop()` returns True."""
    tail = LogTail(log_path)
    last = after_seq
    while True:
        for event in tail.read():
            if event.seq > last:
                last = event.seq
                yield event
        if stop is not None and stop():
            return
        time.sleep(poll_s)
