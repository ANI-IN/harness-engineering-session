"""The only writer of `passes`.

A2 lets the coding agent change `passes` after careful testing (F-a-108). The course moves that
decision to the harness, citing A3's separation of the agent doing the work from the agent judging
it (F-a-110): `passes` becomes true only when the agent claimed done for the build phase AND the
verify gate passed, or, with the verify layer off, the visible tests pass in the sandbox.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from shipharness.harness import suite_cache
from shipharness.harness.base import LayerContext
from shipharness.harness.decisions import HarnessDecision
from shipharness.harness.scope.features import FEATURE_LIST, FEATURE_SCHEMA, write_feature_list
from shipharness.harness.state.commit import commit_paths
from shipharness.runner import git
from shipharness.runner.models import SessionResult
from shipharness.runner.tools import summarise_pytest

VISIBLE_TESTS_ARGS = "tests/visible -q -rfE --no-header -p no:cacheprovider"
VISIBLE_TESTS_COMMAND = f"python -m pytest {VISIBLE_TESTS_ARGS}"
_COUNTS = re.compile(r"passed=(\d+) failed=(\d+) errors=(\d+)")
_RATIO = re.compile(r"(\d+)\s*/\s*(\d+)")


def claimed_done(ctx: LayerContext, result: SessionResult) -> bool:
    """The agent's last finish() for this phase said done (`last_claim`, set by the runner).
    Before the runner sets `last_claim`, a session that ended by an accepted done claim counts."""
    last = ctx.state.get("last_claim")
    if isinstance(last, dict):
        return last.get("claim") == "done" and last.get("phase") == result.phase
    return result.ended_by == "claim_done"


def _ratio(items: list[dict[str, Any]], name: str) -> str:
    for item in items:
        if item.get("name") == name:
            match = _RATIO.search(str(item.get("detail", "")))
            return f"{match.group(1)}/{match.group(2)}" if match else str(item.get("status", ""))
    return "not run"


def _gate_evidence(ctx: LayerContext) -> tuple[dict[str, Any] | None, str]:
    gate = ctx.state.get("verify.gate")
    if not isinstance(gate, dict):
        return None, "no verify gate result"
    if gate.get("passed") is not True:
        return None, f"the verify gate {gate.get('gate_id', '')} did not pass".replace("  ", " ")
    items = [i for i in gate.get("items", []) if isinstance(i, dict)]
    checks = [
        str(i["name"])
        for i in items
        if re.fullmatch(r"R\d+", str(i.get("name", ""))) and i.get("status") == "pass"
    ]
    return {
        "gate_id": str(gate.get("gate_id", "")),
        "commit": git.head_sha(ctx.workspace),
        "visible": _ratio(items, "visible tests"),
        "existing": _ratio(items, "existing tests"),
        "checks": checks,
    }, ""


def _visible_tests_evidence(ctx: LayerContext, timeout_s: int) -> tuple[dict[str, Any] | None, str]:
    run = suite_cache.run(
        ctx.state,
        ctx.sandbox,
        ctx.workspace,
        VISIBLE_TESTS_ARGS,
        timeout_s,
        command=VISIBLE_TESTS_COMMAND,
    )
    summary = summarise_pytest(run.output).splitlines()[0]
    match = _COUNTS.match(summary)
    passed, failed, errors = (int(n) for n in match.groups()) if match else (0, 0, 0)
    if run.exit_code != 0 or failed or errors or passed == 0:
        return None, f"the visible tests did not pass ({summary}, exit {run.exit_code})"
    total = f"{passed}/{passed + failed + errors}"
    return {
        "gate_id": "visible-tests",
        "commit": git.head_sha(ctx.workspace),
        "visible": total,
        "existing": "not run (verify layer off)",
        "checks": [],
    }, ""


# [walkthrough:S3:passes] start
def update_status(
    ctx: LayerContext,
    result: SessionResult,
    feature: dict[str, Any],
    now: Callable[[], datetime],
    test_timeout_s: int = 300,
) -> list[HarnessDecision]:
    """Set `passes` for the feature if, and only if, the evidence is there."""
    if ctx.state.get("scope.passes_set") or result.phase != "build":
        return []
    if not claimed_done(ctx, result):
        return []  # no claim, no status change, nothing run
    if "verify" in ctx.spec.layers:
        evidence, why_not = _gate_evidence(ctx)
    else:
        evidence, why_not = _visible_tests_evidence(ctx, test_timeout_s)
    if evidence is None:
        message = f"passes stays false for {feature['id']}: {why_not}"
        return [HarnessDecision(kind="note", layer="scope", message=message)]
    tested_at = now().astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    feature.update(passes=True, evidence=evidence, testedAt=tested_at)
    write_feature_list(ctx.workspace, feature)
    commit_paths(ctx.sandbox, [FEATURE_LIST, FEATURE_SCHEMA], f"harness: {feature['id']} passes")
    ctx.state["scope.passes_set"] = True
    return [
        HarnessDecision(
            kind="status_set",
            layer="scope",
            message=f"{feature['id']} passes: {evidence['gate_id']} at {evidence['commit'][:7]}",
            paths=[FEATURE_LIST],
            data={"feature_id": feature["id"], "evidence": evidence, "testedAt": tested_at},
        )
    ]


# [walkthrough:S3:passes] end
