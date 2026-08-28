"""completion-gate exercise, Python starter.

The claim audit, the WIP check, the verdict precedence, and the CLI all
work. The evidence rule does not: the naive draft accepts any recorded
evidence entry as proof, so a typecheck filed as evidence, or a recorded
failing run, backs a `passing` claim. Fix gate() per SPEC.md. Run
../../verify.sh --stack=python until it exits 0.
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
        # Naive draft: an evidence entry was recorded, so the claim is
        # backed, and the detail names the command the feature should
        # have run. Exercise: evidence must name this feature's own
        # verification command AND record a passing run (observed starts
        # with "exit 0"); a different command and a failing run are each
        # an unbacked claim with its own detail (SPEC.md, "The evidence
        # rule").
        if evidence is None:
            ok, detail = False, "no evidence recorded"
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
