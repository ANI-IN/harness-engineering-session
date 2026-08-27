"""scope-auditor exercise, Python solution.

Reads a feature list and a session's change log and classifies every
change against the scope surface: in scope only when it targets the
active (in-progress) feature; drift when it targets a queued feature or a
feature the list does not know. The verdict lives in the exit code so a
session-end gate can consume it. SPEC.md pins the rule and the strings.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def audit(feature_list: dict, changes: list[dict]) -> tuple[dict, int]:
    features = feature_list["features"]
    listed = {feature["id"] for feature in features}
    active = [feature["id"] for feature in features if feature["status"] == "in-progress"]
    active_set = set(active)
    results = []
    drift_features: list[str] = []
    for change in changes:
        feature_id = change["feature"]
        if feature_id in active_set:
            in_scope, reason = True, "targets the active feature"
        elif feature_id in listed:
            in_scope, reason = False, f"{feature_id} is in the queue, not active"
        else:
            in_scope, reason = False, f"{feature_id} is not in the feature list"
        if not in_scope and feature_id not in drift_features:
            drift_features.append(feature_id)
        results.append(
            {
                "step": change["step"],
                "file": change["file"],
                "feature": feature_id,
                "in_scope": in_scope,
                "reason": reason,
            }
        )
    drift_count = sum(1 for result in results if not result["in_scope"])
    report = {
        "active": active,
        "changes": results,
        "drift": {"count": drift_count, "features": drift_features},
        "clean": drift_count == 0,
    }
    return report, 0 if drift_count == 0 else 1


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: main.py <feature-list.json> <changes.json>", file=sys.stderr)
        return 2
    try:
        feature_list = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        changes = json.loads(Path(argv[2]).read_text(encoding="utf-8"))["changes"]
    except OSError as error:
        print(f"error: cannot read input: {error}", file=sys.stderr)
        return 2
    report, code = audit(feature_list, changes)
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
