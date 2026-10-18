"""Check runner (contract I-1): one entry point for the verify gate and the referee.

    python -m shipharness.checks.runner --build <dir> --checks r1_tenant,r2_roles,... \\
        --checkpoint <tag> --feature <id> --seed <int> [--params <json-file>] \\
        [--baseline <json-file>] [--adapter module:attr]

stdout: one JSON document {"results": [CheckResult, ...]}. stderr: one JSON line per progress
update {"check": "R1", "done": 37, "total": 112, "label": "House rule 1 probes 37/112"}. Anything
the build prints while it runs goes to stderr, so stdout stays parseable.

Params (all optional): `exemptions` (per rule; default: the adapter's list for the checkpoint),
`allowed_paths` ({"build": [...], "test": [...]}), `adapter`, and the per-check keys documented in
each check module (`hidden_tests`, `shipped_tests`, `flaky_runs`, `regression_targets`,
`changed_files`, `diff_path`, `phase_files`, `harness_artifacts`, `session_patches`, `run_log`,
`r3_max_examples`, `board_mode`, `artifacts_dir`).

Exit codes: 0 no new violations, 3 new violations, 1 error (bad arguments or a check crashed).
Checks never call a model. The runner executes the build's code: run it inside a container.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from shipharness.checks.adapter import load_adapter
from shipharness.checks.base import (
    CheckContext,
    CheckResult,
    Finding,
    get_check,
    make_result,
    mark_baseline,
    registered_checks,
)
from shipharness.checks.builtin import RULE_LABELS, load_builtin_checks

EXIT_OK, EXIT_ERROR, EXIT_VIOLATIONS = 0, 1, 3
Progress = Callable[[str, int, int, str], None]


def json_progress(check: str, done: int, total: int, label: str) -> None:
    line = json.dumps({"check": check, "done": done, "total": total, "label": label})
    print(line, file=sys.stderr, flush=True)


def resolve_names(spec: str) -> list[str]:
    """Check names from "r1_tenant,R2,regression" (rule labels are accepted)."""
    load_builtin_checks()
    by_label = {label.lower(): name for name, label in RULE_LABELS.items()}
    names = []
    for raw in (part.strip() for part in spec.split(",")):
        if not raw:
            continue
        name = raw if raw in registered_checks() else by_label.get(raw.lower(), raw)
        if name not in registered_checks():
            raise ValueError(f"unknown check {raw!r}; registered: {registered_checks()}")
        names.append(name)
    return names


def load_baseline(path: Path | None) -> dict[str, CheckResult] | None:
    if path is None:
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {r["check"]: CheckResult.model_validate(r) for r in data.get("results", [])}


def _crashed(name: str, exc: BaseException, started: float) -> CheckResult:
    finding = Finding(
        rule=RULE_LABELS.get(name, name),
        severity="error",
        detail_key="crashed",
        detail=f"check crashed: {type(exc).__name__}: {str(exc)[:300]}",
    )
    return make_result(name, [finding], total_probes=0, started=started)


def run_checks(
    build_dir: Path,
    names: list[str],
    *,
    checkpoint: str,
    feature_id: str,
    seed: int,
    params: dict[str, Any] | None = None,
    baseline: dict[str, CheckResult] | None = None,
    progress: Progress | None = None,
) -> tuple[list[CheckResult], bool]:
    """Run the named checks; returns (results, any check crashed)."""
    load_builtin_checks()
    params = dict(params or {})
    adapter = load_adapter(params.get("adapter"))
    exemptions = params["exemptions"] if "exemptions" in params else adapter.exemptions(checkpoint)
    results: list[CheckResult] = []
    crashed = False
    for name in names:
        label = RULE_LABELS.get(name, name)
        ctx = CheckContext(
            checkpoint=checkpoint,
            feature_id=feature_id,
            seed=seed,
            phase_allowed_paths=dict(params.get("allowed_paths") or {}),
            exemptions=exemptions,
            params=params,
        )
        if progress is not None:
            ctx.progress = lambda d, t, text, label=label: progress(label, d, t, text)
        started = time.monotonic()
        try:
            result = get_check(name).run(Path(build_dir), ctx)
        except Exception as exc:
            result, crashed = _crashed(name, exc, started), True
        if baseline is not None:
            result = mark_baseline(result, baseline.get(name))
        results.append(result)
    return results, crashed


def exit_code(results: list[CheckResult], crashed: bool) -> int:
    if crashed:
        return EXIT_ERROR
    return EXIT_OK if all(r.passed for r in results) else EXIT_VIOLATIONS


@contextmanager
def stdout_to_stderr() -> Iterator[None]:
    """Send everything written to stdout (Python and file descriptor 1) to stderr."""
    sys.stdout.flush()
    saved_obj = sys.stdout
    try:
        saved_fd: int | None = os.dup(1)
        os.dup2(2, 1)
    except OSError:
        saved_fd = None
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout.flush()
        sys.stdout = saved_obj
        if saved_fd is not None:
            os.dup2(saved_fd, 1)
            os.close(saved_fd)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m shipharness.checks.runner", description=__doc__)
    p.add_argument("--build", required=True, type=Path)
    p.add_argument("--checks", required=True)
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--feature", required=True)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--params", type=Path)
    p.add_argument("--baseline", type=Path)
    p.add_argument("--adapter")
    p.add_argument("--nonce", help="echoed in the results document")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        names = resolve_names(args.checks)
        params = json.loads(args.params.read_text(encoding="utf-8")) if args.params else {}
        if args.adapter:
            params["adapter"] = args.adapter
        baseline = load_baseline(args.baseline)
        if not args.build.is_dir():
            raise ValueError(f"build directory not found: {args.build}")
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return EXIT_ERROR
    with stdout_to_stderr():
        results, crashed = run_checks(
            args.build,
            names,
            checkpoint=args.checkpoint,
            feature_id=args.feature,
            seed=args.seed,
            params=params,
            baseline=baseline,
            progress=json_progress,
        )
    document: dict[str, object] = {"results": [r.model_dump(mode="json") for r in results]}
    if args.nonce:
        document["nonce"] = args.nonce
    print(json.dumps(document), flush=True)
    return exit_code(results, crashed)


if __name__ == "__main__":
    sys.exit(main())
