"""Replay a recorded run log: every re-emitted event carries recorded=True (RECORDING badge)."""

from __future__ import annotations

from pathlib import Path

import structlog

from shipharness.events.bus import EventBus
from shipharness.events.reader import SkippedLine, read_events


def replay(log_path: Path, bus: EventBus, *, skipped: list[SkippedLine] | None = None) -> int:
    """Re-emit all valid events from `log_path` onto `bus`. Returns the number of events replayed.
    Malformed lines are not replayed: each is appended to `skipped` (when given), and a summary
    warning gives their count so a replay with gaps is never silent."""
    found: list[SkippedLine] = [] if skipped is None else skipped
    before = len(found)
    count = 0
    for event in read_events(log_path, skipped=found):
        bus.publish(event.type, event.data, run_id=event.run_id, arm=event.arm, recorded=True)
        count += 1
    if missed := len(found) - before:
        structlog.get_logger(__name__).warning(
            "replay skipped malformed run-log lines",
            run_id=Path(log_path).parent.name,
            skipped=missed,
            replayed=count,
        )
    return count
