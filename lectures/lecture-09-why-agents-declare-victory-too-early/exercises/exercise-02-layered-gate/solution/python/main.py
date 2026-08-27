"""layered-gate exercise, Python solution.

Runs a workspace's declared checks as a termination gate in three layers,
static, then tests, then system, and stops at the first layer that fails:
every check in a later layer is reported as not-reached, gated by the
failing layer, and never executed. A green system check over a red test
suite is not evidence of anything, and executing it costs the most.
SPEC.md pins the engine, the layer order, the report shape, and the exit
codes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

LAYERS = ["static", "tests", "system"]


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


def run_layers(workspace: Path) -> dict:
    config = json.loads((workspace / "checks.json").read_text(encoding="utf-8"))
    layers = []
    stopped_at = None
    for layer in LAYERS:
        declared = [check for check in config["checks"] if check["layer"] == layer]
        rows = []
        if stopped_at is None:
            for check in declared:
                passed, detail = execute_check(workspace, check)
                status = "pass" if passed else "fail"
                rows.append({"id": check["id"], "status": status, "detail": detail})
            status = "passed" if all(row["status"] == "pass" for row in rows) else "failed"
            if status == "failed":
                stopped_at = layer
        else:
            # Gated: a failing layer below this one means these results
            # would be unearned signal; report why they did not run.
            gated = f"gated by failing layer {stopped_at}"
            rows = [
                {"id": check["id"], "status": "not-reached", "detail": gated}
                for check in declared
            ]
            status = "not-reached"
        layers.append({"layer": layer, "status": status, "checks": rows})
    return {
        "workspace": workspace.name,
        "layers": layers,
        "verdict": {
            "stopped_at": stopped_at,
            "result": "done" if stopped_at is None else "not-done",
        },
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: main.py <workspace-dir>", file=sys.stderr)
        return 2
    workspace = Path(argv[1])
    if not workspace.is_dir() or not (workspace / "checks.json").is_file():
        print(f"error: not a workspace (needs checks.json): {workspace}", file=sys.stderr)
        return 2
    report = run_layers(workspace)
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"]["result"] == "done" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
