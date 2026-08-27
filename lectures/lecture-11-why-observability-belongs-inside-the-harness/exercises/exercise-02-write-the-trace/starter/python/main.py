"""write-the-trace: the harness side of observability.

The session writes settings into an in-memory overlay of the workspace and
the harness records one `workspace/write` event per change. The event's
`from` is what makes the log worth keeping: it is the only place the
overwritten value survives.

The second half of the program is the consumer, complete and unchanged: it
runs the workspace's declared checks against the finished overlay and
attributes each failure to the last recorded write to that key. A log with
a wrong `from` still attributes, and still proposes a repair; the repair
just restores the wrong value.
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


def write_key(lines: list[str], key: str, value: str) -> None:
    for index, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[index] = f"{key}={value}"
            return
    lines.append(f"{key}={value}")


class Overlay:
    """The workspace as the session sees it: files loaded on first touch and
    modified in memory until the session ends."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.files: dict[str, list[str]] = {}

    def lines(self, relative: str) -> list[str] | None:
        if relative not in self.files:
            loaded = load_lines(self.workspace, relative)
            if loaded is None:
                return None
            self.files[relative] = loaded
        return self.files[relative]

    def get(self, relative: str, key: str) -> str | None:
        lines = self.lines(relative)
        return None if lines is None else read_key(lines, key)

    def set(self, relative: str, key: str, value: str) -> None:
        if self.lines(relative) is None:
            self.files[relative] = []
        write_key(self.files[relative], key, value)


def run_check(overlay: Overlay, check: dict) -> tuple[bool, str]:
    path, key, rule = check["path"], check["key"], check["rule"]
    lines = overlay.lines(path)
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


def run_session(workspace: Path) -> tuple[list[dict], Overlay]:
    """Replay the plan and record the trace as the harness would."""
    plan = json.loads((workspace / "plan.json").read_text(encoding="utf-8"))
    overlay = Overlay(workspace)
    events: list[dict] = []

    def emit(event: str, detail: dict) -> None:
        events.append(
            {
                "seq": len(events) + 1,
                "level": "INFO",
                "command": "build",
                "event": event,
                "detail": detail,
            }
        )

    emit("session/start", {"task": plan["task"]})
    for number, step in enumerate(plan["steps"], 1):
        write = step["write"]
        path, key, value = write["path"], write["key"], write["value"]
        # Record what the value was before this step overwrote it.
        before = read_key(load_lines(workspace, path) or [], key) or ""
        overlay.set(path, key, value)
        emit(
            "workspace/write",
            {"step": number, "path": path, "key": key, "from": before, "to": value},
        )
    emit("session/end", {"steps": len(plan["steps"]), "declared": "done"})
    return events, overlay


def attribute(events: list[dict], path: str, key: str) -> dict | None:
    """The last recorded write to this exact key in this exact file."""
    for event in reversed(events):
        if event["event"] != "workspace/write":
            continue
        detail = event["detail"]
        if detail["path"] == path and detail["key"] == key:
            return event
    return None


def report(workspace: Path) -> dict:
    events, overlay = run_session(workspace)
    checks = json.loads((workspace / "checks.json").read_text(encoding="utf-8"))["checks"]
    repair_plan = []
    attributed = 0
    for check in checks:
        passed, detail_text = run_check(overlay, check)
        if passed:
            continue
        path, key = check["path"], check["key"]
        found = attribute(events, path, key)
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
        repair_plan.append(
            {
                "check": check["id"],
                "failure": detail_text,
                "attribution": attribution,
                "repair": repair,
            }
        )
    unattributed = len(repair_plan) - attributed
    return {
        "workspace": workspace.name,
        "events": events,
        "repair_plan": repair_plan,
        "outcome": {
            "failing": len(repair_plan),
            "attributed": attributed,
            "unattributed": unattributed,
            "result": "located" if unattributed == 0 else "blind",
        },
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: main.py <workspace-dir>", file=sys.stderr)
        return 2
    workspace = Path(argv[1])
    if not workspace.is_dir():
        print(f"error: not a directory: {workspace}", file=sys.stderr)
        return 2
    for required in ("plan.json", "checks.json"):
        if not (workspace / required).is_file():
            print(f"error: not a workspace (no {required}): {workspace}", file=sys.stderr)
            return 2
    result = report(workspace)
    print(json.dumps(result, indent=2))
    return 0 if result["outcome"]["result"] == "located" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
