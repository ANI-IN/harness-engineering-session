"""Part B (reference solution): the evidence-gated status update.

Order of the checks (README "Detailed requirements, Part B"):
1. already set, or not the build phase, or no done claim for this phase -> "none", nothing run
2. unknown feature id -> "note"
3. verify layer on: the gate result is the evidence; it must be passed, consistent, and show
   every visible test passing. Nothing is run.
4. verify layer off: run the visible tests once; exit 0, a pytest summary, no failures or
   errors, and at least one test passed.
Any doubt -> "note" and passes stays false. On success a new document is returned.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from shipharness.sandbox import Sandbox

VISIBLE_TESTS_COMMAND = "python -m pytest tests/visible -q -rfE --no-header -p no:cacheprovider"
_RATIO = re.compile(r"(\d+)\s*/\s*(\d+)")
_SUMMARY = re.compile(r"(?:(?:\d+ [a-z]+|no tests ran)(?:, )?)+ in \d+(?:\.\d+)?s(?: \([^)]*\))?")
_COUNT = re.compile(r"(\d+) ([a-z]+)")


@dataclass(frozen=True)
class SessionEnd:
    phase: str
    last_claim: dict[str, Any] | None
    verify_layer: bool
    gate: dict[str, Any] | None
    head_commit: str
    passes_already_set: bool = False


@dataclass(frozen=True)
class StatusDecision:
    kind: Literal["status_set", "note", "none"]
    message: str
    document: dict[str, Any]
    evidence: dict[str, Any] | None = None


def pytest_counts(output: str) -> dict[str, int] | None:
    """Counts from the last pytest summary line ("3 passed, 1 skipped in 0.31s"), or None."""
    found: dict[str, int] | None = None
    for raw in output.splitlines():
        line = raw.strip().strip("=").strip()
        if _SUMMARY.fullmatch(line):
            counts = {"passed": 0, "failed": 0, "errors": 0}
            for number, word in _COUNT.findall(line):
                key = "errors" if word.startswith("error") else word
                counts[key] = counts.get(key, 0) + int(number)
            found = counts
    return found


def _ratio(item: dict[str, Any] | None) -> tuple[int, int] | None:
    if item is None:
        return None
    match = _RATIO.search(str(item.get("detail", "")))
    return (int(match.group(1)), int(match.group(2))) if match else None


def _gate_evidence(gate: Any, head: str) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(gate, dict):
        return None, "no verify gate result"
    gate_id = str(gate.get("gate_id", ""))
    if gate.get("passed") is not True:
        return None, f"the verify gate {gate_id} did not pass"
    items = [i for i in gate.get("items", []) if isinstance(i, dict)]
    open_items = [str(i.get("name")) for i in items if i.get("status") in ("fail", "pending")]
    if open_items:
        return None, f"the gate {gate_id} says passed but lists {', '.join(open_items)} as open"
    by_name = {str(i.get("name")): i for i in items}
    visible = by_name.get("visible tests")
    ratio = _ratio(visible)
    if visible is None or visible.get("status") != "pass" or ratio is None:
        return None, f"the gate {gate_id} has no passing visible-tests result"
    if ratio[0] != ratio[1] or ratio[1] == 0:
        return None, f"the gate {gate_id} shows visible tests {ratio[0]}/{ratio[1]}"
    existing = _ratio(by_name.get("existing tests"))
    checks = [
        str(i["name"])
        for i in items
        if re.fullmatch(r"R\d+", str(i.get("name", ""))) and i.get("status") == "pass"
    ]
    return {
        "gate_id": gate_id,
        "commit": head,
        "visible": f"{ratio[0]}/{ratio[1]}",
        "existing": f"{existing[0]}/{existing[1]}" if existing else "not run",
        "checks": checks,
    }, ""


def _visible_tests_evidence(
    sandbox: Sandbox, head: str, timeout_s: int
) -> tuple[dict[str, Any] | None, str]:
    run = sandbox.exec(VISIBLE_TESTS_COMMAND, timeout_s)
    if run.denied is not None:
        return None, f"the visible tests were refused by the sandbox ({run.denied.reason_code})"
    if run.timed_out:
        return None, "the visible tests timed out"
    counts = pytest_counts(run.output)
    if counts is None:
        return None, f"no pytest summary in the output (exit {run.exit_code})"
    passed, failed, errors = counts["passed"], counts["failed"], counts["errors"]
    if run.exit_code != 0 or failed or errors or passed == 0:
        summary = f"passed={passed} failed={failed} errors={errors}, exit {run.exit_code}"
        return None, f"the visible tests did not pass ({summary})"
    return {
        "gate_id": "visible-tests",
        "commit": head,
        "visible": f"{passed}/{passed}",
        "existing": "not run (verify layer off)",
        "checks": [],
    }, ""


def _claimed_done(end: SessionEnd) -> bool:
    claim = end.last_claim
    return (
        isinstance(claim, dict) and claim.get("claim") == "done" and claim.get("phase") == end.phase
    )


def update_status(
    document: dict[str, Any],
    feature_id: str,
    end: SessionEnd,
    sandbox: Sandbox,
    now: Callable[[], datetime],
    test_timeout_s: int = 300,
) -> StatusDecision:
    unchanged = copy.deepcopy(document)
    if end.passes_already_set or end.phase != "build" or not _claimed_done(end):
        return StatusDecision(
            "none", "no done claim for the build phase; status unchanged", unchanged
        )
    features = unchanged.get("features")
    matches = (
        [f for f in features if f.get("id") == feature_id] if isinstance(features, list) else []
    )
    if len(matches) != 1:
        return StatusDecision(
            "note", f"passes stays false: no single feature {feature_id}", unchanged
        )
    if end.verify_layer:
        evidence, why_not = _gate_evidence(end.gate, end.head_commit)
    else:
        evidence, why_not = _visible_tests_evidence(sandbox, end.head_commit, test_timeout_s)
    if evidence is None:
        return StatusDecision("note", f"passes stays false for {feature_id}: {why_not}", unchanged)
    stamp = now()
    if stamp.tzinfo is None:
        raise ValueError("now() must return a timezone-aware datetime")
    tested_at = stamp.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    updated = copy.deepcopy(document)
    for feature in updated["features"]:
        if feature.get("id") == feature_id:
            feature.update(passes=True, evidence=evidence, testedAt=tested_at)
    message = f"{feature_id} passes: {evidence['gate_id']} at {end.head_commit[:7]}"
    return StatusDecision("status_set", message, updated, evidence)
