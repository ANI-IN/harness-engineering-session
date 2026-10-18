"""The run list: what each run is (section, feature, type), whether it is still running, and when it
started, read from the run's ab.json and its events. A value the run does not record is shown as
"unknown", never guessed."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from shipharness.console.state import ConsoleState
from shipharness.datasets.names import SECTION_NAMES, feature_label, section_label
from shipharness.events import read_events

UNKNOWN = "unknown"
AB_RECORD = "ab.json"  # written by `shipharness ab` once both arms are judged (ab/demo.py)
_MODES = {
    "A/B": "A/B",
    "harness in action": "harness in action",
    "constructed example": "constructed example",
}


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    section: str
    feature: str
    kind: str
    status: str
    started: str


START_RECORD = "start.json"  # written by `shipharness ab` before any arm starts (ab/demo.py)


def _read(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _ab_record(run_dir: Path) -> dict[str, Any] | None:
    """What the run is: ab.json once the A/B is judged; while it runs, start.json (section, mode,
    feature), with the full record's fields winning where both have one."""
    start = _read(run_dir / START_RECORD) or {}
    full = _read(run_dir / AB_RECORD) or {}
    if not start and not full:
        return None
    merged: dict[str, Any] = dict(start)
    if start.get("feature_id"):
        merged["task"] = {"feature_id": start["feature_id"]}
    merged.update({k: v for k, v in full.items() if v is not None})
    return merged


def _section(value: object) -> str:
    """'Section 1: Instructions' for demo-1, 'Final project' for final, else unknown."""
    if value == "final":
        return "Final project"
    if isinstance(value, str) and value.startswith("demo-"):
        number = value.removeprefix("demo-")
        if number.isdigit() and int(number) in SECTION_NAMES:
            return section_label(int(number))
    return UNKNOWN


def _started(state: ConsoleState) -> str:
    stamps = [a._seen["launch"][1] for a in state.started if "launch" in a._seen]
    if not stamps:
        return UNKNOWN
    try:
        when = datetime.fromisoformat(min(stamps).replace("Z", "+00:00"))
    except ValueError:
        return UNKNOWN
    return when.strftime("%Y-%m-%d %H:%M UTC")


def run_finished(run_dir: Path, state: ConsoleState) -> bool:
    """Finished: ab.json is written (the A/B is judged), or every arm that started has ended and
    has its full verdict. A run of `shipharness run` (no referee, no A/B) is finished at run_end."""
    if (run_dir / AB_RECORD).is_file() or state.finished:
        return True
    arms = state.started
    no_referee = state.ab_id is None
    return no_referee and bool(arms) and all(a.run_end is not None for a in arms)


def run_summary(run_dir: Path) -> RunSummary:
    state = ConsoleState.from_events(read_events(run_dir / "events.jsonl"))
    record = _ab_record(run_dir) or {}
    task = record.get("task") if isinstance(record.get("task"), dict) else {}
    feature_code = task.get("feature_id") or state.feature
    if record.get("mode") in _MODES:
        kind = _MODES[str(record["mode"])]
    elif state.constructed:
        kind = "constructed example"
    elif state.single_arm:
        kind = "harness in action"
    elif {"bare", "harness"} <= {a.name for a in state.started}:
        kind = "A/B"
    else:
        kind = UNKNOWN
    return RunSummary(
        run_id=run_dir.name,
        section=_section(record.get("section")),
        feature=feature_label(str(feature_code)) if feature_code else UNKNOWN,
        kind=kind,
        status="finished" if run_finished(run_dir, state) else "running",
        started=_started(state),
    )
