"""session-ending: two sessions in sequence over one workspace, where the
only thing that varies is how the first session ended.

`resume` runs the first session (the same work steps under both exit
disciplines), applies the chosen ending (`--exit=dirty` walks away,
`--exit=clean` runs the exit protocol), then runs the second session
against whatever it was left. The second session's protocol is identical
in both runs, so every difference in its behaviour is caused by the ending
it inherited: from the clean workspace it picks up the open feature and
finishes it, from the dirty one it redoes finished work and turns a check
that was green red. The exit code is the second session's outcome.

`first` stops after the first session and grades its ending against five
mechanically checkable items of the clean state checklist. That count is
supporting evidence for the behavioural runs, never the demonstration.

The workspace is read from disk once and edited in memory, so the
committed fixture never changes and every run is idempotent. SPEC.md pins
the check engine, both session scripts, the exit protocol, and the
checklist items.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BUILD_DATE = "2026-08-27"

# The implementation edit each feature needs: the file that carries the
# feature's behaviour, the header written when that file does not exist
# yet, and the declaration line the work adds.
IMPLEMENTATION = {
    "csv-export": ("src/export.txt", "module=export", "writer=csv"),
    "pdf-export": ("src/pdf.txt", "module=pdf", "writer=pdf"),
}

PROGRESS_PLACEHOLDER = "No feature has been verified in this workspace yet."
SESSION_HEADING = "## Session 001"

SESSION_ENTRY = """## Session 002 (2026-08-27)

- Goal: finish csv-export, then open pdf-export.
- Done: csv-export, verified by check unit-csv.
- Not done: pdf-export; the draft module was rolled back, so the workspace
  holds no half applied change.
- Next: pdf-export.

"""

HANDOFF = """# Session handoff

## Verified now

- `check unit-csv`: exit 0, src/export.txt declares writer once
- `check wiring-csv`: exit 0, config/app.conf sets export_dir

## Changed this session

- `src/export.txt`: the csv writer is implemented.
- `config/app.conf`: export_dir set to out/reports.
- `feature_list.json`: csv-export set to passing with evidence.

## Broken or unverified

Nothing. The pdf draft was rolled back, so pdf-export is not-started
rather than half applied.

## Next best step

- pdf-export: add a `writer=pdf` line to `src/pdf.txt`, then run
  `check unit-pdf`.

## Commands

- Verify everything: `check unit-csv && check wiring-csv && check unit-pdf`
"""


# --------------------------------------------------------------------------
# The workspace: a path-to-text map loaded once and edited in memory.
# --------------------------------------------------------------------------


def load_workspace(root: Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return files


def lines_of(files: dict[str, str], path: str) -> list[str]:
    return files[path].split("\n")


def feature_list(files: dict[str, str]) -> dict:
    return json.loads(files["feature_list.json"])


def store_feature_list(files: dict[str, str], data: dict) -> None:
    files["feature_list.json"] = json.dumps(data, indent=2) + "\n"


def set_status(files: dict[str, str], feature_id: str, status: str, evidence=None) -> None:
    data = feature_list(files)
    for feature in data["features"]:
        if feature["id"] == feature_id:
            feature["status"] = status
            if evidence is not None:
                feature["evidence"] = evidence
    store_feature_list(files, data)


def section_ids(files: dict[str, str], path: str, heading: str) -> list[str]:
    """The ids named by `- <id>: <text>` bullets under one markdown heading.

    One parser serves all three artifact sections this unit reads: the
    progress log's verified features, and the handoff's broken checks and
    its next best step."""
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


# --------------------------------------------------------------------------
# The check engine: the deterministic stand-in for running the real command.
# --------------------------------------------------------------------------


def run_check(files: dict[str, str], check: dict) -> tuple[bool, str]:
    path = check["path"]
    if path not in files:
        return False, f"{path} missing"
    lines = files[path].split("\n")
    if check["kind"] == "key-declared-once":
        key = check["key"]
        count = sum(1 for line in lines if line.startswith(f"{key}="))
        if count == 1:
            return True, f"{path} declares {key} once"
        if count == 0:
            return False, f"{path} has no {key}= line"
        return False, f"{path} declares {key} {count} times"
    if check["kind"] == "file-has-line":
        prefix = check["prefix"]
        if any(line.startswith(prefix) for line in lines):
            return True, f"{path} has a line starting with {prefix}"
        return False, f"{path} has no line starting with {prefix}"
    raise ValueError(f"unknown check kind: {check['kind']}")


def run_checks(files: dict[str, str], config: dict) -> list[dict]:
    results = []
    for check in config["checks"]:
        passed, detail = run_check(files, check)
        results.append(
            {
                "id": check["id"],
                "feature": check["feature"],
                "status": "pass" if passed else "fail",
                "detail": detail,
            }
        )
    return results


def summarize(results: list[dict]) -> str:
    return ", ".join(f"{result['id']} {result['status']}" for result in results)


def green_features(results: list[dict]) -> list[str]:
    """Feature ids whose every declared check passes right now."""
    by_feature: dict[str, list[str]] = {}
    for result in results:
        by_feature.setdefault(result["feature"], []).append(result["status"])
    return sorted(fid for fid, seen in by_feature.items() if all(s == "pass" for s in seen))


def implement(files: dict[str, str], feature_id: str) -> str:
    """Apply a feature's implementation edit and report what the file now
    declares. A session that believes a feature is unstarted writes the
    declaration; whether one is already there is not something the edit
    consults."""
    path, header, line = IMPLEMENTATION[feature_id]
    created = path not in files
    if created:
        files[path] = header + "\n"
    files[path] = files[path] + line + "\n"
    key = line.split("=")[0]
    count = sum(1 for text in lines_of(files, path) if text.startswith(f"{key}="))
    times = "once" if count == 1 else f"{count} times"
    verb = f"created {path} with {line}" if created else f"appended {line} to {path}"
    return f"{verb}; the file now declares {key} {times}"


class Transcript:
    """Numbered actions with their observed outcomes: one session's log."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def record(self, action: str, outcome: str) -> None:
        self.events.append({"step": len(self.events) + 1, "action": action, "outcome": outcome})


# --------------------------------------------------------------------------
# The first session: the same work, then one of two endings.
# --------------------------------------------------------------------------


def first_session(files: dict[str, str], config: dict, discipline: str) -> list[dict]:
    log = Transcript()

    log.record("implement the csv writer", implement(files, "csv-export"))

    files["config/app.conf"] = files["config/app.conf"] + "export_dir=out/reports\n"
    log.record("wire the export directory", "config/app.conf now sets export_dir=out/reports")

    by_id = {check["id"]: check for check in config["checks"]}
    _, detail = run_check(files, by_id["unit-csv"])
    log.record("run check unit-csv", f"executed: pass ({detail})")

    set_status(files, "pdf-export", "in-progress")
    files["src/pdf.txt"] = "module=pdf\nstage=draft\n"
    log.record(
        "open pdf-export and draft its module",
        "feature_list.json sets pdf-export to in-progress; src/pdf.txt drafted "
        "with no writer= line yet",
    )

    files["scratch/probe-pdf.txt"] = "page_size=a4\nprobe=manual\n"
    log.record("probe the pdf page size by hand", "scratch/probe-pdf.txt written")

    if discipline == "dirty":
        log.record(
            "end the session",
            "no exit protocol ran: feature_list.json still calls csv-export "
            "in-progress, claude-progress.md has no entry for this session, "
            "src/pdf.txt is left half applied, scratch/probe-pdf.txt is left in "
            "the tree, and no session-handoff.md was written",
        )
    else:
        clean_exit(files, config, log)
    return log.events


def clean_exit(files: dict[str, str], config: dict, log: Transcript) -> None:
    """The exit protocol: verify, roll back what is half applied, write the
    verified state into the machine-readable artifacts, clear the debris,
    and name the next best step."""
    results = run_checks(files, config)
    log.record(
        "run the declared checks and record what they observed",
        f"{summarize(results)} ({results[2]['detail']})",
    )

    del files["src/pdf.txt"]
    set_status(files, "pdf-export", "not-started")
    log.record(
        "roll back the half applied pdf draft",
        "src/pdf.txt removed; feature_list.json returns pdf-export to "
        "not-started, so no check is left failing on a feature in flight",
    )

    set_status(
        files,
        "csv-export",
        "passing",
        {
            "command": "check unit-csv",
            "observed": "exit 0, src/export.txt declares writer once",
            "date": BUILD_DATE,
        },
    )
    data = feature_list(files)
    data["updated"] = BUILD_DATE
    store_feature_list(files, data)
    log.record(
        "write the verified status into feature_list.json",
        f"csv-export set to passing with evidence: check unit-csv, exit 0, {BUILD_DATE}",
    )

    verified = green_features(run_checks(files, config))
    by_feature = {feature["id"]: feature for feature in feature_list(files)["features"]}
    bullets = "\n".join(
        f"- {fid}: verified by {by_feature[fid]['verification']}" for fid in verified
    )
    progress = files["claude-progress.md"].replace(PROGRESS_PLACEHOLDER, bullets)
    files["claude-progress.md"] = progress.replace(
        SESSION_HEADING, SESSION_ENTRY + SESSION_HEADING
    )
    log.record(
        "record the session in claude-progress.md",
        f"verified now lists {', '.join(verified)}; a session 002 entry names "
        "what was done, what was not, and what is next",
    )

    del files["scratch/probe-pdf.txt"]
    files["session-handoff.md"] = HANDOFF
    log.record(
        "clear the scratch artifacts and write session-handoff.md",
        "scratch/probe-pdf.txt removed; session-handoff.md names pdf-export as "
        "the next best step",
    )


# --------------------------------------------------------------------------
# The second session: one protocol, run against whichever ending it got.
# --------------------------------------------------------------------------


def second_session(files: dict[str, str], config: dict) -> tuple[Transcript, str, list[dict]]:
    log = Transcript()

    next_steps = section_ids(files, "session-handoff.md", "## Next best step")
    handoff_step = next_steps[0] if next_steps else None
    log.record(
        "read session-handoff.md",
        f"found; the next best step names {handoff_step}"
        if handoff_step
        else "absent; the previous session wrote down no next best step",
    )

    verified = section_ids(files, "claude-progress.md", "## Verified now")
    log.record(
        "read the verified state in claude-progress.md",
        f"verified now lists {', '.join(verified)}"
        if verified
        else "verified now lists nothing; the log carries no entry for the "
        "previous session, so its work is invisible from here",
    )

    features = feature_list(files)["features"]
    in_progress = [feature["id"] for feature in features if feature["status"] == "in-progress"]
    statuses = ", ".join(f"{feature['id']} {feature['status']}" for feature in features)
    log.record(
        "read feature_list.json",
        statuses + (
            f"; {len(in_progress)} features in flight at once, which breaks WIP=1"
            if len(in_progress) > 1
            else ""
        ),
    )

    # Choose the feature. The handoff wins when it names one; otherwise WIP=1
    # points at the single in-progress feature, and a feature the progress log
    # records as verified is skipped.
    candidates = [fid for fid in in_progress if fid not in verified]
    if handoff_step is not None:
        chosen, why = handoff_step, "named by session-handoff.md"
    elif candidates:
        chosen = candidates[0]
        why = (
            "no handoff, and no progress entry that would let it be skipped; "
            f"feature_list.json leaves {len(in_progress)} features in progress, "
            "so take the first"
            if len(in_progress) > 1
            else "the single in-progress feature, per WIP=1"
        )
    else:
        chosen = features[0]["id"]
        why = "nothing in progress and nothing handed over; take the first feature declared"
    log.record("choose the feature to work on", f"{chosen}: {why}")

    log.record(f"implement {chosen}", implement(files, chosen))

    results = run_checks(files, config)
    log.record("run the declared checks", summarize(results))
    return log, chosen, results


# --------------------------------------------------------------------------
# The clean state checklist: supporting evidence, five mechanical items.
# --------------------------------------------------------------------------


def clean_state(files: dict[str, str], config: dict) -> list[dict]:
    features = {feature["id"]: feature for feature in feature_list(files)["features"]}
    results = run_checks(files, config)
    green = green_features(results)
    named_broken = section_ids(files, "session-handoff.md", "## Broken or unverified")
    logged = section_ids(files, "claude-progress.md", "## Verified now")
    items: list[dict] = []

    def item(name: str, ok: bool, detail: str) -> None:
        items.append({"item": name, "status": "pass" if ok else "fail", "detail": detail})

    unrecorded = [
        result["id"]
        for result in results
        if result["status"] == "fail"
        and features[result["feature"]]["status"] != "not-started"
        and result["id"] not in named_broken
    ]
    item(
        "verification-recorded",
        not unrecorded,
        f"{', '.join(unrecorded)} fails on a feature in flight and no "
        "session-handoff.md records the failure"
        if unrecorded
        else "every check on a feature in flight passes, and no failure is left unrecorded",
    )

    wrong = []
    for fid, feature in features.items():
        if feature["status"] == "passing" and fid not in green:
            wrong.append(f"{fid} is passing but a check on it fails")
        if feature["status"] == "passing" and "evidence" not in feature:
            wrong.append(f"{fid} is passing with no evidence recorded")
        if fid in green and feature["status"] != "passing":
            wrong.append(f"{fid} is {feature['status']} but every check on it passes")
    item(
        "statuses-true",
        not wrong,
        "; ".join(wrong)
        if wrong
        else "every feature status agrees with its checks, and every passing "
        "status carries evidence",
    )

    unlogged = [fid for fid in green if fid not in logged]
    item(
        "progress-recorded",
        not unlogged,
        f"claude-progress.md does not record {', '.join(unlogged)}, whose checks all pass"
        if unlogged
        else "claude-progress.md records every feature whose checks all pass",
    )

    stray = sorted(path for path in files if path.startswith("scratch/"))
    item(
        "no-stray-artifacts",
        not stray,
        f"{', '.join(stray)} left in the workspace" if stray else "no files under scratch/",
    )

    next_steps = section_ids(files, "session-handoff.md", "## Next best step")
    if not next_steps:
        item("next-step-written", False, "no session-handoff.md names a next best step")
    elif next_steps[0] not in features:
        item(
            "next-step-written",
            False,
            f"session-handoff.md names {next_steps[0]}, which is not a feature "
            "in feature_list.json",
        )
    elif features[next_steps[0]]["status"] == "passing":
        item(
            "next-step-written",
            False,
            f"session-handoff.md names {next_steps[0]}, which is already passing",
        )
    else:
        item(
            "next-step-written",
            True,
            f"session-handoff.md names {next_steps[0]}, which is "
            f"{features[next_steps[0]]['status']}",
        )
    return items


# --------------------------------------------------------------------------
# Surfaces.
# --------------------------------------------------------------------------


def first(root: Path, discipline: str) -> dict:
    files = load_workspace(root)
    config = json.loads(files["checks.json"])
    events = first_session(files, config, discipline)
    items = clean_state(files, config)
    return {
        "workspace": root.name,
        "exit_discipline": discipline,
        "task": config["task"],
        "events": events,
        "clean_state": items,
        "failed": sum(1 for entry in items if entry["status"] == "fail"),
    }


def resume(root: Path, discipline: str) -> dict:
    files = load_workspace(root)
    config = json.loads(files["checks.json"])
    events = first_session(files, config, discipline)

    handed_over = run_checks(files, config)
    was_pass = {result["id"]: result["status"] == "pass" for result in handed_over}
    was_green = set(green_features(handed_over))

    log, chosen, results = second_session(files, config)
    regressed = [
        result["id"] for result in results if was_pass[result["id"]] and result["status"] == "fail"
    ]
    completed = [fid for fid in green_features(results) if fid not in was_green]
    verdict = "resumed" if not regressed and completed else "derailed"
    log.record(
        "close the session",
        f"{', '.join(completed)} is finished and verified; nothing the previous "
        "session left green went red"
        if verdict == "resumed"
        else f"{', '.join(regressed)} went from pass to fail; the work went into a "
        "feature that was already finished, and redoing it broke the check",
    )
    return {
        "workspace": root.name,
        "exit_discipline": discipline,
        "first_session": {"task": config["task"], "events": events},
        "second_session": {"chose": chosen, "events": log.events, "checks": results},
        "outcome": {"completed": completed, "regressed": regressed, "result": verdict},
    }


USAGE = "usage: main.py first|resume <workspace-dir> --exit=clean|dirty"


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[1] not in ("first", "resume"):
        print(USAGE, file=sys.stderr)
        return 2
    if argv[3] not in ("--exit=clean", "--exit=dirty"):
        print(USAGE, file=sys.stderr)
        return 2
    discipline = argv[3].removeprefix("--exit=")
    root = Path(argv[2])
    if not root.is_dir() or not (root / "checks.json").is_file():
        print(f"error: not a workspace (needs checks.json): {root}", file=sys.stderr)
        return 2
    if argv[1] == "first":
        report = first(root, discipline)
        print(json.dumps(report, indent=2))
        return 0 if report["failed"] == 0 else 1
    report = resume(root, discipline)
    print(json.dumps(report, indent=2))
    return 0 if report["outcome"]["result"] == "resumed" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
