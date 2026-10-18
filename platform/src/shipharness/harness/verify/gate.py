"""The verify gate (contract I-8): runs when the agent calls finish(claim="done").

Everything runs in the arm's own container: visible tests, the check runner (R1-R7, existing tests,
board) on a copy of the workspace in /tmp, and the clean-state check on the workspace itself. The
gate never runs hidden tests or referee-set mutants: those checks are not in GATE_CHECKS.
"""

from __future__ import annotations

import json
import re
import shlex
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from shipharness.datasets.names import rule_label
from shipharness.harness import suite_cache
from shipharness.harness.verify.checkrun import (
    CHECK_LABELS,
    RunnerOutputError,
    failure_lines,
    last_progress,
    new_nonce,
    parse_runner_output,
    runner_command,
    write_container_file,
)
from shipharness.harness.verify.clean_state import DEFAULT_RUFF_SELECT, clean_state_check
from shipharness.harness.verify.models import GateItem, GateResult
from shipharness.runner.models import TEAMTRACK_VISIBLE_TESTS
from shipharness.runner.tools import summarise_pytest
from shipharness.sandbox.base import Sandbox

GATE_CHECKS: tuple[str, ...] = (
    "r1_tenant",
    "r2_roles",
    "r3_conventions",
    "r4_idempotency",
    "r5_audit",
    "r6_layering",
    "r7_migrations",
    "regression",
    "board",
)
_ITEM_ORDER = ["existing tests", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "board"]
_SAFE = re.compile(r"[^A-Za-z0-9_.-]")


@dataclass
class GateConfig:
    checkpoint: str
    feature: str
    seed: int = 0
    checks: tuple[str, ...] = GATE_CHECKS
    params: dict[str, Any] = field(default_factory=dict)
    baseline_json: str | None = None
    timeout_s: int = 600
    # Seconds of harness work left (HARNESS_TIMEOUT_S); every gate command fits inside it.
    time_left: Callable[[], float | None] = field(default=lambda: None)
    # The run's visible tests (TeamTrack: tests/visible; testgen: the repository's test directory).
    visible_tests_dir: str = TEAMTRACK_VISIBLE_TESTS
    # False when the repository has no migrations: the clean-state item skips the head check.
    migrations: bool = True
    # None when the repository has its own ruff config: the clean-state item uses it as it is.
    ruff_select: str | None = DEFAULT_RUFF_SELECT
    # (the run's state, the content key of the workspace the gate copies): the visible-test item
    # reuses an identical harness run of the suite on that content. None: it always runs.
    visible_reuse: tuple[dict[str, Any], str] | None = None

    def limit(self, own_s: int) -> int:
        """A command's time limit: its own, capped by the harness time left (at least 1 s)."""
        left = self.time_left()
        return own_s if left is None else max(1, min(own_s, int(left)))


def _visible_tests(sandbox: Sandbox, build: str, cfg: GateConfig) -> tuple[GateItem, list[str]]:
    """The run's visible tests on the copy (TeamTrack: tests/visible). With `cfg.visible_reuse`,
    an identical harness run of the suite on the same content is reused (suite_cache)."""
    reuse = cfg.visible_reuse
    where = shlex.quote(cfg.visible_tests_dir)
    args = f"{where} -q -rfE --no-header -p no:cacheprovider"
    result = suite_cache.lookup(reuse[0], reuse[1], args, "copy") if reuse else None
    if result is None:
        result = sandbox.exec(f"cd {build} && python -m pytest {args}", cfg.limit(cfg.timeout_s))
        if reuse:
            suite_cache.store(reuse[0], reuse[1], args, "copy", result)
    summary = summarise_pytest(result.output)
    head, *failures = summary.splitlines()
    if result.exit_code == 0:
        return GateItem(name="visible tests", status="pass", detail=head), []
    lines = [f for f in failures if f.startswith(("FAILED", "ERROR"))] or [
        f"FAIL visible tests: {head}"
    ]
    return GateItem(name="visible tests", status="fail", detail=head), lines


def _check_items(
    sandbox: Sandbox, cfg: GateConfig, root: str, on_progress: Callable[[dict], None] | None
) -> tuple[list[GateItem], list[str]]:
    params = {**cfg.params, "artifacts_dir": f"{root}/artifacts"}  # never in the arm workspace
    labels = [CHECK_LABELS.get(c, c) for c in cfg.checks]
    baseline = None
    try:
        write_container_file(
            sandbox, f"{root}/params.json", json.dumps(params, sort_keys=True), cfg.limit(30)
        )
        if cfg.baseline_json:
            write_container_file(sandbox, f"{root}/baseline.json", cfg.baseline_json, cfg.limit(30))
            baseline = f"{root}/baseline.json"
    except RuntimeError as exc:  # a slow write near the harness time limit: no checks ran
        detail = f"could not write the check inputs in the container: {exc}"[:300]
        return [GateItem(name=n, status="fail", detail=detail) for n in labels], [
            f"FAIL checks: {detail}"
        ]
    nonce = new_nonce()
    command = runner_command(
        build=f"{root}/build",
        checks=list(cfg.checks),
        checkpoint=cfg.checkpoint,
        feature=cfg.feature,
        seed=cfg.seed,
        params=f"{root}/params.json",
        baseline=baseline,
        nonce=nonce,
    )
    output = sandbox.exec(f"cd {root} && {command}", cfg.limit(cfg.timeout_s))
    try:
        results, progress = parse_runner_output(output.output, nonce=nonce)
    except RunnerOutputError as exc:
        detail = f"check runner failed (exit {output.exit_code}): {exc}"[:300]
        return [GateItem(name=n, status="fail", detail=detail) for n in labels], [
            f"FAIL checks: {detail}"
        ]
    for update in last_progress(progress):
        if on_progress is not None:
            on_progress(update)
    by_label = {CHECK_LABELS.get(r.check, r.check): r for r in results}
    items, lines = [], []
    for name in labels:
        r = by_label.get(name)
        if r is None:
            items.append(GateItem(name=name, status="skipped", detail="not reported by the runner"))
        elif r.passed:
            items.append(GateItem(name=name, status="pass", detail=f"{r.total_probes} probes"))
        else:
            items.append(GateItem(name=name, status="fail", detail=f"{r.new_violations} new"))
            lines += failure_lines(r)
    return items, lines


# [walkthrough:S4:gate] start
def run_gate(
    sandbox: Sandbox,
    cfg: GateConfig,
    *,
    gate_id: str,
    base_sha: str,
    phase: str,
    on_update: Callable[[GateResult], None] | None = None,
    on_progress: Callable[[dict], None] | None = None,
) -> GateResult:
    """Verification the agent does not control: every item runs in the arm container."""
    root = f"/tmp/shipharness-gate-{_SAFE.sub('_', gate_id)}"
    names = ["visible tests", *(_ITEM_ORDER if phase == "build" else []), "clean state"]
    if on_update:  # pending pills first, so the console shows the gate running
        pending = [GateItem(name=n, status="pending") for n in names]
        on_update(GateResult(gate_id=gate_id, items=pending, passed=False, feedback=""))
    sandbox.exec(
        f"rm -rf {root} && mkdir -p {root}/build && cp -a ./. {root}/build/", cfg.limit(300)
    )
    visible, lines = _visible_tests(sandbox, f"{root}/build", cfg)
    items = [visible]
    if phase == "build":
        check_items, check_lines = _check_items(sandbox, cfg, root, on_progress)
        items += sorted(check_items, key=_order)
        lines += check_lines
    clean = clean_state_check(
        sandbox, base_sha, cfg.limit(120), migrations=cfg.migrations, ruff_select=cfg.ruff_select
    )
    items.append(clean)
    if clean.status == "fail":
        lines.append(f"FAIL clean state: {clean.detail}")
    sandbox.exec(f"rm -rf {root}", cfg.limit(60))
    passed = not any(i.status == "fail" for i in items)
    feedback = "" if passed else _feedback(gate_id, items, lines)
    result = GateResult(gate_id=gate_id, items=items, passed=passed, feedback=feedback)
    if on_update:
        on_update(result)
    return result


# [walkthrough:S4:gate] end


def _order(item: GateItem) -> int:
    return _ITEM_ORDER.index(item.name) if item.name in _ITEM_ORDER else len(_ITEM_ORDER)


def _feedback(gate_id: str, items: list[GateItem], lines: list[str]) -> str:
    """Text the agent sees as the finish result: a summary and the first three failures. House
    rule items are named by their label ("House rule 1: Tenant isolation")."""
    failed = [rule_label(i.name) for i in items if i.status == "fail"]
    return "\n".join(
        [
            f"Gate {gate_id}: {len(failed)} of {len(items)} items failed ({', '.join(failed)}).",
            *lines[:3],
            "Fix these, commit your work, and call finish again.",
        ]
    )
