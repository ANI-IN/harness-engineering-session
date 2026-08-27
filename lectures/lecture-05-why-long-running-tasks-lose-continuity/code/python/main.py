"""session-simulator: three sessions on one task, with and without handoff.

A deterministic replay of a fixed timeline. With the handoff artifacts
(claude-progress.md + session-handoff.md), later sessions reacquire context
by reading two short files and continue the recorded work. Without them,
each later session pays the full repository scan, restarts in-progress
work, and re-makes an already-made decision. Every cost is computed from
the fixture files; SPEC.md pins the timeline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def line_count(path: Path) -> int:
    lines = path.read_text(encoding="utf-8").split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return len(lines)


def simulate(workspace: Path, handoff: bool) -> dict:
    progress_lines = line_count(workspace / "claude-progress.md")
    handoff_lines = line_count(workspace / "session-handoff.md")
    repo_map = json.loads((workspace / "repo-map.json").read_text(encoding="utf-8"))
    scan_lines = sum(entry["lines"] for entry in repo_map["files"])
    features = json.loads((workspace / "feature_list.json").read_text(encoding="utf-8"))
    statuses = {f["id"]: f["status"] for f in features["features"]}
    in_progress = next(f["id"] for f in features["features"] if f["status"] == "in-progress")
    not_started = next(f["id"] for f in features["features"] if f["status"] == "not-started")
    already_passing = sum(1 for status in statuses.values() if status == "passing")

    reacquired = ["next-step", "open-failure", "decisions", "feature-statuses"]
    sessions = [{
        "session": 1,
        "reacquisition_lines": 0,
        "recovered": [],
        "work": f"implemented half of {in_progress}; recorded progress, handoff, and statuses",
        "rework": False,
        "decision_drift": False,
    }]

    if handoff:
        sessions.append({
            "session": 2,
            "reacquisition_lines": progress_lines + handoff_lines,
            "recovered": reacquired,
            "work": f"resumed {in_progress} via the recorded reproduce command; finished it",
            "rework": False,
            "decision_drift": False,
        })
        sessions.append({
            "session": 3,
            "reacquisition_lines": progress_lines + handoff_lines,
            "recovered": reacquired,
            "work": f"completed {not_started}",
            "rework": False,
            "decision_drift": False,
        })
        completed = already_passing + 2
    else:
        sessions.append({
            "session": 2,
            "reacquisition_lines": scan_lines,
            "recovered": [],
            "work": f"could not see that {in_progress} was underway; restarted it "
                    "from scratch and re-decided the date-storage approach",
            "rework": True,
            "decision_drift": True,
        })
        sessions.append({
            "session": 3,
            "reacquisition_lines": scan_lines,
            "recovered": [],
            "work": f"re-explored the repository and finished {in_progress}; "
                    f"{not_started} was never reached",
            "rework": False,
            "decision_drift": True,
        })
        completed = already_passing + 1

    return {
        "handoff": handoff,
        "sessions": sessions,
        "totals": {
            "reacquisition_lines": sum(s["reacquisition_lines"] for s in sessions),
            "features_completed": completed,
            "rework_sessions": sum(1 for s in sessions if s["rework"]),
            "drift_events": sum(1 for s in sessions if s["decision_drift"]),
        },
    }


def compare_table(workspace: Path) -> str:
    lines = ["mode | reacquisition_lines | features_completed | rework_sessions | drift_events"]
    for handoff, label in ((True, "with-handoff"), (False, "no-handoff")):
        totals = simulate(workspace, handoff)["totals"]
        lines.append(
            f"{label} | {totals['reacquisition_lines']} | {totals['features_completed']} | "
            f"{totals['rework_sessions']} | {totals['drift_events']}"
        )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    args = argv[1:]
    no_handoff = "--no-handoff" in args
    compare = "--compare" in args
    positional = [a for a in args if not a.startswith("--")]
    if len(positional) != 1 or (no_handoff and compare):
        print("usage: main.py <workspace-dir> [--no-handoff | --compare]", file=sys.stderr)
        return 2
    workspace = Path(positional[0])
    if not workspace.is_dir():
        print(f"error: workspace not found: {workspace}", file=sys.stderr)
        return 2

    if compare:
        print(compare_table(workspace))
    else:
        print(json.dumps(simulate(workspace, not no_handoff), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
