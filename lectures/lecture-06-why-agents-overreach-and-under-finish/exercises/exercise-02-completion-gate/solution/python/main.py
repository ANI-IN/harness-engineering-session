"""completion-gate exercise, Python solution.

Audits a feature list's `passing` claims against the evidence rule (the
recorded command is the feature's own verification command and the
recorded run passed), checks the WIP limit, and says through its exit
code whether the next feature may be activated. SPEC.md pins the rules,
the strings, and the verdict precedence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

WIP_LIMIT = 1


def gate(features: list[dict]) -> tuple[dict, int]:
    claims = []
    unbacked: list[str] = []
    for feature in features:
        if feature["status"] != "passing":
            continue
        evidence = feature.get("evidence")
        command = feature["verification"]
        if evidence is None:
            ok, detail = False, "no evidence recorded"
        elif evidence["command"] != command:
            ok, detail = False, (
                f"evidence names a different command ({evidence['command']}, not {command})"
            )
        elif not evidence["observed"].startswith("exit 0"):
            ok, detail = False, f"evidence records a failing run ({evidence['observed']})"
        else:
            ok, detail = True, f"verified: {command} reported exit 0"
        claims.append({"id": feature["id"], "evidence_ok": ok, "detail": detail})
        if not ok:
            unbacked.append(feature["id"])
    in_progress = [feature["id"] for feature in features if feature["status"] == "in-progress"]
    if len(in_progress) > WIP_LIMIT:
        verdict, code = "wip-exceeded", 1
    elif unbacked:
        verdict, code = "unbacked-claims", 1
    else:
        verdict, code = "sound", 0
    report = {
        "claims": claims,
        "may_activate": verdict == "sound" and not in_progress,
        "unbacked": unbacked,
        "verdict": verdict,
        "wip": {"in_progress": in_progress, "limit": WIP_LIMIT},
    }
    return report, code


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: main.py <feature_list.json>", file=sys.stderr)
        return 2
    try:
        data = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    except OSError as error:
        print(f"error: cannot read feature list: {error}", file=sys.stderr)
        return 2
    report, code = gate(data["features"])
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
