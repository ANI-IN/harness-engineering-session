"""The referee (contract I-9): judges what an arm shipped, never how it got there.

A fresh export of the checkpoint plus the arm's product diff (harness artifacts stripped), the
check runner in a referee container (network none) with the hidden tests mounted read-only,
referee-set mutants against the shipped tests, the blinded reviewer, then a ScoreRecord written
to `exports/scores/` and a verdict event. Both arms go through exactly this code. Aborted runs are
judged too.

The checks the task's primary measure reads run first (with the mutants, when it counts them), and
a primary_verdict event goes out as soon as they finish; the secondary checks follow. The order
never changes a score: every check runs on the same build with the same inputs either way.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from shipharness.ab.artifacts import (
    HARNESS_ARTIFACT_PATTERNS,
    diff_paths,
    glob_match,
    is_harness_artifact,
)
from shipharness.ab.artifacts import strip_harness_artifacts as strip
from shipharness.ab.score import ScoreRecord, evaluate_primary, primary_fields
from shipharness.ab.workspace import (
    export_checkpoint,
    export_hidden_tests,
    init_repo,
    resolve_commit,
)
from shipharness.checks import params as P
from shipharness.checks.base import CheckResult
from shipharness.datasets.names import rule_label
from shipharness.events import EVENT_DATA_MODELS, Arm, EventBus
from shipharness.filters.pytest_cmd import (
    UnsafeTestId,
    check_test_id,
    counts,
    pytest_command,
)
from shipharness.harness.verify.checkrun import (
    RunnerOutputError,
    last_progress,
    new_nonce,
    parse_runner_output,
    runner_command,
    write_container_file,
)
from shipharness.reviewer import ReviewInput, ReviewOutcome, blind
from shipharness.runner.models import AgentRunResult
from shipharness.sandbox.base import Sandbox
from shipharness.sandbox.policy import Mount
from shipharness.tracing import NullTracer, Tracer, write_export

REFEREE_CHECKS: tuple[str, ...] = (
    "r1_tenant",
    "r2_roles",
    "r3_conventions",
    "r4_idempotency",
    "r5_audit",
    "r6_layering",
    "r7_migrations",
    "regression",
    "hidden_tests",
    "diff_scope",
    "flakiness",
    "continuity",
    "board",
)
WORK = "/work"  # the referee container mounts the build here (sandbox policy workspace_mount)
log = structlog.get_logger(__name__)
HIDDEN_DIR = "tests/hidden"  # inside the build, read-only, referee container only
INPUTS_MOUNT = "/referee-in"  # run log and per-session patches, read-only
# Shipped tests are run five times: TestGen-LLM deems a test flaky unless it passes on "every one of
# five executions" (B11, F-b-19).
FLAKY_RUNS = 5
# One line per test in pytest's -rA summary: `PASSED tests/x.py::test_a`.
_RESULT_LINE = re.compile(r"^(PASSED|FAILED|ERROR|XFAIL|XPASS) (\S+)")

# Which checks feed each ScoreRecord field (see shipharness.checks.scores). "mutants" are the
# referee-set mutants, run after the checks; an empty tuple means the host computes the field from
# the applied diff before any check runs.
MUTANTS = "mutants"
FIELD_SOURCES: dict[str, tuple[str, ...]] = {
    "r1_new_violations": ("r1_tenant",),
    "r1_leaks": ("r1_tenant",),
    "r2_new_violations": ("r2_roles",),
    "r3_new_failures": ("r3_conventions",),
    "r4_duplicates": ("r4_idempotency",),
    "r5_audit_missing": ("r5_audit",),
    "r6_ok": ("r6_layering",),
    "r7_ok": ("r7_migrations",),
    "regression_passed": ("regression",),
    "regression_total": ("regression",),
    "hidden_passed": ("hidden_tests",),
    "hidden_total": ("hidden_tests",),
    "flaky_tests": ("flakiness",),
    "continuity_failure": ("continuity",),
    "redone_lines_pct": ("continuity",),
    "board_ok": ("board",),
    "mutants_killed": (MUTANTS,),
    "mutants_total": (MUTANTS,),
    "shipped_tests": (),
    "out_of_scope_files": (),
    "test_phase_source_edits": (),
}


def primary_stage(measure: str) -> tuple[tuple[str, ...], bool]:
    """(checks, mutants): what must have run before `measure` can be evaluated. Checks keep the
    REFEREE_CHECKS order. A field without a known source waits for every check and the mutants."""
    needed: set[str] = set()
    for name in primary_fields(measure):
        if name not in FIELD_SOURCES:
            return REFEREE_CHECKS, True
        needed.update(FIELD_SOURCES[name])
    return tuple(c for c in REFEREE_CHECKS if c in needed), MUTANTS in needed


SandboxFactory = Callable[[Path, list[Mount], Arm], Sandbox]
MutantRunner = Callable[[Any, list[str], Path, Sandbox], str]
Reviewer = Callable[[ReviewInput], ReviewOutcome]


@dataclass
class RefereeTask:
    feature_id: str
    checkpoint: str
    ticket_text: str
    variant: str = "canonical"
    hidden_test_ids: list[str] = field(default_factory=list)
    allowed_paths: dict[str, list[str]] = field(default_factory=dict)
    primary_measure: str = ""
    # None: the check runner uses the adapter's documented exemptions for the checkpoint (as the
    # verify gate does). Set it, even to {}, only to override them for this task.
    exemptions: dict[str, list[str]] | None = None
    mutant_set: str = ""


@dataclass
class RefereeDeps:
    course_repo: Path
    checkpoint_ref: str | None  # git ref exported for the checkpoint (None: working tree)
    sandbox_factory: SandboxFactory
    exports_dir: Path
    base_dir: Path  # referee directories live here (outside the course checkout)
    seed: int
    tracer: Tracer = field(default_factory=NullTracer)
    reviewer: Reviewer | None = None
    grading_criteria: str = ""
    mutants: list[Any] = field(default_factory=list)  # referee set only
    mutant_runner: MutantRunner | None = None
    container_paths: bool = True  # False for the UNSANDBOXED fallback (no mounts)
    sandboxed: bool = True
    timeout_s: int = 1200
    # Baselines are deterministic for a checkpoint commit, task inputs, seed, and check code, so
    # A/Bs of the same task reuse them (None: no cache).
    baseline_cache_dir: Path | None = None
    # True: the primary measure's checks run first and primary_verdict is sent before the rest.
    # False: one runner call for every check, then the mutants (same scores, later verdict).
    early_primary: bool = True


@dataclass
class ArmVerdict:
    record: ScoreRecord
    results: list[CheckResult]
    referee_dir: Path
    apply_error: str | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _apply(build: Path, patch: Path) -> str | None:
    """Apply the product diff in the referee build (a repo this module created). None = ok."""
    if patch.stat().st_size == 0:
        return None
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
    done = subprocess.run(
        # absolute: git runs inside `build`, where a relative patch path does not resolve
        ["git", "-c", "core.autocrlf=false", "apply", "--whitespace=nowarn", str(patch.resolve())],
        cwd=build,
        capture_output=True,
        env=env,
        check=False,
    )
    if done.returncode == 0:
        return None
    return done.stderr.decode("utf-8", errors="replace").strip()[:500] or "git apply failed"


def _allowed(path: str, patterns: list[str]) -> bool:
    return any(glob_match(path, p) for p in patterns)


def shipped_tests(build: Path, paths: list[str]) -> list[str]:
    """Test ids (`file::name`) in test files the arm added or changed."""
    ids: list[str] = []
    for rel in paths:
        name = rel.rsplit("/", 1)[-1]
        if not (
            rel.startswith("tests/visible/") and name.startswith("test") and name.endswith(".py")
        ):
            continue
        path = build / rel
        if path.is_symlink() or not path.is_file():
            continue
        try:
            tree = ast.parse(path.read_bytes().decode("utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
                "test"
            ):
                ids.append(f"{rel}::{node.name}")
            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                ids += [
                    f"{rel}::{node.name}::{item.name}"
                    for item in node.body
                    if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
                    and item.name.startswith("test")
                ]
    return ids


# Files that decide how tests are collected and run. The arm's versions never apply when it is
# judged: they are restored to the checkpoint's (or removed), and so is anything under tests/hidden.
JUDGE_CONFIG_FILES = (
    "conftest.py",
    "tests/conftest.py",
    "pytest.ini",
    "setup.cfg",
    "tox.ini",
    "pyproject.toml",
)


def snapshot_judge_config(build: Path) -> dict[str, bytes | None]:
    return {
        rel: (build / rel).read_bytes() if (build / rel).is_file() else None
        for rel in JUDGE_CONFIG_FILES
    }


def restore_judge_config(build: Path, snapshot: dict[str, bytes | None]) -> None:
    for rel, data in snapshot.items():
        path = build / rel
        _remove(path)
        if data is not None:
            path.write_bytes(data)
    _remove(build / HIDDEN_DIR)


def _remove(path: Path) -> None:
    """Remove a file, link, or directory without following links."""
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def checkpoint_test_ids(build: Path) -> list[str]:
    """Test ids in the checkpoint's visible test files (static: top-level and class methods)."""
    visible = build / "tests" / "visible"
    if not visible.is_dir():
        return []
    files = sorted(
        p.relative_to(build).as_posix()
        for p in visible.rglob("test*.py")
        if p.is_file() and not p.is_symlink()
    )
    return shipped_tests(build, files)


def _event_fields(result: CheckResult) -> dict[str, Any]:
    """check_result event data: only the fields the event model declares (it forbids extras
    such as artifacts or metrics)."""
    allowed = EVENT_DATA_MODELS["check_result"].model_fields
    return {k: v for k, v in result.model_dump(mode="json").items() if k in allowed}


def _score_fields(results: list[CheckResult]) -> dict[str, Any]:
    """Score fields from the checks package's own mapping, when it provides one."""
    try:
        from shipharness.checks.scores import score_fields  # type: ignore[import-not-found]
    except ImportError:
        return {}
    return dict(score_fields(results))


def default_mutant_runner(mutant: Any, tests: list[str], build: Path, sandbox: Sandbox) -> str:
    from shipharness.filters import Mutant, run_mutant  # type: ignore[attr-defined]

    m = mutant if isinstance(mutant, Mutant) else Mutant(**mutant)
    return str(run_mutant(m, tests, build, sandbox, 300))


def _product_sessions(patches: list[Path], out_dir: Path) -> list[Path]:
    """Copies of the per-session patches without harness artifacts, for the continuity check.
    The state layer rewrites progress.md and the handoff every session; those are not product
    work (M6 pilot run 2: they read as session 2 removing session 1's lines)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    copies: list[Path] = []
    for index, patch in enumerate(patches, start=1):
        copy = out_dir / f"session-{index}.patch"
        copy.write_bytes(strip(patch.read_bytes()) if patch.is_file() else b"")
        copies.append(copy)
    return copies


class Referee:
    """Judges both arms of one task with the same checks, seed, and baseline."""

    def __init__(self, task: RefereeTask, deps: RefereeDeps) -> None:
        self.task, self.deps = task, deps
        self._baseline: str | None = None
        self._baseline_done = False
        self._baseline_lock = threading.Lock()
        self._sha: str | None = None

    # -- container -----------------------------------------------------------------------------

    def _paths(
        self, build: Path, hidden: Path, runlog: Path | None, sessions: list[Path]
    ) -> tuple[dict[str, Any], list[Mount]]:
        """Container-side locations of the referee-only inputs, and the read-only mounts.
        Hidden tests sit inside the build tree (ids are build-relative), mounted read-only, in
        the referee container only; the run log and per-session patches are mounted beside."""
        if (
            not self.deps.container_paths
        ):  # UNSANDBOXED fallback: no mounts, copy and use host paths
            if hidden.is_dir():
                shutil.rmtree(build / HIDDEN_DIR, ignore_errors=True)
                shutil.copytree(hidden, build / HIDDEN_DIR)
            return {
                "hidden_dir": HIDDEN_DIR,
                "run_log": str(runlog) if runlog else None,
                "session_patches": [str(p) for p in sessions],
            }, []
        mounts: list[Mount] = [(hidden, f"{WORK}/{HIDDEN_DIR}", "ro")]
        if runlog is not None:
            mounts.append((runlog, f"{INPUTS_MOUNT}/{runlog.name}", "ro"))
        for index, patch in enumerate(sessions, start=1):
            mounts.append((patch, f"{INPUTS_MOUNT}/session-{index}.patch", "ro"))
        return {
            "hidden_dir": HIDDEN_DIR,
            "run_log": f"{INPUTS_MOUNT}/{runlog.name}" if runlog else None,
            "session_patches": [
                f"{INPUTS_MOUNT}/session-{i}.patch" for i in range(1, len(sessions) + 1)
            ],
        }, mounts

    def _start(
        self, build: Path, mounts: list[Mount], arm: Arm
    ) -> tuple[Sandbox | None, str | None]:
        """Start a referee container; a failure is reported, never raised, so a Docker hiccup
        gives a "could not judge" verdict instead of losing both arms' runs."""
        sandbox: Sandbox | None = None
        try:
            sandbox = self.deps.sandbox_factory(build, mounts, arm)
            sandbox.start()
        except Exception as exc:  # noqa: BLE001
            if sandbox is not None:
                with contextlib.suppress(Exception):  # best effort; the start already failed
                    sandbox.stop()
            return None, f"referee container did not start: {type(exc).__name__}: {exc}"[:500]
        return sandbox, None

    _INPUTS = "/tmp/shipharness-referee"

    def _run_checks(
        self,
        sandbox: Sandbox,
        params: dict[str, Any],
        baseline: str | None,
        checks: tuple[str, ...],
    ) -> tuple[list[CheckResult], list[dict[str, Any]], str | None]:
        error = self._write_inputs(sandbox, params, baseline)
        if error is not None:
            return [], [], error
        return self._run_runner(sandbox, checks, bool(baseline), self.deps.timeout_s)

    def _write_inputs(
        self, sandbox: Sandbox, params: dict[str, Any], baseline: str | None
    ) -> str | None:
        """Write the check params (and the baseline) into the container. None = ok."""
        root = self._INPUTS
        sandbox.exec(f"mkdir -p {root}", 60)
        try:
            write_container_file(sandbox, f"{root}/params.json", json.dumps(params, sort_keys=True))
            if baseline:
                write_container_file(sandbox, f"{root}/baseline.json", baseline)
        except RuntimeError as exc:
            return f"referee container not usable: {exc}"[:500]
        return None

    def _run_runner(
        self, sandbox: Sandbox, checks: tuple[str, ...], baseline: bool, timeout_s: int
    ) -> tuple[list[CheckResult], list[dict[str, Any]], str | None]:
        root = self._INPUTS
        nonce = new_nonce()
        command = runner_command(
            build=".",
            checks=list(checks),
            checkpoint=self.task.checkpoint,
            feature=self.task.feature_id,
            seed=self.deps.seed,
            params=f"{root}/params.json",
            baseline=f"{root}/baseline.json" if baseline else None,
            nonce=nonce,
        )
        output = sandbox.exec(command, timeout_s)
        try:
            results, progress = parse_runner_output(output.output, nonce=nonce)
        except RunnerOutputError as exc:
            return [], [], f"check runner failed (exit {output.exit_code}): {exc}"[:500]
        return results, progress, None

    def baseline(self, arm: Arm = "bare") -> str | None:
        """Runner output on the clean checkpoint (computed once, shared by both arms; reused
        across A/Bs of the same task through the baseline cache). Thread-safe: run_ab starts it
        while the arms work."""
        with self._baseline_lock:
            if self._baseline_done:
                return self._baseline
            cached = self._baseline_cache_path()
            if cached is not None and cached.is_file():
                self._baseline = cached.read_text(encoding="utf-8")
                self._baseline_done = True
                return self._baseline
            self._baseline = self._compute_baseline(arm)
            self._baseline_done = True
            if cached is not None and self._baseline is not None:
                cached.parent.mkdir(parents=True, exist_ok=True)
                partial = cached.with_suffix(".part")
                partial.write_text(self._baseline, encoding="utf-8")
                partial.replace(cached)
            return self._baseline

    def _baseline_cache_path(self) -> Path | None:
        if self.deps.baseline_cache_dir is None or self.deps.checkpoint_ref is None:
            return None
        import shipharness.checks as checks_package
        from shipharness.harness.verify import checkrun

        code = hashlib.sha256()
        for path in sorted(Path(checks_package.__file__).parent.glob("*.py")):
            code.update(path.name.encode() + b"\0" + path.read_bytes())
        code.update(Path(checkrun.__file__).read_bytes())
        key = {
            "checkpoint_sha": resolve_commit(self.deps.course_repo, self.deps.checkpoint_ref),
            "seed": self.deps.seed,
            "hidden_test_ids": sorted(self.task.hidden_test_ids),
            "allowed_paths": self.task.allowed_paths,
            "exemptions": self.task.exemptions,
            "checks": list(REFEREE_CHECKS),
            "code": code.hexdigest(),
        }
        digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:32]
        return Path(self.deps.baseline_cache_dir) / f"{digest}.json"

    def _compute_baseline(self, arm: Arm) -> str | None:
        root = self.deps.base_dir / "baseline"
        build = export_checkpoint(self.deps.course_repo, self.deps.checkpoint_ref, root / "build")
        init_repo(build, f"checkpoint {self.task.checkpoint}")
        hidden = export_hidden_tests(
            self.deps.course_repo, self.deps.checkpoint_ref, root / "hidden"
        )
        inputs, mounts = self._paths(build, hidden, None, [])
        sandbox, start_error = self._start(build, mounts, arm)
        if sandbox is None:
            log.warning("referee baseline unavailable", reason=start_error)
            return None
        try:
            checks = tuple(c for c in REFEREE_CHECKS if c not in ("continuity", "flakiness"))
            params = self._params(
                inputs,
                changed_files=[],
                shipped_files=[],
                shipped_ids=[],
                test_phase_files=[],
                existing_ids=checkpoint_test_ids(build),
            )
            results, _p, error = self._run_checks(sandbox, params, None, checks)
        finally:
            sandbox.stop()
        if error is not None:
            return None
        return json.dumps({"results": [r.model_dump(mode="json") for r in results]})

    def _params(
        self,
        inputs: dict[str, Any],
        *,
        changed_files: list[str],
        shipped_files: list[str],
        shipped_ids: list[str],
        test_phase_files: list[str],
        existing_ids: list[str],
        run_id: str = "",
    ) -> dict[str, Any]:
        """Check params under the names the checks read (shipharness.checks.params).

        Regression runs the checkpoint's own test ids only: tests the arm added (new files or new
        functions in existing files) are judged by flakiness and mutants, never as regressions.
        `file::name` selects every parameter of a parametrized test."""
        params: dict[str, Any] = {
            **inputs,
            P.REGRESSION_EXPECTED: list(existing_ids),
            P.RUN_ID: run_id,
            P.HIDDEN_TESTS: list(self.task.hidden_test_ids),
            P.SHIPPED_TESTS: shipped_ids,
            "shipped_test_files": shipped_files,  # informational, for reports
            P.CHANGED_FILES: list(changed_files),
            P.PHASE_FILES: {"test": list(test_phase_files)},
            P.ALLOWED_PATHS: self.task.allowed_paths,
            P.HARNESS_ARTIFACTS: list(HARNESS_ARTIFACT_PATTERNS),
            P.FLAKY_RUNS: FLAKY_RUNS,
        }
        if existing_ids:
            params[P.REGRESSION_TARGETS] = list(existing_ids)
        if self.task.exemptions is not None:
            params[P.EXEMPTIONS] = self.task.exemptions
        return params

    # -- judging -------------------------------------------------------------------------------

    def judge(
        self,
        *,
        run_id: str,
        ab_id: str | None,
        arm: Arm,
        layers: list[str],
        result: AgentRunResult | None,
        diff: bytes,
        bus: EventBus | None,
        run_log: Path | None = None,
        test_phase_files: list[str] | None = None,
        session_patches: list[Path] | None = None,
        recorded: bool = False,
        export: bool = True,  # False for the swap test: its records are not runs
        log_run_id: str | None = None,
        arm_ended: float | None = None,
    ) -> ArmVerdict:
        """`log_run_id` is the run id whose events `run_log` holds (continuity counts that run's
        sessions); swap and replay pass the original run id while scoring under their own.
        `arm_ended` is the `time.monotonic()` reading when the arm finished (default: now); the
        primary_verdict event reports the seconds since then."""

        def emit(type_: str, data: Any) -> None:
            if bus is not None:
                bus.publish(type_, data, run_id=run_id, arm=arm, recorded=recorded)  # type: ignore[arg-type]

        ended = time.monotonic() if arm_ended is None else arm_ended
        baseline = self.baseline(arm)
        rdir = self.deps.base_dir / f"{arm}-{hashlib.sha256(run_id.encode()).hexdigest()[:10]}"
        build = export_checkpoint(self.deps.course_repo, self.deps.checkpoint_ref, rdir / "build")
        init_repo(build, f"checkpoint {self.task.checkpoint}")
        hidden = export_hidden_tests(
            self.deps.course_repo, self.deps.checkpoint_ref, rdir / "hidden"
        )
        existing_ids = checkpoint_test_ids(build)
        config = snapshot_judge_config(build)
        product = strip(diff)  # harness artifacts are state, not product changes
        patch = rdir / "product.patch"
        patch.write_bytes(product)
        apply_error = _apply(build, patch)
        restore_judge_config(build, config)  # the arm never configures how it is judged
        paths = [p for p in diff_paths(product) if p != "/dev/null"]
        allowed = self.task.allowed_paths
        scope_globs = [*allowed.get("build", []), *allowed.get("test", [])]
        out_of_scope = [p for p in paths if scope_globs and not _allowed(p, scope_globs)]
        phase_edits = [
            p
            for p in (test_phase_files or [])
            if not is_harness_artifact(p) and allowed and not _allowed(p, allowed.get("test", []))
        ]
        shipped_ids = shipped_tests(build, paths)
        shipped_files = sorted({i.split("::", 1)[0] for i in shipped_ids})

        results: list[CheckResult] = []
        mutant_outcomes: dict[str, str] = {}
        error = apply_error
        meta = {"run_id": run_id, "ab_id": ab_id, "arm": arm, "seed": self.deps.seed}
        with self.deps.tracer.agent_run("referee", meta, tags=[arm, "referee"]) as root:
            referee_url = self.deps.tracer.url(root)
            if referee_url:
                emit("trace_link", {"url": referee_url, "kind": "referee"})
            scored: dict[str, Any] = {
                "run_id": run_id,
                "ab_id": ab_id,
                "arm": arm,
                "layers": layers,
                "result": result,
                "shipped": len(shipped_ids),
                "out_of_scope": len(out_of_scope),
                "phase_edits": len(phase_edits),
                "referee_url": referee_url,
                "recorded": recorded,
            }
            announced: list[bool] = []

            def announce(
                found: list[CheckResult], mutants: dict[str, str], why: str | None
            ) -> None:
                """Send primary_verdict once: the primary measure on what has been judged so far
                (the same record code as the final verdict, so the values are the same)."""
                if announced:
                    return
                announced.append(True)
                early = self._record(
                    **scored, results=found, mutants=mutants, review=None, failed=why is not None
                )
                emit(
                    "primary_verdict",
                    {
                        "arm": arm,
                        "run_id": run_id,
                        "feature_id": self.task.feature_id,
                        "primary_measure": self.task.primary_measure,
                        "passed": early.passed_primary,
                        "values": early.primary,
                        "elapsed_s": round(time.monotonic() - ended, 3),
                    },
                )

            sandbox: Sandbox | None = None
            if apply_error is None:
                sessions = _product_sessions(list(session_patches or []), rdir / "sessions")
                inputs, mounts = self._paths(build, hidden, run_log, sessions)
                sandbox, error = self._start(build, mounts, arm)
            if sandbox is not None:
                try:
                    params = self._params(
                        inputs,
                        changed_files=paths,
                        shipped_files=shipped_files,
                        shipped_ids=shipped_ids,
                        test_phase_files=list(test_phase_files or []),
                        existing_ids=existing_ids,
                        run_id=log_run_id or run_id,
                    )
                    results, mutant_outcomes, error = self._judge_build(
                        sandbox, params, baseline, build, shipped_ids, emit, announce
                    )
                finally:
                    sandbox.stop()
            announce([], {}, error)  # nothing ran in a container (diff or start failed)
            review = self._review(diff, emit)
            record = self._record(
                **scored,
                results=results,
                mutants=mutant_outcomes,
                review=review,
                failed=error is not None,
            )
            root.set_outputs({"passed_primary": record.passed_primary})
        if export:
            write_export("scores", run_id, record, self.deps.exports_dir)
        summary = self._summary(record, error)
        emit(
            "verdict",
            {
                "primary": record.primary,
                "passed_primary": record.passed_primary,
                "summary": summary,
            },
        )
        report = {
            "seed": self.deps.seed,
            "apply_error": apply_error,
            "error": error,
            "files": paths,
            "out_of_scope": out_of_scope,
            "test_phase_source_edits": phase_edits,
            "shipped_tests": shipped_ids,
            "mutants": mutant_outcomes,
            "results": [r.model_dump(mode="json") for r in results],
        }
        (rdir / "referee.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return ArmVerdict(record=record, results=results, referee_dir=rdir, apply_error=apply_error)

    def _judge_build(
        self,
        sandbox: Sandbox,
        params: dict[str, Any],
        baseline: str | None,
        build: Path,
        shipped_ids: list[str],
        emit: Callable[[str, Any], None],
        announce: Callable[[list[CheckResult], dict[str, str], str | None], None],
    ) -> tuple[list[CheckResult], dict[str, str], str | None]:
        """Run the checks and the referee mutants in the referee container.

        With `early_primary`, the checks the primary measure reads (and the mutants, when it counts
        them) run first and `announce` gets their results; the secondary checks follow in a second
        runner call within the same time budget. Otherwise one call runs every check, then the
        mutants, then `announce`. A runner failure in either call discards every check result, as
        a failure of the one combined call does; the mutants run either way."""
        if self.deps.early_primary:
            first, mutants_first = primary_stage(self.task.primary_measure)
        else:
            first, mutants_first = REFEREE_CHECKS, True
        stages = (first, tuple(c for c in REFEREE_CHECKS if c not in first))
        results: list[CheckResult] = []
        mutants: dict[str, str] | None = None
        budget = float(self.deps.timeout_s)
        error = self._write_inputs(sandbox, params, baseline)
        for index, checks in enumerate(stages):
            if checks and error is None:
                started = time.monotonic()
                found, progress, error = self._run_runner(
                    sandbox, checks, bool(baseline), max(1, round(budget))
                )
                budget -= time.monotonic() - started
                if error is None:
                    self._report(found, progress, emit)
                    results += found
            if index == 0:
                if mutants_first:
                    mutants = self._mutants(sandbox, build, shipped_ids, emit)
                announce([] if error else list(results), mutants or {}, error)
        if mutants is None:
            mutants = self._mutants(sandbox, build, shipped_ids, emit)
        if error is not None:
            return [], mutants, error
        order = {name: i for i, name in enumerate(REFEREE_CHECKS)}
        return sorted(results, key=lambda r: order.get(r.check, len(order))), mutants, None

    def _report(
        self,
        results: list[CheckResult],
        progress: list[dict[str, Any]],
        emit: Callable[[str, Any], None],
    ) -> None:
        """check_progress and check_result events (and trace spans) for one runner call."""
        for update in last_progress(progress):
            emit("check_progress", update)
        for r in results:
            with self.deps.tracer.child(
                f"check:{r.check}",
                "tool",
                new_violations=r.new_violations,
                total_probes=r.total_probes,
            ):
                pass
            emit("check_result", _event_fields(r))

    def _mutants(
        self, sandbox: Sandbox, build: Path, tests: list[str], emit: Callable[[str, Any], None]
    ) -> dict[str, str]:
        outcomes: dict[str, str] = {}
        if not self.deps.mutants:
            return outcomes
        runner = self.deps.mutant_runner or default_mutant_runner
        tests = self._passing_unmutated(sandbox, tests)
        for mutant in self.deps.mutants:
            mutant_id = str(mutant["id"] if isinstance(mutant, dict) else mutant.id)
            if not tests:
                outcome = "survived"  # no shipped test can kill it
            else:
                try:
                    outcome = runner(mutant, tests, build, sandbox)
                except Exception as exc:  # noqa: BLE001 - one broken mutant never stops the referee
                    outcome = f"error: {type(exc).__name__}"
            outcome = outcome if outcome in ("killed", "survived", "timeout") else "error"
            outcomes[mutant_id] = outcome
            emit(
                "mutant_result",
                {"mutant_id": mutant_id, "set": "referee", "outcome": outcome, "killed_by": None},
            )
        return outcomes

    @staticmethod
    def _passing_unmutated(sandbox: Sandbox, tests: list[str]) -> list[str]:
        """Shipped tests that pass on the arm's unmutated build. A test that already fails
        would "kill" every mutant, so only these may judge mutants (as filter 1 requires).

        One pytest process runs every shipped test and reports each one (`-rA`); a shipped id
        passes when every test under it passed. An id with no reported outcome (a collection
        error, a timeout, a skip) is run on its own, as before (batched and isolated
        outcomes were compared on every arm of a pilot round and matched)."""
        safe: list[str] = []
        for test in tests:
            try:
                safe.append(check_test_id(test))
            except UnsafeTestId:
                continue
        if not safe:
            return []
        outcomes: dict[str, set[str]] = {}
        batch = sandbox.exec(pytest_command("python", safe, extra="-rA"), 300)
        if not batch.timed_out:
            for line in batch.output.splitlines():
                match = _RESULT_LINE.match(line.strip())
                if match:
                    outcomes.setdefault(match.group(2), set()).add(match.group(1))
        passing: set[str] = set()
        for test in safe:
            under = [
                found
                for node, found in outcomes.items()
                if node == test or node.startswith((test + "::", test + "["))
            ]
            if under:
                if all(found == {"PASSED"} for found in under):
                    passing.add(test)
                continue
            run = sandbox.exec(pytest_command("python", [test]), 300)
            if run.exit_code == 0 and not run.timed_out and counts(run.output)["passed"] >= 1:
                passing.add(test)
        return [test for test in safe if test in passing]

    def _review(self, diff: bytes, emit: Callable[[str, Any], None]) -> ReviewOutcome | None:
        if self.deps.reviewer is None:
            return None
        inp = ReviewInput(
            task=self.task.ticket_text,
            diff=blind(diff),
            grading_criteria=self.deps.grading_criteria,
        )
        outcome = self.deps.reviewer(inp)
        if outcome.review is not None:
            emit("reviewer_output", outcome.review.model_dump(mode="json"))
        return outcome

    def _checkpoint_sha(self) -> str | None:
        """The commit the exported checkpoint ref names (None: the working tree)."""
        if self.deps.checkpoint_ref is None:
            return None
        if self._sha is None:
            self._sha = resolve_commit(self.deps.course_repo, self.deps.checkpoint_ref)
        return self._sha

    def _record(
        self,
        *,
        run_id: str,
        ab_id: str | None,
        arm: Arm,
        layers: list[str],
        result: AgentRunResult | None,
        results: list[CheckResult],
        mutants: dict[str, str],
        shipped: int,
        out_of_scope: int,
        phase_edits: int,
        review: ReviewOutcome | None,
        referee_url: str | None,
        recorded: bool,
        failed: bool,
    ) -> ScoreRecord:
        by = {r.check: r for r in results}

        def new(check: str, default: int = 0) -> int:
            return by[check].new_violations if check in by else default

        def ok(check: str) -> bool:
            return bool(by[check].passed) if check in by else False

        def counts(check: str, total_default: int) -> tuple[int, int]:
            if check not in by:
                return 0, total_default
            r = by[check]
            return max(r.total_probes - r.new_violations, 0), r.total_probes

        r1 = by.get("r1_tenant")
        regression = counts("regression", 0)
        hidden = counts("hidden_tests", len(self.task.hidden_test_ids))
        continuity = by.get("continuity")
        fields: dict[str, Any] = {
            "r1_new_violations": new("r1_tenant"),
            "r1_leaks": sum(1 for f in r1.findings if f.severity == "leak" and not f.baseline)
            if r1
            else 0,
            "r2_new_violations": new("r2_roles"),
            "r3_new_failures": new("r3_conventions"),
            "r4_duplicates": new("r4_idempotency"),
            "r5_audit_missing": new("r5_audit"),
            "r6_ok": ok("r6_layering"),
            "r7_ok": ok("r7_migrations"),
            "regression_passed": regression[0],
            "regression_total": regression[1],
            "hidden_passed": hidden[0],
            "hidden_total": hidden[1],
            "mutants_killed": sum(1 for o in mutants.values() if o == "killed"),
            "mutants_total": len(self.deps.mutants),
            "shipped_tests": shipped,
            "flaky_tests": new("flakiness"),
            "out_of_scope_files": out_of_scope,
            "test_phase_source_edits": phase_edits,
            "continuity_failure": (not continuity.passed) if continuity else None,
            "redone_lines_pct": None,
            "board_ok": ok("board"),
        }
        # Computed here on the host from the applied diff (authoritative), not taken from the
        # container checks: mutants, scope counts, and the shipped-test count.
        own = {
            "mutants_killed",
            "mutants_total",
            "out_of_scope_files",
            "test_phase_source_edits",
            "shipped_tests",
        }
        fields.update(
            {k: v for k, v in _score_fields(results).items() if k in fields and k not in own}
        )
        primary, passed = evaluate_primary(self.task.primary_measure, fields)
        passed = passed and not failed
        referee_accepts = (
            passed
            and all(fields[k] == 0 for k in ("r1_new_violations", "r2_new_violations"))
            and fields["r6_ok"]
            and fields["r7_ok"]
            and fields["regression_passed"] == fields["regression_total"]
        )
        verdict = review.review.verdict if review and review.review else None
        return ScoreRecord(
            run_id=run_id,
            ab_id=ab_id,
            arm=arm,
            feature_id=self.task.feature_id,
            variant=self.task.variant,
            checkpoint=self.task.checkpoint,
            checkpoint_sha=self._checkpoint_sha(),
            layers=sorted(layers),  # type: ignore[arg-type]
            status=result.status if result else "ERROR",
            claim=result.claim if result else "none",
            **fields,
            reviewer_verdict=verdict,
            reviewer_agrees=None if verdict is None else (verdict == "accept") == referee_accepts,
            primary=primary,
            passed_primary=passed,
            cost_usd=result.cost_usd if result else 0.0,
            review_cost_usd=round(review.cost_usd, 6) if review else 0.0,
            turns_total=result.turns_total if result else 0,
            wall_s=result.wall_s if result else 0.0,
            trace_url=result.trace_url if result else None,
            referee_trace_url=referee_url,
            sandboxed=self.deps.sandboxed,
            recorded=recorded,
            captured_at=_now(),
        )

    @staticmethod
    def _summary(record: ScoreRecord, error: str | None) -> str:
        said = f"agent said {record.claim}"
        if error:
            return f"{said}; referee could not judge the build: {error}"[:500]
        outcome = "passes" if record.passed_primary else "fails"
        return (
            f"{said}; referee: {outcome} the primary measure; hidden tests "
            f"{record.hidden_passed}/{record.hidden_total}, mutants killed "
            f"{record.mutants_killed}/{record.mutants_total}, {rule_label('R1')}, new violations "
            f"{record.r1_new_violations}"
        )
