"""Filtered test generation for a Python repo with pytest (`shipharness testgen`).

The runner runs the test phase only, in a fresh copy of the repo. Every test function the agent
wrote then goes through the five filters; the kept tests are written to an output directory with a
JSON report. The learner's repository is never modified.

With `--layers verify`, the verify layer filters the new tests in the visible-test directory at the
end of the test phase; it uses testgen's filter context, and testgen records those results and
filters only the tests the layer did not evaluate, so each proposed test is evaluated once and the
report counts every one of them.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import importlib
import json
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from shipharness.config import Prices, Settings
from shipharness.cost import Caps, CostTracker
from shipharness.events import EventBus
from shipharness.filters.models import CandidateTest, FilterContext, FilterResult
from shipharness.filters.mutants import MutantError, load_mutants
from shipharness.filters.pipeline import (
    FilterSetupError,
    build_context,
    collect_candidates,
    discarded,
    kept_tests,
    run_pipeline,
)
from shipharness.filters.source import is_test_path
from shipharness.harness.base import Harness
from shipharness.runner.loop import RunOptions, run_agent
from shipharness.runner.model import ModelClient
from shipharness.runner.models import AgentRunSpec, checked_tests_dir
from shipharness.runner.paths import PathOutsideWorkspace, resolve_in_workspace
from shipharness.runner.tools import iter_workspace_files
from shipharness.sandbox import DockerSandbox, LocalSandbox, default_policy, render_policy
from shipharness.sandbox.base import Sandbox
from shipharness.testgen.workspace import prepare_workspace
from shipharness.tracing import make_tracer

SandboxKind = Literal["local", "docker"]


@dataclass
class TestgenOptions:
    __test__ = False  # not a pytest test class

    repo: Path
    module: str  # repo-relative path of the module under test
    layers: str = "none"  # "none" or "verify"
    max_tests: int = 10
    sandbox: SandboxKind = "local"
    image: str | None = None
    existing_tests: list[str] = field(default_factory=list)  # [] = the repo's configured suite
    mutants: Path | None = None  # default: <repo>/mutants/<dotted module>.jsonl if present
    mutant_set: str | None = None  # "filter" or "referee": only that set of the file (None: all)
    python: str = "python"
    out_dir: Path | None = None
    test_phase_turns: int | None = None
    doctest_modules: bool = False  # existing suite runs with --doctest-modules
    # Metadata of a testgen-targets-v1 line, when the target comes from the dataset; its
    # `baseline_includes_doctests` overrides `doctest_modules`.
    target_metadata: dict[str, Any] | None = None
    # Directory of the visible tests (run_visible_tests, the verify gate, the layer's filters).
    # None: the directory of the existing tests (see visible_tests_dir).
    visible_tests_dir: str | None = None


@dataclass
class TestgenResult:
    __test__ = False

    exit_code: int
    run_id: str
    status: str = "ERROR"
    error: str | None = None
    unsandboxed: bool = False
    results: list[FilterResult] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    discarded: dict[str, FilterResult] = field(default_factory=dict)
    not_evaluated: list[str] = field(default_factory=list)
    out_dir: Path | None = None
    events_path: Path | None = None
    cost_usd: float = 0.0
    baseline_includes_doctests: bool = False


def baseline_doctests(options: TestgenOptions) -> bool:
    """Whether doctests are part of the baseline suite: the dataset target's
    `baseline_includes_doctests` when present, else the --doctest-modules option."""
    value = (options.target_metadata or {}).get("baseline_includes_doctests")
    if isinstance(value, bool):
        return value
    return options.doctest_modules


def baseline_tests(existing: list[str], module_rel: str, doctests: bool) -> list[str]:
    """Existing-suite targets. With doctests, the module under test is added so pytest collects
    its doctests (upstream boltons runs `pytest --doctest-modules boltons tests`). An empty list
    stays empty: the repo's configured suite decides what is collected."""
    tests = list(existing)
    if doctests and tests and module_rel not in tests:
        tests.append(module_rel)
    return tests


def visible_tests_dir(repo: Path, existing: list[str], explicit: str | None = None) -> str:
    """The run's visible-test directory: `explicit` when given, else the deepest directory that
    holds every existing test path (`tests/test_queueutils.py` gives `tests`), else `tests` when
    the repository has one, else the repository root (`.`)."""
    if explicit:
        return checked_tests_dir(explicit.replace("\\", "/"))
    dirs = []
    for entry in existing:
        rel = entry.split("::", 1)[0].replace("\\", "/").rstrip("/")
        if not rel:
            continue
        is_dir = (Path(repo) / rel).is_dir() or not PurePosixPath(rel).suffix
        dirs.append(rel if is_dir else str(PurePosixPath(rel).parent))
    if dirs:
        common = os.path.commonpath(dirs).replace("\\", "/")
        return checked_tests_dir(common or ".")
    return "tests" if (Path(repo) / "tests").is_dir() else "."


def module_to_dotted(module: str) -> str:
    path = PurePosixPath(module.replace("\\", "/"))
    parts = list(path.with_suffix("").parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def new_run_id() -> str:
    return f"r-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


def _ticket(module: str, max_tests: int) -> str:
    return (
        f"Write pytest tests for the module `{module}` in this repository. Put them in new test "
        f"files next to the existing tests (for example tests/test_{PurePosixPath(module).stem}"
        f"_generated.py). Write at most {max_tests} test functions. Each test must check real "
        "behaviour of the module with assertions. Do not change source files and do not mock "
        "the module under test."
    )


def _test_hashes(workspace: Path) -> dict[str, str]:
    root = Path(workspace)
    hashes: dict[str, str] = {}
    for path in iter_workspace_files(root):
        rel = path.relative_to(root).as_posix()
        if rel.endswith(".py") and is_test_path(rel) and PurePosixPath(rel).name != "conftest.py":
            hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def strip_tests(source: str, remove: set[str]) -> str:
    """Remove the named test functions (`name` or `Class::name`) with their decorators."""
    tree = ast.parse(source)
    spans: list[tuple[int, int]] = []

    def span(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> tuple[int, int]:
        first = min([node.lineno] + [d.lineno for d in node.decorator_list])
        return first, node.end_lineno or node.lineno

    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name in remove:
            spans.append(span(node))
        elif isinstance(node, ast.ClassDef):
            methods = [
                item
                for item in node.body
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
                and f"{node.name}::{item.name}" in remove
            ]
            if methods and len(methods) == len(node.body):
                spans.append(span(node))
            else:
                spans.extend(span(item) for item in methods)
    lines = source.splitlines(keepends=True)
    drop = {n for first, last in spans for n in range(first, last + 1)}
    kept = [line for number, line in enumerate(lines, start=1) if number not in drop]
    return "".join(kept)


def _write_outputs(out_dir: Path, workspace: Path, result: TestgenResult, files: list[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    kept = set(result.kept)
    for rel in files:
        ids = [tid for tid in kept if tid.split("::", 1)[0] == rel]
        if not ids:
            continue
        source = resolve_in_workspace(workspace, rel).read_text(encoding="utf-8")
        all_ids = {
            r.test_id.split("::", 1)[1]
            for r in result.results
            if "::" in r.test_id and r.test_id.split("::", 1)[0] == rel
        }
        remove = all_ids - {tid.split("::", 1)[1] for tid in ids}
        target = out_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(strip_tests(source, remove), encoding="utf-8")
    report = {
        "run_id": result.run_id,
        "status": result.status,
        "unsandboxed": result.unsandboxed,
        "baseline_includes_doctests": result.baseline_includes_doctests,
        "kept": result.kept,
        "not_evaluated": result.not_evaluated,
        "results": [r.model_dump() for r in result.results],
    }
    (out_dir / "testgen-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


@dataclass
class FilterRun:
    """The five filters for one testgen run, evaluated at most once per proposed test, whichever
    component asks: the verify layer at the end of the test phase (as its pipeline), then testgen
    for the tests the layer did not see. At most `max_tests` tests are evaluated; the rest are
    listed as not evaluated."""

    max_tests: int
    bus: EventBus | None
    run_id: str
    arm: Literal["bare", "harness"]
    workspace: Path
    ctx: FilterContext | None = None
    results: list[FilterResult] = field(default_factory=list)
    evaluated: list[str] = field(default_factory=list)
    not_evaluated: list[str] = field(default_factory=list)

    def evaluate(self, cands: list[CandidateTest]) -> list[FilterResult]:
        if self.ctx is None:
            raise FilterSetupError("the filter context is not ready")
        seen = set(self.evaluated) | set(self.not_evaluated)
        new = [c for c in cands if c.test_id not in seen]
        room = max(0, self.max_tests - len(self.evaluated))
        now, later = new[:room], new[room:]
        self.not_evaluated += [c.test_id for c in later]
        results = run_pipeline(now, self.ctx, self.bus, run_id=self.run_id, arm=self.arm)
        self.evaluated += [c.test_id for c in now]
        self.results += results
        return results

    def __call__(
        self, candidates: list[dict[str, str]], _layer_ctx: Any, _shas: dict[str, str]
    ) -> list[FilterResult]:
        """The verify layer's test-phase pipeline. Candidates are rebuilt from their files, the
        same way testgen collects them (a candidate's source is its whole test file)."""
        wanted = [c["test_id"] for c in candidates]
        files = sorted({c["file"] for c in candidates})
        by_id = {c.test_id: c for c in collect_candidates(self.workspace, files)}
        return self.evaluate([by_id[t] for t in wanted if t in by_id])


def _harness(layers: str, pipeline: FilterRun | None = None) -> Harness:
    if layers == "none":
        return Harness([])
    if layers != "verify":
        raise ValueError(f"--layers must be none or verify, got {layers!r}")
    with contextlib.suppress(ModuleNotFoundError):  # the integrator adds this module (I-4)
        importlib.import_module("shipharness.harness.layers")  # registers the layers
    try:
        return Harness.from_names(frozenset({"verify"}), pipeline=pipeline)
    except ValueError as exc:
        raise ValueError(f"the verify layer is not available in this build: {exc}") from None


def _sandbox(
    options: TestgenOptions, settings: Settings, workspace: Path, bus: EventBus, run_id: str
) -> Sandbox:
    policy = default_policy(settings)
    arm = "harness" if options.layers != "none" else "bare"
    if options.sandbox == "docker":
        if not options.image:
            raise ValueError("--sandbox docker needs --image (a prepared image for this repo)")
        return DockerSandbox(
            policy, options.image, workspace, bus, run_id, arm, runtime=settings.sandbox_runtime
        )
    return LocalSandbox(policy, workspace, bus, run_id, arm)


def run_testgen(
    options: TestgenOptions, settings: Settings, *, client: ModelClient
) -> TestgenResult:
    run_id = new_run_id()
    result = TestgenResult(exit_code=1, run_id=run_id, unsandboxed=options.sandbox == "local")
    repo = Path(options.repo)
    arm: Literal["bare", "harness"] = "harness" if options.layers != "none" else "bare"
    workspace = Path(tempfile.gettempdir()) / "shipharness-ws" / run_id / "ws"
    filter_run = FilterRun(options.max_tests, None, run_id, arm, workspace)
    try:
        module_path = resolve_in_workspace(repo, options.module)
        harness = _harness(options.layers, filter_run)
        visible = visible_tests_dir(repo, options.existing_tests, options.visible_tests_dir)
    except (PathOutsideWorkspace, ValueError) as exc:
        result.error = f"invalid --module, --layers, or --visible-tests: {exc}"
        return result
    if not module_path.is_file():
        result.error = f"module not found: {options.module}"
        return result
    module_rel = module_path.relative_to(repo.resolve()).as_posix()
    dotted = module_to_dotted(module_rel)
    mutant_file = options.mutants or (repo / "mutants" / f"{dotted}.jsonl")
    try:
        mutants = load_mutants(mutant_file, repo) if Path(mutant_file).is_file() else []
        if options.mutant_set:
            mutants = [m for m in mutants if m.set == options.mutant_set]
    except MutantError as exc:
        result.error = f"invalid mutant file: {exc}"
        return result

    doctests = baseline_doctests(options)
    result.baseline_includes_doctests = doctests

    run_dir = Path(settings.runs_dir) / run_id
    result.events_path = run_dir / "events.jsonl"
    result.out_dir = Path(options.out_dir) if options.out_dir else run_dir / "kept"
    tracker = CostTracker(
        Prices.load(settings.prices_file),
        Caps.from_settings(settings),
        Path(settings.runs_dir).parent / "ledger.jsonl",
        session_id=settings.shipharness_class_date,
    )
    with EventBus(result.events_path, ab_id=None) as bus:
        try:
            prepare_workspace(repo, workspace)
            sandbox = _sandbox(options, settings, workspace, bus, run_id)
            sandbox.start()
        except (ValueError, RuntimeError, OSError) as exc:
            result.error = str(exc)
            shutil.rmtree(workspace.parent, ignore_errors=True)
            return result
        try:
            existing = baseline_tests(options.existing_tests, module_rel, doctests)
            bus.publish(
                "harness_decision",
                {
                    "kind": "baseline",
                    "layer": "testgen",
                    "message": (
                        "baseline suite includes doctests (--doctest-modules)"
                        if doctests
                        else "baseline suite without doctests"
                    ),
                    "paths": existing,
                    "data": {"doctest_modules": doctests},
                },
                run_id=run_id,
                arm=arm,
            )
            ctx = build_context(
                workspace,
                sandbox,
                existing_tests=existing,
                mutants=mutants,
                target_module=dotted,
                python=options.python,
                timeout_s=settings.tool_timeout_s,
                doctest_modules=doctests,
            )
            filter_run.ctx, filter_run.bus = ctx, bus
            before = _test_hashes(workspace)
            spec = AgentRunSpec(
                run_id=run_id,
                arm=arm,
                feature_id=f"TG-{dotted}",
                checkpoint="testgen",
                ticket_text=_ticket(module_rel, options.max_tests),
                layers=harness.names,
                phases=("test",),
                test_phase_turns=options.test_phase_turns or settings.max_turns_per_session,
                model=settings.openai_model,
                reasoning_effort=settings.openai_reasoning_effort,
                max_output_tokens=settings.max_output_tokens,
                service_tier=settings.openai_service_tier,
                run_timeout_s=settings.run_timeout_s,
                cost_limit_usd=settings.max_run_cost_usd,
                workspace=workspace,
                visible_tests_dir=visible,
            )
            run = run_agent(
                spec,
                harness,
                sandbox,
                bus,
                tracker,
                make_tracer(settings, "shipharness-testgen"),
                client,
                RunOptions(
                    wrapup_turns=settings.wrapup_turns,
                    tool_timeout_s=settings.tool_timeout_s,
                    run_timeout_s=settings.run_timeout_s,
                    policy_summary=render_policy(default_policy(settings)),
                    tool_log_dir=run_dir / "tool-logs",
                    diff_path=run_dir / "diff.patch",
                    tags=["testgen"],
                ),
            )
            result.status = run.status
            result.cost_usd = run.cost_usd
            after = _test_hashes(workspace)
            files = sorted(rel for rel, sha in after.items() if before.get(rel) != sha)
            # Tests the verify layer already evaluated (and removed when discarded) count once.
            filter_run.evaluate(collect_candidates(workspace, files))
            result.results = filter_run.results
            result.not_evaluated = filter_run.not_evaluated
            result.kept = kept_tests(result.results)
            result.discarded = discarded(result.results)
            _write_outputs(result.out_dir, workspace, result, files)
        except FilterSetupError as exc:
            result.error = str(exc)
            return result
        finally:
            sandbox.stop()
            # Kept tests and the report are in out_dir; the agent's workspace copy goes.
            shutil.rmtree(workspace.parent, ignore_errors=True)
    if run.status == "completed":
        result.exit_code = 0
    elif run.status.startswith("ABORTED"):
        result.exit_code = 2
    else:
        result.error = run.error or "run failed"
    return result
