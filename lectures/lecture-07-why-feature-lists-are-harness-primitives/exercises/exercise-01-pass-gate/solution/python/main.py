"""pass-gate exercise, Python solution.

The harness side of a feature list: an agent may only request a status
transition, and this gate decides. Legal edges follow the canonical state
machine, WIP=1 holds on entry to in-progress, passing is final, and the
only road into passing is evidence whose command is the feature's own
verification command and whose observed result records a passing run.
Contract: ../../SPEC.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

EXIT_ALLOWED = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2


def decide(features: list[dict], request: dict) -> tuple[dict, int]:
    by_id = {feature["id"]: feature for feature in features}
    feature = by_id[request["feature"]]
    feature_id, current, target = feature["id"], feature["status"], request["to"]

    def verdict(decision: str, reason: str) -> tuple[dict, int]:
        report = {
            "feature": feature_id,
            "from": current,
            "to": target,
            "decision": decision,
            "reason": reason,
        }
        return report, EXIT_ALLOWED if decision == "allowed" else EXIT_REFUSED

    if current == "passing":
        return verdict("refused", f"passing is final: {feature_id} cannot leave passing")
    if target == "in-progress" and current in ("not-started", "blocked"):
        active = [
            f["id"] for f in features if f["status"] == "in-progress" and f["id"] != feature_id
        ]
        if active:
            return verdict("refused", f"WIP limit: {active[0]} is already in-progress")
        return verdict("allowed", "WIP=1 holds: no other feature in-progress")
    if target == "blocked" and current == "in-progress":
        return verdict("allowed", "blocked is reachable from in-progress")
    if target == "passing" and current == "in-progress":
        evidence = request.get("evidence")
        if not evidence:
            return verdict("refused", "no evidence recorded; passing requires evidence")
        if evidence["command"] != feature["verification"]:
            return verdict(
                "refused",
                f"evidence command '{evidence['command']}' does not match "
                f"verification '{feature['verification']}'",
            )
        if not evidence["observed"].startswith("exit 0"):
            return verdict(
                "refused",
                f"evidence records a failing run ('{evidence['observed']}'), not a pass",
            )
        return verdict(
            "allowed", f"evidence matches the verification command ({feature['verification']})"
        )
    return verdict("refused", f"illegal transition: {current} -> {target}")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: main.py <feature_list.json> <request.json>", file=sys.stderr)
        return EXIT_USAGE
    try:
        feature_list = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        request = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"error: cannot read input: {error}", file=sys.stderr)
        return EXIT_USAGE
    features = feature_list["features"]
    if request["feature"] not in {feature["id"] for feature in features}:
        print(f"error: unknown feature '{request['feature']}'", file=sys.stderr)
        return EXIT_USAGE
    report, code = decide(features, request)
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
