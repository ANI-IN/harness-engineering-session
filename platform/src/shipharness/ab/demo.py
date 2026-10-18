"""One A/B: the same task run by the bare arm and the harness arm in parallel, then judged by the
same referee. Used by `shipharness ab`, `make demo-N`, and the experiments.

Integrity rules implemented here: both specs come from one set of values (model, effort, ticket,
checkpoint, budgets, cost cap, tools, sandbox policy); the only differences are the arm label, run
id, layers, and workspace path. The arms run concurrently. Every run, aborted or not, is judged.
"""

from __future__ import annotations

import dataclasses
import json
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, get_args

import structlog

from shipharness.ab.mutants import referee_mutants
from shipharness.ab.referee import (
    Referee,
    RefereeDeps,
    RefereeTask,
    Reviewer,
    SandboxFactory,
)
from shipharness.ab.score import ScoreRecord
from shipharness.ab.workspace import (
    create_arm_workspace,
    new_ab_id,
    new_run_id,
    resolve_commit,
)
from shipharness.config import Settings
from shipharness.cost import CostTracker
from shipharness.events import Arm, EventBus
from shipharness.harness.base import LAYER_ORDER, Harness, parse_layers
from shipharness.harness.decisions import LayerName
from shipharness.harness.verify.layer import default_seed
from shipharness.log_setup import redact
from shipharness.runner import git
from shipharness.runner.loop import RunOptions, run_agent
from shipharness.runner.model import ModelClient
from shipharness.runner.models import AgentRunResult, AgentRunSpec
from shipharness.sandbox.base import Sandbox
from shipharness.tracing import NullTracer, Tracer, write_export

ARMS: tuple[Arm, ...] = get_args(Arm)
SECTION_STACKS: dict[str, tuple[LayerName, ...]] = {
    "demo-1": ("instructions",),
    "demo-2": ("instructions", "state"),
    "demo-3": ("instructions", "state", "scope"),
    "demo-4": LAYER_ORDER,
    "final": LAYER_ORDER,
}


# Section demos judged by a measure other than the dataset line's own (owner, 2026-10-18): Section
# 3's class demo on Feature 4 uses the measure pre-registered for the Section 3 confirmation
# (docs/evidence/s3.md), files changed outside the allowed paths; Feature 4's own measure (every
# hidden test and every referee mutant) stays the dataset's for Section 4, show-4, and the final.
SECTION_MEASURES: dict[tuple[str, str], str] = {("demo-3", "F4"): "out_of_scope_files>=1"}


def section_measure(section: str | None, feature_id: str) -> str | None:
    """The section demo's own primary measure for this feature, or None (the dataset's applies)."""
    return SECTION_MEASURES.get((section or "", feature_id))


def section_task(task: ABTask, section: str | None) -> ABTask:
    """The task as the section demo judges it: its primary measure replaced where the section
    pre-registered its own (SECTION_MEASURES); otherwise unchanged."""
    measure = section_measure(section, task.feature_id)
    return dataclasses.replace(task, primary_measure=measure) if measure else task


def section_layers(section: str, modifier: str | None = None) -> frozenset[LayerName]:
    """The harness arm's layers for a section demo; `-<layer>` removes one."""
    stack = set(SECTION_STACKS[section])
    if modifier:
        removed = parse_layers(modifier if modifier.startswith("-") else f"-{modifier}")
        stack -= set(LAYER_ORDER) - set(removed)
    return frozenset(stack)


@dataclass
class ABTask:
    feature_id: str
    checkpoint: str
    ticket_text: str
    variant: str = "canonical"
    session_budget: list[int] = field(default_factory=lambda: [30])
    test_phase_turns: int = 12
    hidden_test_ids: list[str] = field(default_factory=list)
    allowed_paths: dict[str, list[str]] = field(default_factory=dict)
    mutant_set: str = ""
    primary_measure: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dataset_line(cls, line: Mapping[str, Any]) -> ABTask:
        inputs, outputs = line["inputs"], line.get("outputs", {})
        metadata = dict(line.get("metadata", {}))
        return cls(
            feature_id=inputs["feature_id"],
            checkpoint=inputs["checkpoint"],
            ticket_text=inputs["ticket_text"],
            variant=inputs.get("variant", "canonical"),
            session_budget=list(inputs.get("session_budget", [30])),
            test_phase_turns=int(metadata.get("test_phase_turns", 12)),
            hidden_test_ids=list(outputs.get("hidden_test_ids", [])),
            allowed_paths={k: list(v) for k, v in outputs.get("allowed_paths", {}).items()},
            mutant_set=outputs.get("mutant_set", ""),
            primary_measure=outputs.get("primary_measure", ""),
            metadata=metadata,
        )

    def harness_kwargs(self) -> dict[str, Any]:
        """Feature data the state and scope layers accept (Harness.from_names kwargs)."""
        return {
            "feature_category": self.metadata.get("category", "feature"),
            "feature_description": self.metadata.get("description", self.ticket_text[:200]),
            # None (no steps in the dataset line) lets the layers take the ticket's bullet lines or
            # its title; an empty list would give a feature list and exec plan with no steps.
            "feature_steps": list(steps) if (steps := self.metadata.get("steps")) else None,
        }

    def referee_task(self) -> RefereeTask:
        return RefereeTask(
            feature_id=self.feature_id,
            checkpoint=self.checkpoint,
            ticket_text=self.ticket_text,
            variant=self.variant,
            hidden_test_ids=self.hidden_test_ids,
            allowed_paths=self.allowed_paths,
            primary_measure=self.primary_measure,
            mutant_set=self.mutant_set,
        )


ClientFactory = Callable[[Arm], ModelClient]
ArmSandboxFactory = Callable[[Arm, Path, EventBus, str], Sandbox]


@dataclass
class ABDeps:
    settings: Settings
    course_repo: Path
    checkpoint_ref: str | None
    client_factory: ClientFactory
    sandbox_factory: ArmSandboxFactory
    referee_sandbox_factory: SandboxFactory
    cost: CostTracker
    tracer: Tracer = field(default_factory=NullTracer)
    reviewer: Reviewer | None = None
    grading_criteria: str = ""
    workspace_base: Path | None = None
    layer_registry: Mapping[str, type] | None = None
    harness_kwargs: dict[str, Any] = field(default_factory=dict)
    mutants: list[Any] = field(default_factory=list)
    seed: int | None = None
    sandboxed: bool = True
    container_paths: bool = True
    policy_summary: str = ""
    tags: list[str] = field(default_factory=list)
    # Board preview per arm (console screen 2): called with (arm, bus, arm spec); the object
    # needs start_server(), run(stop_event), and close() (stops its container at once).
    preview_factory: Callable[[Arm, EventBus, AgentRunSpec], Any] | None = None
    mutant_runner: Any = None  # referee mutant runner; None = the filters package runner
    mutant_source_repo: Path | None = None  # where teamtrack/mutants lives (default course_repo)
    baseline_cache_dir: Path | None = None  # referee baselines reused across A/Bs of a task
    profile: str = "standard"  # run profile already applied to `settings` (recorded, displayed)


@dataclass
class ArmRun:
    spec: AgentRunSpec
    result: AgentRunResult
    record: ScoreRecord


@dataclass
class ABResult:
    ab_id: str
    arms: dict[Arm, ArmRun]
    run_dir: Path


def arm_specs(
    task: ABTask,
    settings: Settings,
    *,
    ab_id: str | None,
    harness_layers: frozenset[LayerName],
    workspaces: Mapping[Arm, Path],
    run_ids: Mapping[Arm, str],
    run_cost_limit_usd: float | None = None,
    profile: str = "standard",
    constructed: bool = False,
) -> dict[Arm, AgentRunSpec]:
    """Both arms' specs from one set of values. `run_cost_limit_usd` is the per-arm run cap
    (both phases together); it defaults to MAX_RUN_COST_USD, and the A/B passes the cost
    tracker's run cap, which is MAX_FINAL_RUN_COST_USD for `--section final`. `profile` names the
    run profile already applied to `settings`. With only the harness arm in `workspaces`, the
    spec is marked single-arm; `constructed` marks a constructed example (scripted steps)."""
    if run_cost_limit_usd is None:
        run_cost_limit_usd = settings.max_run_cost_usd
    shared: dict[str, Any] = dict(
        ab_id=ab_id,
        feature_id=task.feature_id,
        checkpoint=task.checkpoint,
        ticket_text=task.ticket_text,
        variant=task.variant,
        phases=("build", "test"),
        session_budget=list(task.session_budget),
        test_phase_turns=task.test_phase_turns,
        allowed_paths=task.allowed_paths,
        model=settings.openai_model,
        reasoning_effort=settings.openai_reasoning_effort,
        max_output_tokens=settings.max_output_tokens,
        service_tier=settings.openai_service_tier,
        run_timeout_s=settings.run_timeout_s,
        profile=profile,
        single_arm=set(workspaces) == {"harness"},
        constructed=constructed,
        cost_limit_usd=run_cost_limit_usd,
    )
    return {
        arm: AgentRunSpec(
            **shared,
            run_id=run_ids[arm],
            arm=arm,
            layers=harness_layers if arm == "harness" else frozenset(),
            workspace=workspaces[arm],
        )
        for arm in workspaces
    }


def _error_result(spec: AgentRunSpec, message: str) -> AgentRunResult:
    return AgentRunResult(
        run_id=spec.run_id,
        arm=spec.arm,
        status="ERROR",
        claim="none",
        claim_summary="",
        sessions=[],
        phase_shas={},
        diff_path=None,
        cost_usd=0.0,
        turns_total=0,
        wall_s=0.0,
        trace_url=None,
        error=message[:300],
    )


def _harness(
    task: ABTask, spec: AgentRunSpec, deps: ABDeps, layers: frozenset[LayerName]
) -> Harness:
    if spec.arm == "bare" or not layers:
        return Harness([])
    kwargs = {**task.harness_kwargs(), **deps.harness_kwargs}
    return Harness.from_names(layers, deps.layer_registry, **kwargs)


# run id -> time.monotonic() when the arm finished; the referee's primary_verdict event reports the
# seconds since then.
_ARM_ENDED: dict[str, float] = {}


def run_arm(
    task: ABTask, spec: AgentRunSpec, deps: ABDeps, bus: EventBus, run_dir: Path
) -> AgentRunResult:
    """One arm, start to finish. Never raises: a failure becomes an ERROR result."""
    s = deps.settings
    options = RunOptions(
        wrapup_turns=s.wrapup_turns,
        tool_timeout_s=s.tool_timeout_s,
        run_timeout_s=s.run_timeout_s,
        harness_timeout_s=s.harness_timeout_s,
        policy_summary=deps.policy_summary,
        tool_log_dir=run_dir / spec.arm / "tool-logs",
        snapshot_dir=run_dir / spec.arm / "snapshots",
        diff_path=run_dir / spec.arm / "diff.patch",
        tags=list(deps.tags),
    )
    try:
        harness = _harness(task, spec, deps, spec.layers)
        sandbox = deps.sandbox_factory(spec.arm, spec.workspace, bus, spec.run_id)
        sandbox.start()
    except Exception as exc:  # noqa: BLE001 - recorded as an ERROR run, still judged
        _ARM_ENDED[spec.run_id] = time.monotonic()
        return _error_result(spec, f"arm setup failed: {type(exc).__name__}: {exc}")
    try:
        client = deps.client_factory(spec.arm)
        return run_agent(spec, harness, sandbox, bus, deps.cost, deps.tracer, client, options)
    finally:
        _ARM_ENDED[spec.run_id] = time.monotonic()
        sandbox.stop()


def _referee_mutants(task: ABTask, deps: ABDeps, checkpoint_sha: str | None) -> list[Any]:
    """From the pinned checkpoint commit (a separate `mutant_source_repo` reads its tree)."""
    if deps.mutant_source_repo is not None:
        return referee_mutants(task.mutant_set, deps.mutant_source_repo, deps.mutants)
    return referee_mutants(task.mutant_set, deps.course_repo, deps.mutants, ref=checkpoint_sha)


def task_seed(task: ABTask, deps: ABDeps) -> int:
    """The referee and gate seed of a task (fixed per feature and checkpoint)."""
    return deps.seed if deps.seed is not None else default_seed(task.feature_id, task.checkpoint)


def make_referee(task: ABTask, deps: ABDeps, checkpoint_sha: str | None, base_dir: Path) -> Referee:
    """The referee of one A/B. `make warm` builds it the same way, so the baseline it caches has
    the key a class run looks up."""
    return Referee(
        task.referee_task(),
        RefereeDeps(
            course_repo=deps.course_repo,
            checkpoint_ref=checkpoint_sha,
            sandbox_factory=deps.referee_sandbox_factory,
            exports_dir=Path(deps.settings.exports_dir),
            base_dir=base_dir,
            seed=task_seed(task, deps),
            tracer=deps.tracer,
            reviewer=deps.reviewer,
            grading_criteria=deps.grading_criteria,
            mutants=_referee_mutants(task, deps, checkpoint_sha),
            mutant_runner=deps.mutant_runner,
            baseline_cache_dir=deps.baseline_cache_dir,
            sandboxed=deps.sandboxed,
            container_paths=deps.container_paths,
        ),
    )


# Seconds run_ab waits for each preview loop to end before it stops the preview container itself.
PREVIEW_JOIN_S = 10.0


@dataclass
class _RunningPreview:
    thread: threading.Thread
    preview: Any

    def join_or_stop(self, timeout_s: float) -> None:
        """Wait for the preview loop to end. A capture still running after `timeout_s` (the F4
        conflict capture can take longer) has its container stopped now: the loop runs on a
        daemon thread, and a process that exits first never runs the loop's own stop."""
        self.thread.join(timeout=timeout_s)
        if self.thread.is_alive():
            try:
                self.preview.close()
            except Exception as exc:  # noqa: BLE001 - display only; the run's result stands
                structlog.get_logger(__name__).warning(
                    "board preview container not stopped", reason=f"{type(exc).__name__}: {exc}"
                )


def _start_previews(
    deps: ABDeps, bus: EventBus, specs: Mapping[Arm, AgentRunSpec]
) -> tuple[threading.Event, list[_RunningPreview]]:
    stop = threading.Event()
    running: list[_RunningPreview] = []
    if deps.preview_factory is None:
        return stop, running
    for arm, spec in specs.items():
        try:
            preview = deps.preview_factory(arm, bus, spec)
            preview.start_server()
        except Exception as exc:  # noqa: BLE001 - the board preview is display only
            structlog.get_logger(__name__).warning(
                "board preview unavailable", arm=arm, reason=f"{type(exc).__name__}: {exc}"[:300]
            )
            continue
        thread = threading.Thread(target=preview.run, args=(stop,), daemon=True)
        thread.start()
        running.append(_RunningPreview(thread, preview))
    return stop, running


@contextmanager
def _joined(thread: threading.Thread) -> Iterator[None]:
    """Join `thread` when the block exits, also when it raises."""
    try:
        yield
    finally:
        thread.join()


def run_ab(
    task: ABTask,
    harness_layers: frozenset[LayerName],
    deps: ABDeps,
    *,
    ab_id: str | None = None,
    section: str | None = None,
    arms: tuple[Arm, ...] = ARMS,
    constructed: bool = False,
) -> ABResult:
    """Both arms (default), or the harness arm alone (`arms=("harness",)`: "harness in action",
    judged the same way and marked single-arm, never compared with a bare run). `constructed`:
    a constructed example (`shipharness.examples`, scripted steps), harness arm alone, marked as
    such and never exported where real runs are counted."""
    if tuple(arms) not in (ARMS, ("harness",)):
        raise ValueError(f"arms must be both arms or the harness arm alone, got {arms!r}")
    if constructed and tuple(arms) != ("harness",):
        raise ValueError("a constructed example runs the harness arm alone, never an A/B")
    arms = tuple(arms)
    task = section_task(task, section)
    ab_id = ab_id or new_ab_id()
    run_dir = Path(deps.settings.runs_dir) / ab_id
    write_start_record(run_dir, ab_id, task, section, arms, constructed)
    run_ids = {arm: new_run_id() for arm in arms}
    # The checkpoint is pinned to the commit its tag names now: both arms, the referee, and later
    # swap tests and replays export that commit, even if the tag moves afterwards.
    checkpoint_sha = (
        resolve_commit(deps.course_repo, deps.checkpoint_ref) if deps.checkpoint_ref else None
    )
    workspaces = {
        arm: create_arm_workspace(
            ab_id,
            arm,
            deps.course_repo,
            checkpoint_sha,
            base=deps.workspace_base,
            label=deps.checkpoint_ref,
        )
        for arm in arms
    }
    specs = arm_specs(
        task,
        deps.settings,
        ab_id=ab_id,
        harness_layers=harness_layers,
        workspaces=workspaces,
        run_ids=run_ids,
        run_cost_limit_usd=deps.cost.caps.run,  # final section: MAX_FINAL_RUN_COST_USD
        profile=deps.profile,
        constructed=constructed,
    )
    seed = task_seed(task, deps)
    referee = make_referee(
        task, deps, checkpoint_sha, workspaces[arms[0]].parent.parent / "referee"
    )
    # The baseline depends only on the checkpoint, so it runs while the arms work.
    baseline = threading.Thread(target=referee.baseline, name="referee-baseline", daemon=True)
    baseline.start()
    # The baseline's referee container is stopped before run_ab returns or raises.
    with EventBus(run_dir / "events.jsonl", ab_id=ab_id) as bus, _joined(baseline):
        stop, previews = _start_previews(deps, bus, specs)

        # [walkthrough:Opening:two_arms] start
        # Same task, same model, effort, budgets, cost cap, tools, and sandbox for both arms.
        # The only difference is the harness. Both arms run at the same time.
        # Both arms are judged by the same referee on what they shipped (aborted runs too),
        # each as soon as it finishes: no idle wait for the other arm.
        def run_and_judge(arm: Arm) -> tuple[AgentRunResult, ScoreRecord]:
            result = run_arm(task, specs[arm], deps, bus, run_dir)
            baseline.join()
            referee.baseline()  # computed by the thread (or now, if the thread failed)
            return result, _judge(referee, specs[arm], result, bus, run_dir)

        try:
            with ThreadPoolExecutor(max_workers=2, thread_name_prefix="arm") as pool:
                futures = {arm: pool.submit(run_and_judge, arm) for arm in arms}
                done = {arm: future.result() for arm, future in futures.items()}
        finally:
            stop.set()  # previews stop (and their containers with them) on every path
            for preview in previews:
                preview.join_or_stop(PREVIEW_JOIN_S)
        results = {arm: done[arm][0] for arm in arms}
        records = {arm: done[arm][1] for arm in arms}
        # [walkthrough:Opening:two_arms] end
    runs = {arm: ArmRun(specs[arm], results[arm], records[arm]) for arm in arms}
    write_ab_record(
        run_dir,
        task,
        seed,
        runs,
        section=section,
        checkpoint_sha=checkpoint_sha,
        from_working_tree=deps.checkpoint_ref is None,
        profile=deps.profile,
        constructed=constructed,
    )
    return ABResult(ab_id=ab_id, arms=runs, run_dir=run_dir)


AB_RECORD = "ab.json"
SINGLE_ARM_MODE = "harness in action"
CONSTRUCTED_MODE = "constructed example"
CONSTRUCTED_SCORE = "score.json"  # <run dir>/harness/score.json: a constructed run's ScoreRecord


START_RECORD = "start.json"


def write_start_record(
    run_dir: Path,
    ab_id: str,
    task: ABTask,
    section: str | None,
    arms: tuple[Arm, ...],
    constructed: bool,
) -> Path:
    """What the run is, written before any arm starts: the console's run list reads it while the
    run goes on (ab.json, the full record, is written when both arms are judged)."""
    single_arm = set(arms) == {"harness"}
    mode = CONSTRUCTED_MODE if constructed else SINGLE_ARM_MODE if single_arm else "A/B"
    data = {
        "ab_id": ab_id,
        "section": section,
        "mode": mode,
        "feature_id": task.feature_id,
        "single_arm": single_arm,
        "constructed": constructed,
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / START_RECORD
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def write_ab_record(
    run_dir: Path,
    task: ABTask,
    seed: int,
    arms: Mapping[Arm, ArmRun],
    *,
    section: str | None = None,
    checkpoint_sha: str | None = None,
    from_working_tree: bool = False,
    profile: str = "standard",
    constructed: bool = False,
) -> Path:
    """Everything swap and replay need, without host paths or keys. `section` (demo-N or final)
    lets `make swap-N` find the section's most recent A/B. `checkpoint_sha` is the commit the
    arms started from (swap and replay export it, never the tag); a working-tree A/B records
    null and `from_working_tree: true`. `profile` is the run profile; `single_arm` (harness arm
    alone, mode "harness in action") keeps the record out of swap tests and comparisons;
    `constructed` (mode "constructed example") marks scripted steps instead of a model."""
    single_arm = set(arms) == {"harness"}
    mode = CONSTRUCTED_MODE if constructed else SINGLE_ARM_MODE if single_arm else "A/B"
    data = {
        "task": asdict(task),
        "seed": seed,
        "section": section,
        "checkpoint_sha": checkpoint_sha,
        "from_working_tree": from_working_tree,
        "profile": profile,
        "single_arm": single_arm,
        "constructed": constructed,
        "mode": mode,
        "arms": {
            arm: {
                "spec": run.spec.public_dict(),
                "result": run.result.model_dump(mode="json", exclude={"diff_path"}),
                "diff": f"{arm}/diff.patch",
                "test_phase_files": phase_changed_files(
                    run.spec, run.result, store=snapshot_store(run_dir, arm)
                ),
                "session_patches": [
                    p.relative_to(run_dir).as_posix()
                    for p in sorted(
                        (run_dir / arm / "sessions").glob("session-*.patch"),
                        key=lambda p: int(p.stem.rsplit("-", 1)[-1]),
                    )
                ],
            }
            for arm, run in arms.items()
        },
    }
    path = run_dir / AB_RECORD
    path.write_text(json.dumps(redact(data), indent=2, sort_keys=True), encoding="utf-8")
    return path


def phase_changed_files(
    spec: AgentRunSpec, result: AgentRunResult, *, store: Path | None = None
) -> list[str]:
    """Files the arm changed during the test phase (the S3 measure's second half). With
    working-tree snapshots (`store`): the change from the first test session's start tree to the
    last test session's end tree, so build-phase work the arm never committed is not counted.
    Without them: the working tree against the commit at the start of the test phase."""
    tests = [s for s in result.sessions if s.phase == "test"]
    if store is not None and tests and all(s.start_tree and s.end_tree for s in tests):
        return git.tree_changed_files(store, tests[0].start_tree, tests[-1].end_tree)
    shas = result.phase_shas.get("test")
    return git.changed_files(spec.workspace, shas[0]) if shas else []


def _judge(
    referee: Referee, spec: AgentRunSpec, result: AgentRunResult, bus: EventBus, run_dir: Path
) -> ScoreRecord:
    diff = result.diff_path.read_bytes() if result.diff_path and result.diff_path.exists() else b""
    verdict = referee.judge(
        run_id=spec.run_id,
        ab_id=spec.ab_id,
        arm=spec.arm,
        layers=sorted(spec.layers),
        result=result,
        diff=diff,
        bus=bus,
        run_log=run_dir / "events.jsonl",
        test_phase_files=phase_changed_files(spec, result, store=snapshot_store(run_dir, spec.arm)),
        session_patches=session_patches(
            spec, result, run_dir / spec.arm / "sessions", store=snapshot_store(run_dir, spec.arm)
        ),
        arm_ended=_ARM_ENDED.pop(spec.run_id, None),
        export=not spec.single_arm,
    )
    if spec.constructed:
        return keep_constructed(verdict.record, run_dir / spec.arm)
    if not spec.single_arm:
        return verdict.record
    return export_single_arm(verdict.record, referee.deps.exports_dir)


def export_single_arm(record: ScoreRecord, exports_dir: Path) -> ScoreRecord:
    """Write a single-arm run's score marked as such (it is never written unmarked, so no report
    ever counts it in a bare-vs-harness comparison)."""
    marked = record.model_copy(update={"single_arm": True})
    write_export("scores", marked.run_id, marked, exports_dir)
    return marked


def keep_constructed(record: ScoreRecord, arm_dir: Path) -> ScoreRecord:
    """A constructed example's score, marked, kept in its run directory only: it never enters
    `exports/`, which the A/B report, screen 4, and the experiments read."""
    marked = record.model_copy(update={"single_arm": True, "constructed": True})
    arm_dir.mkdir(parents=True, exist_ok=True)
    (arm_dir / CONSTRUCTED_SCORE).write_text(marked.model_dump_json(indent=2), encoding="utf-8")
    return marked


def snapshot_store(run_dir: Path, arm: str) -> Path:
    """Where an arm's session snapshots live (outside the workspace; RunOptions.snapshot_dir)."""
    return run_dir / arm / "snapshots" / "store.git"


def session_patches(
    spec: AgentRunSpec, result: AgentRunResult, out_dir: Path, *, store: Path | None = None
) -> list[Path]:
    """One patch per session (for the continuity check). With working-tree snapshots (`store`),
    each patch is the change between the session's start and end trees, so an arm that never
    commits is measured like one that does. Without them: committed changes between the session's
    start and end commits, and the last session also includes uncommitted work."""
    patches: list[Path] = []
    sessions = list(result.sessions)
    if store is not None and sessions and all(s.start_tree and s.end_tree for s in sessions):
        for session in sessions:
            out = out_dir / f"session-{session.index}.patch"
            written = git.write_tree_diff(store, session.start_tree, session.end_tree, out)
            if written is not None:
                patches.append(written)
        return patches
    for position, session in enumerate(result.sessions):
        out = out_dir / f"session-{session.index}.patch"
        if position == len(result.sessions) - 1:
            written = git.write_diff(spec.workspace, session.start_sha, out)
        else:
            written = git.write_range_diff(spec.workspace, session.start_sha, session.end_sha, out)
        if written is not None:
            patches.append(written)
    return patches
