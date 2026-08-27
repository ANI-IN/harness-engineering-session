"""claim-audit exercise, Python starter.

The audit runs end to end and its report has the full shape, but one
naive decision remains (see SPEC.md "Starter state"): a check the claim
records as executed, with the evidence text it printed at the time, is
accepted on that record instead of being re-executed. Fix the audit so
every claimed check is re-executed, then run ../../verify.sh
--stack=python until it exits 0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def read_key(path: Path, key: str) -> str | None:
    for line in path.read_text(encoding="utf-8").split("\n"):
        if line.startswith(f"{key}="):
            return line[len(key) + 1 :].strip()
    return None


def execute_check(workspace: Path, check: dict) -> tuple[bool, str]:
    kind = check["kind"]
    if kind == "file-exists":
        path = check["path"]
        if (workspace / path).is_file():
            return True, f"{path} present"
        return False, f"{path} missing"
    if kind == "file-has-line":
        path, prefix = check["path"], check["prefix"]
        file = workspace / path
        if not file.is_file():
            return False, f"{path} missing"
        if any(line.startswith(prefix) for line in file.read_text(encoding="utf-8").split("\n")):
            return True, f"{path} has a line starting with {prefix}"
        return False, f"{path} has no line starting with {prefix}"
    if kind == "file-lacks-marker":
        path, marker = check["path"], check["marker"]
        file = workspace / path
        if not file.is_file():
            return False, f"{path} missing"
        if marker in file.read_text(encoding="utf-8"):
            return False, f"{path} contains {marker}"
        return True, f"{path} carries no {marker} marker"
    if kind == "values-agree":
        left, right = check["left"], check["right"]
        for side in (left, right):
            if not (workspace / side["path"]).is_file():
                return False, f"{side['path']} missing"
            if read_key(workspace / side["path"], side["key"]) is None:
                return False, f"{side['path']} has no {side['key']}= line"
        left_value = read_key(workspace / left["path"], left["key"])
        right_value = read_key(workspace / right["path"], right["key"])
        if left_value == right_value:
            return True, (
                f"{left['path']} {left['key']}={left_value} matches "
                f"{right['path']} {right['key']}={right_value}"
            )
        return False, (
            f"{left['path']} {left['key']}={left_value} but "
            f"{right['path']} {right['key']}={right_value}"
        )
    raise ValueError(f"unknown check kind: {kind}")


def audit(workspace: Path, claim: dict) -> dict:
    config = json.loads((workspace / "checks.json").read_text(encoding="utf-8"))
    by_id = {check["id"]: check for check in config["checks"]}
    reexecution = []
    divergences = 0
    for claimed in claim["checks"]:
        check = by_id[claimed["id"]]
        if claimed["basis"] == "executed":
            # Naive draft: the session already ran this check and recorded
            # its output, so re-running it would only repeat work. Exercise:
            # the record describes the past; re-execute regardless of basis.
            actual, detail = claimed["status"], claimed["evidence"]
        else:
            passed, detail = execute_check(workspace, check)
            actual = "pass" if passed else "fail"
        diverged = actual != claimed["status"]
        divergences += 1 if diverged else 0
        reexecution.append(
            {
                "id": claimed["id"],
                "layer": check["layer"],
                "claimed": claimed["status"],
                "basis": claimed["basis"],
                "actual": actual,
                "detail": detail,
                "verdict": "diverged" if diverged else "confirmed",
            }
        )
    checks = claim["checks"]
    return {
        "workspace": workspace.name,
        "claim": {
            "done": claim["done"],
            "green": sum(1 for check in checks if check["status"] == "pass"),
            "executed": sum(1 for check in checks if check["basis"] == "executed"),
            "predicted": sum(1 for check in checks if check["basis"] == "predicted"),
        },
        "reexecution": reexecution,
        "verdict": {
            "divergences": divergences,
            "result": "earned" if divergences == 0 else "premature",
        },
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: main.py <workspace-dir> <claim-file>", file=sys.stderr)
        return 2
    workspace, claim_path = Path(argv[1]), Path(argv[2])
    if not workspace.is_dir() or not (workspace / "checks.json").is_file():
        print(f"error: not a workspace (needs checks.json): {workspace}", file=sys.stderr)
        return 2
    if not claim_path.is_file():
        print(f"error: no such claim file: {claim_path}", file=sys.stderr)
        return 2
    claim = json.loads(claim_path.read_text(encoding="utf-8"))
    if not claim.get("done"):
        print("error: the claim declares no completion; nothing to audit", file=sys.stderr)
        return 2
    report = audit(workspace, claim)
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"]["result"] == "earned" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
