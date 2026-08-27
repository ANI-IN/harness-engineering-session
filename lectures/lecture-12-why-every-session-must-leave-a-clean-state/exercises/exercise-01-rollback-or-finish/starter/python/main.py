"""rollback-or-finish: what the exit protocol owes each in-flight edit.

A session reaches its end with a list of edits it made. For each one the
exit protocol decides what to do before the session may end.

This draft has two moves: an edit whose check passes is finished, and an
edit whose check fails is written into the handoff's broken-or-unverified
section so the next session knows about it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load_workspace(root: Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return files


def run_check(files: dict[str, str], check: dict) -> tuple[bool, str]:
    """The check engine, unchanged from the lecture demo's contract."""
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


def decide(actual: str) -> str:
    """What the exit protocol owes one edit.

    A verified edit is finished. An unverified one is not lost: name it in
    the handoff and the next session can pick it up from there.
    """
    if actual == "pass":
        return "finish"
    return "declare"


def review(root: Path, ending: dict) -> dict:
    files = load_workspace(root)
    config = json.loads(files["checks.json"])
    by_id = {check["id"]: check for check in config["checks"]}

    edits = []
    summary = {"declare": 0, "finish": 0, "roll_back": 0}
    for edit in ending["edits"]:
        passed, detail = run_check(files, by_id[edit["check"]])
        actual = "pass" if passed else "fail"
        decision = decide(actual)
        summary[decision.replace("-", "_")] += 1
        edits.append(
            {
                "path": edit["path"],
                "check": edit["check"],
                "created": edit["created"],
                "actual": actual,
                "detail": detail,
                "decision": decision,
            }
        )
    owed = summary["declare"] + summary["roll_back"]
    return {
        "workspace": root.name,
        "session": ending["session"],
        "edits": edits,
        "summary": summary,
        "verdict": "may-end" if owed == 0 else "exit-protocol-owed",
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: main.py <workspace-dir> <ending-file>", file=sys.stderr)
        return 2
    root, ending_path = Path(argv[1]), Path(argv[2])
    if not root.is_dir() or not (root / "checks.json").is_file():
        print(f"error: not a workspace (needs checks.json): {root}", file=sys.stderr)
        return 2
    if not ending_path.is_file():
        print(f"error: no such ending file: {ending_path}", file=sys.stderr)
        return 2
    report = review(root, json.loads(ending_path.read_text(encoding="utf-8")))
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "may-end" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
