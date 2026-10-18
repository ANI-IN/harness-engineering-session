"""Talking to the check runner (contract I-1) inside a container: command line, input files, and
parsing of its output. Used by the verify gate (arm container) and the referee (referee container).

The sandbox returns stdout and stderr combined, so the parser accepts both kinds of line: the
results document `{"results": [...]}` and progress lines `{"check": ..., "done": ..., ...}`.
"""

from __future__ import annotations

import base64
import json
import secrets
import shlex
from typing import Any

from pydantic import ValidationError

from shipharness.checks.base import CheckResult
from shipharness.datasets.names import rule_short
from shipharness.sandbox.base import Sandbox

RUNNER_MODULE = "shipharness.checks.runner"
_CHUNK = 48_000  # bytes of base64 per exec: well below the 128 KiB single-argument limit

# Check registry name -> gate item / score name.
CHECK_LABELS: dict[str, str] = {
    "r1_tenant": "R1",
    "r2_roles": "R2",
    "r3_conventions": "R3",
    "r4_idempotency": "R4",
    "r5_audit": "R5",
    "r6_layering": "R6",
    "r7_migrations": "R7",
    "regression": "existing tests",
    "hidden_tests": "hidden tests",
    "diff_scope": "diff scope",
    "flakiness": "flakiness",
    "continuity": "continuity",
    "board": "board",
}


class RunnerOutputError(ValueError):
    """The check runner produced no parseable results document."""


def runner_command(
    *,
    build: str,
    checks: list[str],
    checkpoint: str,
    feature: str,
    seed: int,
    params: str | None = None,
    baseline: str | None = None,
    python: str = "python",
    nonce: str | None = None,
) -> str:
    # -P: the working directory (the arm's build, for the referee) is never put on sys.path, so a
    # `shipharness` package shipped in the build cannot replace the image's runner.
    argv = [
        python,
        "-P",
        "-m",
        RUNNER_MODULE,
        "--build",
        build,
        "--checks",
        ",".join(checks),
        "--checkpoint",
        checkpoint,
        "--feature",
        feature,
        "--seed",
        str(int(seed)),
    ]
    if params:
        argv += ["--params", params]
    if baseline:
        argv += ["--baseline", baseline]
    if nonce:
        argv += ["--nonce", nonce]
    return " ".join(shlex.quote(a) for a in argv)


def write_container_file(sandbox: Sandbox, path: str, text: str, timeout_s: int = 30) -> None:
    """Write `text` to `path` inside the container through exec (no shared mount needed).
    Base64 in chunks, so any content and any size survives shell quoting and argv limits."""
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    target = shlex.quote(path)
    first = True
    for start in range(0, max(len(encoded), 1), _CHUNK):
        chunk = encoded[start : start + _CHUNK]
        redirect = ">" if first else ">>"
        result = sandbox.exec(f"printf %s {chunk} | base64 -d {redirect} {target}", timeout_s)
        if result.exit_code != 0:
            raise RuntimeError(f"could not write {path} in the container: {result.output[:200]}")
        first = False


def _json_objects(text: str) -> list[dict[str, Any]]:
    """Every top-level JSON object in `text`, whether one per line or pretty-printed."""
    decoder = json.JSONDecoder()
    found: list[dict[str, Any]] = []
    index = 0
    while True:
        start = text.find("{", index)
        if start < 0:
            return found
        try:
            value, end = decoder.raw_decode(text, start)
        except ValueError:
            index = start + 1
            continue
        if isinstance(value, dict):
            found.append(value)
        index = end


def new_nonce() -> str:
    """Per-run token the runner echoes in its results document (see parse_runner_output)."""
    return secrets.token_hex(16)


def parse_runner_output(
    text: str, nonce: str | None = None
) -> tuple[list[CheckResult], list[dict[str, Any]]]:
    """(results, progress updates). Raises RunnerOutputError if there is no results document.

    With `nonce`, only the first results document carrying that nonce counts: build code imported
    by the checks shares the output stream and could print a results document of its own."""
    results: list[CheckResult] | None = None
    progress: list[dict[str, Any]] = []
    for obj in _json_objects(text):
        if "results" in obj and isinstance(obj["results"], list):
            if nonce is not None and (results is not None or obj.get("nonce") != nonce):
                continue
            try:
                results = [CheckResult.model_validate(r) for r in obj["results"]]
            except ValidationError as exc:
                raise RunnerOutputError(f"invalid check result: {exc.errors()[:1]}") from None
        elif {"check", "done", "total"} <= obj.keys():
            progress.append(
                {
                    "check": str(obj["check"]),
                    "done": int(obj["done"]),
                    "total": int(obj["total"]),
                    "label": str(obj.get("label", "")),
                }
            )
    if results is None:
        tail = text.strip()[-300:]
        raise RunnerOutputError(f"check runner printed no results document: {tail}")
    return results, progress


def last_progress(progress: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The final progress update per check, in first-seen order (for check_progress events)."""
    latest: dict[str, dict[str, Any]] = {}
    for update in progress:
        latest[update["check"]] = update
    return list(latest.values())


def failure_lines(result: CheckResult, limit: int = 3) -> list[str]:
    """Grep-friendly lines for the new findings of a failing check (a house rule by its short
    name, "House rule 1"; the gate's summary line above them gives the full label)."""
    label = rule_short(CHECK_LABELS.get(result.check, result.check))
    lines = []
    for finding in [f for f in result.findings if not f.baseline][:limit]:
        where = f" {finding.endpoint}" if finding.endpoint else ""
        lines.append(f"FAIL {label}{where}: {finding.severity}: {finding.detail}")
    if not lines:
        lines.append(f"FAIL {label}: {result.new_violations} new violation(s)")
    return lines
