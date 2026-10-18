"""Shared checks for scripted diff cases (used by the visible tests and by the grader).

A case (fixtures/cases.json) gives the phase, the allowed paths, whether the state layer is on,
the paths the diff changes, and, for an out-of-scope diff, the refusals expected as
[path, code] pairs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_cases(folder: Path) -> list[dict[str, Any]]:
    cases = json.loads((folder / "cases.json").read_text(encoding="utf-8"))
    for case in cases:
        case["diff"] = (folder / "diffs" / f"{case['id']}.diff").read_bytes()
    return cases


def verdict_for(case: dict[str, Any]) -> Any:
    from a3scope.scope import PhasePolicy, check_diff

    policy = PhasePolicy(allowed_paths=case["allowed_paths"], state_layer=case["state_layer"])
    return check_diff(policy, case["phase"], case["diff"])


def assert_changed_paths(case: dict[str, Any]) -> None:
    from a3scope.diffparse import changed_paths, parse_diff

    got = changed_paths(parse_diff(case["diff"]))
    assert sorted(got) == sorted(case["changed"]), f"{case['id']}: changed paths {got}"


def assert_rejected(case: dict[str, Any]) -> None:
    verdict = verdict_for(case)
    assert verdict.accepted is False, f"{case['id']}: out-of-scope diff was accepted"
    got = {(r.path, r.code) for r in verdict.refusals}
    if case.get("unparseable_ok") and any(code == "unparseable" for _, code in got):
        return
    for path, code in case["refusals"]:
        assert (path, code) in got, f"{case['id']}: expected refusal {(path, code)}, got {got}"
    for refusal in verdict.refusals:
        assert refusal.message, f"{case['id']}: refusal for {refusal.path!r} has no message"
        assert refusal.path in refusal.message, f"{case['id']}: message does not name the path"


def assert_accepted(case: dict[str, Any]) -> None:
    verdict = verdict_for(case)
    refused = [(r.path, r.code) for r in verdict.refusals]
    assert verdict.accepted is True and not refused, f"{case['id']}: false positive {refused}"
