"""scope-replay: the same scripted session under two tracking regimes.

`replay` is the demo: a deterministic scripted session finishes "the rest
of the project" in a workspace, taking its beliefs from whichever tracking
artifact the workspace carries (a prose `notes.md` or a canonical
`feature_list.json`). The session never sees `project.json`, the recorded
ground truth the deterministic fake agent replays; the closing audit does,
and grades the session's "done" claim by running every scope feature's
real verification outcome. On the memo workspace the claim is false (exit
1); on the tracked workspace the same session ends verified (exit 0).
`plan` is the supporting surface: it prints only what a fresh session can
ground in the tracker, with no ground truth at all. SPEC.md pins the memo
reading rule, the step scripts, and the audit templates.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MEMO_LINE = re.compile(r"^- ([a-z][a-z0-9]*(?:-[a-z0-9]+)*): (.+)$")
REMAINING_WORDS = ("need", "todo")


def parse_memo(text: str) -> list[tuple[str, str]]:
    mentions = []
    for line in text.splitlines():
        match = MEMO_LINE.match(line)
        if match:
            mentions.append((match.group(1), match.group(2).strip()))
    return mentions


def reads_as_remaining(prose: str) -> bool:
    lowered = prose.lower()
    return any(word in lowered for word in REMAINING_WORDS)


def find_tracker(workspace: Path) -> str | None:
    if (workspace / "feature_list.json").is_file():
        return "feature_list.json"
    if (workspace / "notes.md").is_file():
        return "notes.md"
    return None


def replay(workspace: Path, tracker: str) -> tuple[dict, int]:
    project = json.loads((workspace / "project.json").read_text(encoding="utf-8"))
    truth = {feature["id"]: dict(feature) for feature in project["features"]}
    events: list[dict] = []
    step = 0
    wasted = 0
    believed: dict[str, str] = {}
    reworked: set[str] = set()

    def spend(action: str, outcome: str) -> None:
        nonlocal step
        step += 1
        events.append({"step": step, "action": action, "outcome": outcome})

    if tracker == "notes.md":
        mentions = parse_memo((workspace / "notes.md").read_text(encoding="utf-8"))
        spend(
            "read notes.md",
            f"{len(mentions)} features mentioned; states are prose; "
            "no verification commands recorded",
        )
        planned = []
        for feature_id, prose in mentions:
            if reads_as_remaining(prose):
                spend(f"interpret '{feature_id}'", f"'{prose}' reads as remaining; planned")
                planned.append(feature_id)
            else:
                spend(f"interpret '{feature_id}'", f"'{prose}' reads as done; skipped")
            believed[feature_id] = "done"
        for feature_id in planned:
            already_passing = truth[feature_id]["built"] and not truth[feature_id]["hidden_defect"]
            spend(
                f"implement {feature_id}",
                "code written; the workspace already had this feature built"
                if truth[feature_id]["built"]
                else "code written",
            )
            truth[feature_id]["built"] = True
            spend(
                f"self-check {feature_id}",
                "looks complete; the memo records no verification command to run",
            )
            spend("update notes.md", f"{feature_id} marked done in prose")
            if already_passing:
                reworked.add(feature_id)
                wasted += 3
        spend("declare done", "the memo shows nothing remaining")
    else:
        entries = json.loads(
            (workspace / "feature_list.json").read_text(encoding="utf-8")
        )["features"]
        spend(
            "read feature_list.json",
            f"{len(entries)} features; every entry carries an explicit status "
            "and a verification command",
        )
        for entry in entries:
            feature_id, status, command = entry["id"], entry["status"], entry["verification"]
            if status == "passing":
                spend(
                    f"{feature_id}: status passing",
                    f"evidence recorded ({command}); skipped without rework",
                )
            else:
                spend(
                    f"implement {feature_id}",
                    "code written" if status == "not-started" else "remaining work written",
                )
                truth[feature_id]["built"] = True
                if truth[feature_id]["hidden_defect"]:
                    spend(f"run {command}", "exit 1: a hidden defect surfaces inside the session")
                    spend(f"fix {feature_id}", "defect repaired")
                    truth[feature_id]["hidden_defect"] = False
                spend(f"run {command}", "exit 0; status passing with evidence recorded")
            believed[feature_id] = "passing"
        spend("declare done", "every feature passing; the claim carries evidence")

    audit = []
    verified_count = 0
    for feature in project["features"]:
        feature_id = feature["id"]
        state = truth[feature_id]
        verified = state["built"] and not state["hidden_defect"]
        if verified:
            verified_count += 1
            note = (
                "verification passes; the session rebuilt a feature that already passed"
                if feature_id in reworked
                else "verification passes"
            )
        elif state["built"]:
            note = "verification fails: the code carries a defect no session run exposed"
        else:
            note = "never attempted: absent from the tracker"
        audit.append(
            {
                "id": feature_id,
                "believed": believed.get(feature_id, "untracked"),
                "verified": verified,
                "note": note,
            }
        )

    honest = verified_count == len(project["features"])
    report = {
        "workspace": workspace.name,
        "tracker": tracker,
        "events": events,
        "steps_spent": step,
        "wasted_steps": wasted,
        "claimed_done": True,
        "features_required": len(project["features"]),
        "features_verified": verified_count,
        "audit": audit,
        "done_claim_honest": honest,
    }
    return report, 0 if honest else 1


def plan(workspace: Path, tracker: str) -> tuple[dict, int]:
    entries_out = []
    next_ids = []
    if tracker == "notes.md":
        for feature_id, prose in parse_memo(
            (workspace / "notes.md").read_text(encoding="utf-8")
        ):
            remaining = reads_as_remaining(prose)
            entries_out.append(
                {
                    "id": feature_id,
                    "state": (
                        "remaining (interpreted from prose)"
                        if remaining
                        else "done (interpreted from prose)"
                    ),
                    "verification": "none recorded",
                    "grounded": False,
                }
            )
            if remaining:
                next_ids.append(feature_id)
    else:
        entries = json.loads(
            (workspace / "feature_list.json").read_text(encoding="utf-8")
        )["features"]
        for entry in entries:
            entries_out.append(
                {
                    "id": entry["id"],
                    "state": entry["status"],
                    "verification": entry["verification"],
                    "grounded": True,
                }
            )
            if entry["status"] != "passing":
                next_ids.append(entry["id"])
    grounded = bool(entries_out) and all(entry["grounded"] for entry in entries_out)
    report = {
        "workspace": workspace.name,
        "tracker": tracker,
        "entries": entries_out,
        "next": next_ids,
        "grounded": grounded,
    }
    return report, 0 if grounded else 1


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in ("replay", "plan"):
        print(
            "usage: main.py replay <workspace-dir> | main.py plan <workspace-dir>",
            file=sys.stderr,
        )
        return 2
    workspace = Path(argv[2])
    if not workspace.is_dir():
        print(f"error: not a directory: {workspace}", file=sys.stderr)
        return 2
    tracker = find_tracker(workspace)
    if tracker is None:
        print(
            f"error: no tracker (feature_list.json or notes.md) in {workspace}",
            file=sys.stderr,
        )
        return 2
    if argv[1] == "replay":
        if not (workspace / "project.json").is_file():
            print(
                f"error: project.json (recorded ground truth) missing in {workspace}",
                file=sys.stderr,
            )
            return 2
        report, code = replay(workspace, tracker)
    else:
        report, code = plan(workspace, tracker)
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
