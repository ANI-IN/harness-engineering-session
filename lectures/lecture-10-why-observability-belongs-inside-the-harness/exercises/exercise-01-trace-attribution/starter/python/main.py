"""trace-attribution: point each failing check at the recorded write that
broke it.

The workspace is a session's leavings and the trace is the event log that
session's harness wrote. For every check that fails now, the audit finds
the write that put the current value there and names the value it
overwrote, which is the only thing a repair can be grounded in. A failing
check whose key never appears in the trace is reported as unattributed:
the log covered the wrong surface, and for this question that is the same
as no log at all.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

INTEGER_RE = re.compile(r"^-?[0-9]+$")


def load_lines(workspace: Path, relative: str) -> list[str] | None:
    file = workspace / relative
    if not file.is_file():
        return None
    return file.read_text(encoding="utf-8").split("\n")


def read_key(lines: list[str], key: str) -> str | None:
    for line in lines:
        if line.startswith(f"{key}="):
            return line[len(key) + 1 :].strip()
    return None


def run_check(workspace: Path, check: dict) -> tuple[bool, str]:
    """One declared health check over the workspace as it is now."""
    path, key, rule = check["path"], check["key"], check["rule"]
    lines = load_lines(workspace, path)
    if lines is None:
        return False, f"{path} missing"
    value = read_key(lines, key)
    if value is None:
        return False, f"{path} has no {key}= line"
    if rule == "non-empty":
        if value:
            return True, f"{path} {key}={value} is set"
        return False, f"{path} {key} is empty"
    if rule == "positive-integer":
        if INTEGER_RE.match(value) and int(value) > 0:
            return True, f"{path} {key}={value} is a positive integer"
        return False, f"{path} {key}={value} is not a positive integer"
    raise ValueError(f"unknown check rule: {rule}")


def load_trace(trace: Path) -> list[dict]:
    events = []
    for line in trace.read_text(encoding="utf-8").split("\n"):
        if line.strip():
            events.append(json.loads(line))
    return events


def attribute(events: list[dict], path: str) -> dict | None:
    """The last recorded write to the file this check reads.

    A failing check names the file it reads, so the write that left the
    current value there is the last write the trace records against that
    file.
    """
    for event in reversed(events):
        if event["event"] != "workspace/write":
            continue
        if event["detail"]["path"] == path:
            return event
    return None


def audit(workspace: Path, trace: Path) -> dict:
    checks = json.loads((workspace / "checks.json").read_text(encoding="utf-8"))["checks"]
    events = load_trace(trace)
    diagnosis = []
    attributed = 0
    for check in checks:
        passed, _ = run_check(workspace, check)
        if passed:
            continue
        path, key = check["path"], check["key"]
        lines = load_lines(workspace, path) or []
        observed = read_key(lines, key) or ""
        found = attribute(events, path)
        if found is None:
            attribution = f"unattributed: the trace records no write to {key} in {path}"
            repair = "none"
        else:
            detail = found["detail"]
            attribution = (
                f"event {found['seq']} recorded step {detail['step']} setting "
                f"{detail['key']} in {detail['path']} from {detail['from']} to {detail['to']}"
            )
            repair = f"restore {detail['key']}={detail['from']} in {detail['path']}"
            attributed += 1
        diagnosis.append(
            {
                "check": check["id"],
                "path": path,
                "key": key,
                "observed": observed,
                "attribution": attribution,
                "repair": repair,
            }
        )
    unattributed = len(diagnosis) - attributed
    return {
        "workspace": workspace.name,
        "handoff": {"trace": trace.name, "events_read": len(events)},
        "diagnosis": diagnosis,
        "outcome": {
            "failing": len(diagnosis),
            "attributed": attributed,
            "unattributed": unattributed,
            "result": "located" if unattributed == 0 else "blind",
        },
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: main.py <workspace-dir> <trace-file>", file=sys.stderr)
        return 2
    workspace, trace = Path(argv[1]), Path(argv[2])
    if not workspace.is_dir() or not (workspace / "checks.json").is_file():
        print(f"error: not a workspace (no checks.json): {workspace}", file=sys.stderr)
        return 2
    if not trace.is_file():
        print(f"error: not a trace file: {trace}", file=sys.stderr)
        return 2
    report = audit(workspace, trace)
    print(json.dumps(report, indent=2))
    return 0 if report["outcome"]["result"] == "located" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
