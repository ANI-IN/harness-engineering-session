"""pass-gate exercise, Python starter.

The state machine works: legal edges, WIP=1 on entry to in-progress,
passing is final. The road into passing does not: the naive draft lets any
recorded evidence through, without asking what was run or what it showed,
so an agent that ran `echo done` gets the same verdict as one that ran the
feature's verification command. Fix the passing branch of decide() per
SPEC.md. Run ../../verify.sh --stack=python until it exits 0.
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
        # Naive draft: evidence is present, so the claim goes through. The
        # gate never asks whether the evidence's command is this feature's
        # verification command, or whether the observed result was a pass.
        return verdict("allowed", "evidence recorded")
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
