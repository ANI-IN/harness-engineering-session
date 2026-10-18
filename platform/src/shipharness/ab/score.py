"""ScoreRecord and the pre-registered primary measures."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from shipharness.events import Arm
from shipharness.harness.decisions import LayerName

# Bumped whenever a measurement change could change a score.
# The console's A/B report shows only records of the current version.
REFEREE_VERSION = "2026-10-17"


class ScoreRecord(BaseModel):
    """One per arm per run; also the LangSmith evaluator output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    ab_id: str | None
    arm: Arm
    feature_id: str
    variant: str
    checkpoint: str
    # The commit the checkpoint named when the run was judged (None: judged from the working tree).
    checkpoint_sha: str | None = None
    layers: list[LayerName]
    status: str
    claim: str
    r1_new_violations: int
    r1_leaks: int
    r2_new_violations: int
    r3_new_failures: int
    r4_duplicates: int
    r5_audit_missing: int
    r6_ok: bool
    r7_ok: bool
    regression_passed: int
    regression_total: int
    hidden_passed: int
    hidden_total: int
    mutants_killed: int
    mutants_total: int
    shipped_tests: int
    flaky_tests: int
    out_of_scope_files: int
    test_phase_source_edits: int
    continuity_failure: bool | None
    redone_lines_pct: float | None
    board_ok: bool
    reviewer_verdict: Literal["accept", "reject"] | None
    reviewer_agrees: bool | None
    primary: dict[str, float | int | bool]
    passed_primary: bool
    cost_usd: float
    review_cost_usd: float
    turns_total: int
    wall_s: float
    trace_url: str | None
    referee_trace_url: str | None
    sandboxed: bool
    recorded: bool
    captured_at: str
    # True: the harness arm ran alone (`ab --arms harness`); never in a bare-vs-harness comparison.
    single_arm: bool = False
    # True: a constructed example (`shipharness example`, scripted steps, no model); never counted.
    constructed: bool = False
    referee_version: str = REFEREE_VERSION


# Primary measure grammar (dataset `outputs.primary_measure`):
#   failure condition: "<field><op><number>" terms joined by " or "  -> passed = no term holds
#   bare field:        "continuity_failure"                           -> passed = field is falsy
#   co-primary counts: "hidden_passed,mutants_killed"                 -> passed = every count
#                       equals its total (hidden_total, mutants_total)
_TERM = re.compile(r"^\s*([a-z_0-9]+)\s*(>=|<=|==|!=|>|<)\s*(-?\d+(?:\.\d+)?)\s*$")
_OPS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
}
_TOTALS = {"hidden_passed": "hidden_total", "mutants_killed": "mutants_total"}


def evaluate_primary(measure: str, fields: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """(primary values, passed_primary) for one run."""
    text = measure.strip()
    if not text:
        return {}, True
    if "," in text:
        names = [n.strip() for n in text.split(",") if n.strip()]
        primary = {n: fields[n] for n in names}
        passed = all(fields[n] == fields[_TOTALS[n]] for n in names if n in _TOTALS)
        return primary, passed
    failed = False
    primary: dict[str, Any] = {}
    for term in re.split(r"\s+or\s+", text):
        match = _TERM.match(term)
        if match:
            name, op, value = match.groups()
            current = fields[name]
            primary[name] = current
            failed = failed or bool(_OPS[op](current, float(value)))
        else:
            name = term.strip()
            current = fields[name]
            primary[name] = bool(current)
            failed = failed or bool(current)
    return primary, not failed


def primary_fields(measure: str) -> list[str]:
    """The ScoreRecord fields `evaluate_primary` reads for `measure`, in order: each named field,
    and for a co-primary count also the total it is compared with."""
    text = measure.strip()
    if not text:
        return []
    names: list[str] = []
    if "," in text:
        for name in (n.strip() for n in text.split(",") if n.strip()):
            names += [name, _TOTALS[name]] if name in _TOTALS else [name]
        return names
    for term in re.split(r"\s+or\s+", text):
        match = _TERM.match(term)
        names.append(match.group(1) if match else term.strip())
    return names


# The 12 scores of the combined referee evaluator.
SCORE_KEYS: tuple[str, ...] = (
    "r1_new_violations",
    "r2_new_violations",
    "r3_new_failures",
    "r4_duplicates",
    "r5_audit_missing",
    "r7_ok",
    "regression_pass_rate",
    "hidden_passed",
    "mutants_killed",
    "out_of_scope_files",
    "flaky_tests",
    "passed_primary",
)


def evaluator_scores(record: ScoreRecord) -> list[dict[str, Any]]:
    data = record.model_dump()
    total = record.regression_total
    data["regression_pass_rate"] = round(record.regression_passed / total, 4) if total else 0.0
    return [{"key": key, "score": data[key]} for key in SCORE_KEYS]
