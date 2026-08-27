"""idempotent-cleanup: the exit protocol, safe to run again.

A session's exit protocol gets interrupted: the machine dies, the run is
cancelled, a retry re-enters it. Whatever ran already must not run twice,
so every step reconciles the artifact towards the state it wants instead
of performing an action. Each step reports whether it changed anything,
and a pass in which nothing changed is `already-clean`.

The workspace is read from disk once and edited in memory, so the
committed fixture never changes and repeated runs are reproducible.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SESSION_HEADING_PREFIX = "## Session "


def load_workspace(root: Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return files


def section_ids(files: dict[str, str], path: str, heading: str) -> list[str]:
    """The ids named by `- <id>: <text>` bullets under one markdown heading."""
    text = files.get(path)
    if text is None:
        return []
    found, inside = [], False
    for line in text.split("\n"):
        if line.startswith("## "):
            inside = line.strip() == heading
            continue
        if inside and line.startswith("- ") and ":" in line:
            found.append(line[2:].split(":")[0].strip())
    return found


def progress_entry(session: dict) -> str:
    return (
        f"## Session {session['session']} ({session['date']})\n\n"
        f"- Verified: {', '.join(session['verified'])}.\n"
        f"- Next: {session['next_step']}\n\n"
    )


def handoff_text(session: dict, features: dict[str, dict]) -> str:
    verified = "\n".join(
        f"- {fid}: verified by {features[fid]['verification']}" for fid in session["verified"]
    )
    return (
        "# Session handoff\n\n"
        f"## Verified now\n\n{verified}\n\n"
        f"## Next best step\n\n- {session['next_step']}\n"
    )


def features_by_id(files: dict[str, str]) -> dict[str, dict]:
    data = json.loads(files["feature_list.json"])
    return {feature["id"]: feature for feature in data["features"]}


def record_progress(files: dict[str, str], session: dict) -> tuple[bool, str]:
    """Ensure claude-progress.md carries this session's entry, exactly once.

    The log is append-only by nature, which is what makes this the step that
    has to reconcile rather than append: the entry for a session that is
    already recorded is already there."""
    marker = f"## Session {session['session']}"
    text = files["claude-progress.md"]
    if any(line.startswith(marker) for line in text.split("\n")):
        return False, f"claude-progress.md already records session {session['session']}"
    entry = progress_entry(session)
    index = text.index(SESSION_HEADING_PREFIX)
    files["claude-progress.md"] = text[:index] + entry + text[index:]
    return True, f"added a session {session['session']} entry to claude-progress.md"


def set_statuses(files: dict[str, str], session: dict) -> tuple[bool, str]:
    data = json.loads(files["feature_list.json"])
    changed = []
    for feature in data["features"]:
        if feature["id"] not in session["verified"]:
            continue
        if feature["status"] == "passing" and "evidence" in feature:
            continue
        feature["status"] = "passing"
        feature["evidence"] = {
            "command": feature["verification"],
            "observed": "exit 0",
            "date": session["date"],
        }
        changed.append(feature["id"])
    if not changed:
        return False, f"{', '.join(session['verified'])} already passing with evidence"
    files["feature_list.json"] = json.dumps(data, indent=2) + "\n"
    return True, f"set {', '.join(changed)} to passing with evidence"


def clear_scratch(files: dict[str, str], _session: dict) -> tuple[bool, str]:
    stray = sorted(path for path in files if path.startswith("scratch/"))
    if not stray:
        return False, "no files under scratch/"
    for path in stray:
        del files[path]
    return True, f"removed {', '.join(stray)}"


def write_handoff(files: dict[str, str], session: dict) -> tuple[bool, str]:
    wanted = session["next_step"].split(":")[0].strip()
    named = section_ids(files, "session-handoff.md", "## Next best step")
    if named and named[0] == wanted:
        return False, f"session-handoff.md already names {wanted}"
    files["session-handoff.md"] = handoff_text(session, features_by_id(files))
    return True, f"wrote session-handoff.md naming {wanted}"


STEPS = [
    ("record-progress", record_progress),
    ("set-statuses", set_statuses),
    ("clear-scratch", clear_scratch),
    ("write-handoff", write_handoff),
]


def cleanup(root: Path, passes: int) -> dict:
    files = load_workspace(root)
    session = json.loads(files["session.json"])
    reports = []
    for number in range(1, passes + 1):
        steps, changed_any = [], False
        for step_id, step in STEPS:
            changed, outcome = step(files, session)
            changed_any = changed_any or changed
            steps.append({"id": step_id, "outcome": outcome})
        reports.append(
            {
                "pass": number,
                "steps": steps,
                "verdict": "changed" if changed_any else "already-clean",
            }
        )

    marker = f"## Session {session['session']}"
    entries = sum(
        1 for line in files["claude-progress.md"].split("\n") if line.startswith(marker)
    )
    named = section_ids(files, "session-handoff.md", "## Next best step")
    return {
        "workspace": root.name,
        "session": session["session"],
        "passes": reports,
        "summary": {
            "handoff_next_step": named[0] if named else None,
            "passing": sorted(
                fid
                for fid, feature in features_by_id(files).items()
                if feature["status"] == "passing"
            ),
            "progress_entries": entries,
            "scratch_files": sum(1 for path in files if path.startswith("scratch/")),
        },
    }


USAGE = "usage: main.py <workspace-dir> --passes=<1-5>"


def main(argv: list[str]) -> int:
    if len(argv) != 3 or not argv[2].startswith("--passes="):
        print(USAGE, file=sys.stderr)
        return 2
    value = argv[2].removeprefix("--passes=")
    if not value.isdigit() or not 1 <= int(value) <= 5:
        print(USAGE, file=sys.stderr)
        return 2
    root = Path(argv[1])
    if not root.is_dir() or not (root / "session.json").is_file():
        print(f"error: not a workspace (needs session.json): {root}", file=sys.stderr)
        return 2
    print(json.dumps(cleanup(root, int(value)), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
