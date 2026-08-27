"""verification-gap exercise, Python solution.

Classifies every run by whether its first claim was backed by an earlier
passing verification, then computes the verification gap (unverified claims
over all claims). Contract: ../../SPEC.md.
"""

from __future__ import annotations

import json
import sys


def classify(events: list[dict]) -> dict:
    """Classify one run's events (in execution order)."""
    first_claim_index = next(
        (i for i, e in enumerate(events) if e["type"] == "claim"), None
    )
    if first_claim_index is None:
        return {"claimed": False, "verified_before_claim": False, "classification": "no-claim"}
    verified = any(
        e["type"] == "verification" and e.get("result") == "pass"
        for e in events[:first_claim_index]
    )
    return {
        "claimed": True,
        "verified_before_claim": verified,
        "classification": "verified-done" if verified else "unverified-done",
    }


def gap_report(events: list[dict]) -> dict:
    order: list[str] = []
    runs: dict[str, list[dict]] = {}
    for event in events:
        run_id = event["run"]
        if run_id not in runs:
            order.append(run_id)
            runs[run_id] = []
        runs[run_id].append(event)

    report_runs = []
    claims = verified_claims = 0
    for run_id in order:
        entry = {"id": run_id, **classify(runs[run_id])}
        report_runs.append(entry)
        if entry["claimed"]:
            claims += 1
            if entry["verified_before_claim"]:
                verified_claims += 1

    unverified = claims - verified_claims
    return {
        "runs": report_runs,
        "claims": claims,
        "verified_claims": verified_claims,
        "unverified_claims": unverified,
        "verification_gap": unverified / claims if claims else 0.0,
    }


def parse_transcript(text: str) -> list[dict]:
    events = []
    for number, line in enumerate(text.split("\n"), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"malformed transcript at line {number}: {error}") from error
        for field in ("run", "type", "detail"):
            if field not in event:
                raise ValueError(f"malformed transcript at line {number}: missing {field!r}")
        events.append(event)
    return events


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: main.py <transcript.jsonl>", file=sys.stderr)
        return 2
    try:
        with open(argv[1], encoding="utf-8") as handle:
            text = handle.read()
    except OSError as error:
        print(f"error: cannot read transcript: {error}", file=sys.stderr)
        return 2
    try:
        events = parse_transcript(text)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(gap_report(events), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
