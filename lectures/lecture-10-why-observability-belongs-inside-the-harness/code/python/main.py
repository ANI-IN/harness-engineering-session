"""resume-trace: one build session, one resume session, and the event log
that decides whether the second one can finish the first one's work.

`build` replays a deterministic scripted session over a workspace. It walks
a plan, writes key/value settings, leaves a session note, and declares done.
Under `--observability=structured` the harness also appends one structured
event per write to `log/events.jsonl`; under `--observability=none` it does
not. Nothing else about the session changes: same plan, same steps, same
resulting files, same note.

`resume` is the next session. It replays the build to obtain the workspace
and the handoff artifacts the build left behind (never the build's report:
stdout does not survive a session boundary), runs the workspace's declared
checks, and for every failing check tries to attribute the write that broke
it and restore the value that write overwrote. With the event log it can;
without it the overwritten value exists nowhere and the repair is
impossible, so the workspace stays broken and the exit code says so.

All session writes land in an in-memory overlay of the workspace; the
fixtures on disk are never modified. SPEC.md pins the plan format, the check
rules, the event shape, and the resume procedure.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

INTEGER_RE = re.compile(r"^-?[0-9]+$")
SESSION_NOTE = "notes/session-note.md"
EVENT_LOG = "log/events.jsonl"


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
    modified in memory. The seam where a real harness would write to disk."""

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
    """One declared health check. Rules are `non-empty` (the key carries a
    value) and `positive-integer` (the value parses as an integer above
    zero); details name the file, the key, and the observed value."""
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


def session_note(task: str, steps: int) -> list[str]:
    """What the session writes about itself. Prose, unstructured, and
    identical under both observability modes: the agent's self-report is the
    constant here, the harness's event log is the variable."""
    return [
        "# Session note",
        "",
        f"Task: {task}",
        f"Implemented the plan end to end; {steps} steps completed.",
        "No verification was run in this session.",
    ]


def run_build(workspace: Path, observability: str) -> tuple[list[dict], dict]:
    """The first session. Returns its transcript (stdout, which ends with the
    session) and its artifacts (files, note, log: the only things the next
    session can read)."""
    plan = json.loads((workspace / "plan.json").read_text(encoding="utf-8"))
    overlay = Overlay(workspace)
    events: list[dict] = []
    transcript: list[dict] = []

    def emit(event: str, detail: dict) -> None:
        if observability != "structured":
            return
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
        before = overlay.get(path, key) or ""
        overlay.set(path, key, value)
        emit(
            "workspace/write",
            {"step": number, "path": path, "key": key, "from": before, "to": value},
        )
        transcript.append(
            {
                "step": number,
                "action": step["action"],
                "outcome": f"{path} {key}={value} (was {before or 'unset'})",
            }
        )
    emit("session/end", {"steps": len(plan["steps"]), "declared": "done"})

    note = session_note(plan["task"], len(plan["steps"]))
    files = [SESSION_NOTE] + ([EVENT_LOG] if observability == "structured" else [])
    artifacts = {
        "overlay": overlay,
        "files": sorted(files),
        "note": note,
        "log": [json.dumps(event, separators=(",", ":")) for event in events],
        "task": plan["task"],
    }
    return transcript, artifacts


def build_report(workspace: Path, observability: str) -> dict:
    transcript, artifacts = run_build(workspace, observability)
    return {
        "workspace": workspace.name,
        "observability": observability,
        "task": artifacts["task"],
        "transcript": transcript,
        "handoff": {
            "files": artifacts["files"],
            "session_note": artifacts["note"],
            "events": [json.loads(line) for line in artifacts["log"]],
        },
        "declared": "done",
    }


def attribute(events: list[dict], path: str, key: str) -> dict | None:
    """The last recorded write to this exact key in this exact file. Scanning
    the file alone is not enough: a later write to a different key in the
    same file is not what broke this check."""
    for event in reversed(events):
        if event["event"] != "workspace/write":
            continue
        detail = event["detail"]
        if detail["path"] == path and detail["key"] == key:
            return event
    return None


def resume_report(workspace: Path, observability: str) -> dict:
    """The second session. It receives the build's artifacts and nothing
    else, diagnoses every failing check, and repairs what it can attribute."""
    _, artifacts = run_build(workspace, observability)
    overlay: Overlay = artifacts["overlay"]
    events = [json.loads(line) for line in artifacts["log"]]
    checks = json.loads((workspace / "checks.json").read_text(encoding="utf-8"))["checks"]

    failing = [check for check in checks if not run_check(overlay, check)[0]]
    diagnosis = []
    repaired = 0
    for check in failing:
        path, key = check["path"], check["key"]
        observed = overlay.get(path, key) or ""
        found = attribute(events, path, key)
        if found is None:
            attribution = f"unattributed: the handoff records no write to {key} in {path}"
            repair = "none"
        else:
            detail = found["detail"]
            attribution = (
                f"event {found['seq']} recorded step {detail['step']} setting "
                f"{detail['key']} in {detail['path']} from {detail['from']} to {detail['to']}"
            )
            repair = f"restore {detail['key']}={detail['from']} in {detail['path']}"
            overlay.set(path, key, detail["from"])
            repaired += 1
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

    recheck = []
    failing_after = 0
    for check in checks:
        passed, detail = run_check(overlay, check)
        failing_after += 0 if passed else 1
        recheck.append(
            {"id": check["id"], "status": "pass" if passed else "fail", "detail": detail}
        )

    return {
        "workspace": workspace.name,
        "observability": observability,
        "handoff": {"files": artifacts["files"], "events_read": len(events)},
        "diagnosis": diagnosis,
        "recheck": recheck,
        "outcome": {
            "failing_before": len(failing),
            "repaired": repaired,
            "failing_after": failing_after,
            "result": "resumed" if failing_after == 0 else "stuck",
        },
    }


def resolve_workspace(arg: str) -> Path | None:
    workspace = Path(arg)
    if not workspace.is_dir():
        print(f"error: not a directory: {workspace}", file=sys.stderr)
        return None
    for required in ("plan.json", "checks.json"):
        if not (workspace / required).is_file():
            print(f"error: not a workspace (no {required}): {workspace}", file=sys.stderr)
            return None
    return workspace


def main(argv: list[str]) -> int:
    usage = (
        "usage: main.py build|resume <workspace-dir> --observability=structured|none"
    )
    if len(argv) != 4 or argv[1] not in ("build", "resume"):
        print(usage, file=sys.stderr)
        return 2
    if argv[3] not in ("--observability=structured", "--observability=none"):
        print(usage, file=sys.stderr)
        return 2
    observability = argv[3].split("=", 1)[1]
    workspace = resolve_workspace(argv[2])
    if workspace is None:
        return 2
    if argv[1] == "build":
        print(json.dumps(build_report(workspace, observability), indent=2))
        return 0
    report = resume_report(workspace, observability)
    print(json.dumps(report, indent=2))
    return 0 if report["outcome"]["result"] == "resumed" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
