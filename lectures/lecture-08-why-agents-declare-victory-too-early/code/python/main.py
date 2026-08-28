"""claim-gate: the scripted session that declares done, and the evidence
gate that re-executes its claim.

`session` is the premature declaration itself: a deterministic scripted
session finishes its implementation steps with a 4-step check budget left,
executes the checks it can afford (cheapest first, in declared order),
predicts a pass for every check it cannot, and declares done. Everything
it ran was green, so the claim is locally honest, and the session exits 0
because nothing inside the loop challenges the claim: the declaration
sticks. `gate` replays that session to obtain the claim, then re-executes
every claimed check against the workspace and reports claim vs check;
any divergence is a premature declaration and exit 1. SPEC.md pins the
check engine, the session policy, and the seeded gaps.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CHECK_BUDGET = 4

IMPLEMENTATION_STEPS = [
    ("implement the export writer", "src/export.txt updated"),
    ("add the export unit test", "tests/unit-export.txt updated"),
    ("wire the config read", "src/export.txt reads export_dir from config/app.conf"),
]


def read_key_from_file(path: Path, key: str) -> str | None:
    for line in path.read_text(encoding="utf-8").split("\n"):
        if line.startswith(f"{key}="):
            return line[len(key) + 1 :].strip()
    return None


def execute_check(workspace: Path, check: dict) -> tuple[bool, str]:
    """The check engine: one executable probe per declared check. The
    deterministic stand-in for running the real command (the seam where a
    shell would sit); details name the exact evidence or the exact gap."""
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
            if read_key_from_file(workspace / side["path"], side["key"]) is None:
                return False, f"{side['path']} has no {side['key']}= line"
        left_value = read_key_from_file(workspace / left["path"], left["key"])
        right_value = read_key_from_file(workspace / right["path"], right["key"])
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


def load_declared_checks(path: Path) -> dict:
    return json.loads((path / "checks.json").read_text(encoding="utf-8"))


def session(workspace: Path) -> dict:
    """The scripted session (SPEC.md, "The session"). It reaches the
    completion decision with CHECK_BUDGET steps left; a check it cannot
    afford is predicted to pass at zero cost, which is the premature
    declaration mechanism under study."""
    config = load_declared_checks(workspace)
    events = []
    step = 0

    def record(action: str, outcome: str) -> None:
        nonlocal step
        step += 1
        events.append({"step": step, "action": action, "outcome": outcome})

    for action, outcome in IMPLEMENTATION_STEPS:
        record(action, outcome)

    remaining = CHECK_BUDGET
    claim_checks = []
    executed = predicted = 0
    all_executed_passed = True
    for check in config["checks"]:
        cost = check["cost"]
        if cost <= remaining:
            remaining -= cost
            passed, detail = execute_check(workspace, check)
            executed += 1
            status = "pass" if passed else "fail"
            all_executed_passed = all_executed_passed and passed
            record(
                f"run check {check['id']} (cost {cost})",
                f"executed: {status} ({detail}); budget left {remaining}",
            )
            claim_checks.append({"id": check["id"], "status": status, "basis": "executed"})
        else:
            predicted += 1
            record(
                f"consider check {check['id']} (cost {cost})",
                f"cost exceeds budget left {remaining}; predicted pass from the code just written",
            )
            claim_checks.append({"id": check["id"], "status": "pass", "basis": "predicted"})

    done = all_executed_passed
    green = sum(1 for check in claim_checks if check["status"] == "pass")
    if done:
        record(
            "declare done",
            f"claim: {green}/{len(claim_checks)} checks green "
            f"({executed} executed, {predicted} predicted)",
        )
    else:
        record("keep working", "an executed check failed; no completion claim")

    return {
        "workspace": workspace.name,
        "task": config["task"],
        "check_budget": CHECK_BUDGET,
        "events": events,
        "claim": {
            "done": done,
            "checks": claim_checks,
            "executed": executed,
            "predicted": predicted,
        },
    }


def gate(workspace: Path) -> dict:
    """The evidence gate: replays the session to obtain the claim, then
    re-executes every claimed check. The report is claim vs check; the
    exit code is the verdict."""
    config = load_declared_checks(workspace)
    claim = session(workspace)["claim"]
    by_id = {check["id"]: check for check in config["checks"]}
    reexecution = []
    divergences = 0
    for claimed in claim["checks"]:
        check = by_id[claimed["id"]]
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
    green = sum(1 for check in claim["checks"] if check["status"] == "pass")
    return {
        "workspace": workspace.name,
        "claim": {
            "done": claim["done"],
            "green": green,
            "executed": claim["executed"],
            "predicted": claim["predicted"],
        },
        "reexecution": reexecution,
        "verdict": {
            "divergences": divergences,
            "result": "earned" if divergences == 0 else "premature",
        },
    }


def resolve_workspace(arg: str) -> Path | None:
    workspace = Path(arg)
    if not workspace.is_dir():
        print(f"error: not a directory: {workspace}", file=sys.stderr)
        return None
    if not (workspace / "checks.json").is_file():
        print(f"error: not a workspace (no checks.json): {workspace}", file=sys.stderr)
        return None
    return workspace


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in ("session", "gate"):
        print(
            "usage: main.py session <workspace-dir> | main.py gate <workspace-dir>",
            file=sys.stderr,
        )
        return 2
    workspace = resolve_workspace(argv[2])
    if workspace is None:
        return 2
    if argv[1] == "session":
        report = session(workspace)
        print(json.dumps(report, indent=2))
        return 0 if report["claim"]["done"] else 1
    report = gate(workspace)
    if not report["claim"]["done"]:
        print(
            "error: the scripted session declares no completion here; nothing to audit",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"]["result"] == "earned" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
