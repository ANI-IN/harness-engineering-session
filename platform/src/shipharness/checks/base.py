"""Check interface for the referee and verify gate. Checks never call a model."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict

MAX_FINDINGS = 200
Severity = Literal["violation", "leak", "error", "info"]


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule: str  # "R1".."R8", "regression", "hidden", "scope", "flaky", "continuity", "board"
    severity: Severity  # "info" is reported but never counted
    endpoint: str | None = None  # "GET /issues/{issue_id}"
    detail: str
    # Stable identifier of the failure within (rule, endpoint), e.g. "leak", "status",
    # "test:tests/visible/test_x.py::test_y". Part of the baseline key; `detail` is free text.
    detail_key: str = ""
    baseline: bool = False  # present at the checkpoint baseline

    @property
    def counted(self) -> bool:
        return self.severity != "info"


class CheckResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    check: str
    passed: bool  # no new violations
    new_violations: int
    baseline_violations: int
    total_probes: int
    findings: list[Finding]
    duration_ms: int
    seed: int | None = None
    artifacts: list[str] = []
    # Numbers a ScoreRecord needs that are not finding counts (e.g. "redone_lines_pct").
    metrics: dict[str, float | int | bool | None] = {}


def _no_progress(_done: int, _total: int, _label: str) -> None:
    return None


@dataclass
class CheckContext:
    checkpoint: str
    feature_id: str
    seed: int = 0
    phase_allowed_paths: dict[str, list[str]] = field(default_factory=dict)
    exemptions: dict[str, list[str]] = field(default_factory=dict)  # rule -> ["POST /path", ...]
    progress: Callable[[int, int, str], None] = _no_progress
    # Per-check inputs from the runner's --params file (hidden test ids, shipped tests, run log...).
    params: dict[str, Any] = field(default_factory=dict)

    def is_exempt(self, rule: str, endpoint: str | None) -> bool:
        return endpoint is not None and endpoint in self.exemptions.get(rule, [])


class Check(Protocol):
    name: str

    def run(self, build_dir: Path, ctx: CheckContext) -> CheckResult: ...


_REGISTRY: dict[str, type[Check]] = {}


def register_check[C](cls: C) -> C:
    name = cls.name  # type: ignore[attr-defined]
    if name in _REGISTRY:
        raise ValueError(f"check {name!r} is already registered")
    _REGISTRY[name] = cls  # type: ignore[assignment]
    return cls


def get_check(name: str) -> Check:
    try:
        return _REGISTRY[name]()
    except KeyError:
        raise KeyError(f"no check named {name!r}; registered: {sorted(_REGISTRY)}") from None


def registered_checks() -> list[str]:
    return sorted(_REGISTRY)


def _ordered(findings: list[Finding]) -> list[Finding]:
    counted = [f for f in findings if f.counted]
    return counted + [f for f in findings if not f.counted]


def make_result(
    check: str,
    findings: list[Finding],
    *,
    total_probes: int,
    started: float,
    seed: int | None = None,
    artifacts: list[str] | None = None,
    metrics: dict[str, float | int | bool | None] | None = None,
) -> CheckResult:
    """Build a CheckResult with every counted finding treated as new (no baseline applied yet)."""
    counted = [f for f in findings if f.counted]
    return CheckResult(
        check=check,
        passed=not counted,
        new_violations=len(counted),
        baseline_violations=0,
        total_probes=total_probes,
        findings=_ordered(findings)[:MAX_FINDINGS],
        duration_ms=int((time.monotonic() - started) * 1000),
        seed=seed,
        artifacts=artifacts or [],
        metrics=metrics or {},
    )


def _key(f: Finding) -> tuple[str, str | None, str, str]:
    return (f.rule, f.endpoint, f.severity, f.detail_key)


def mark_baseline(current: CheckResult, baseline: CheckResult | None) -> CheckResult:
    """Mark findings already present at the checkpoint; count and gate only the new ones."""
    known = {_key(f) for f in baseline.findings} if baseline else set()
    marked = [f.model_copy(update={"baseline": _key(f) in known}) for f in current.findings]
    new = [f for f in marked if not f.baseline and f.counted]
    old = [f for f in marked if f.baseline and f.counted]
    info = [f for f in marked if not f.counted]
    return current.model_copy(
        update={
            "findings": (new + old + info)[:MAX_FINDINGS],
            "new_violations": len(new),
            "baseline_violations": len(old),
            "passed": not new,
        }
    )
