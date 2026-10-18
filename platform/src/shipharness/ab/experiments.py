"""Pre-class experiments: LangSmith `evaluate()` once per arm on the same
dataset split with `num_repetitions=k`, the two arms concurrently, and one combined referee
evaluator that returns the 12 scores and writes the full ScoreRecord to `exports/scores/` before
returning. The run summary goes to `exports/experiments/<name>.json`; reports read only exports.
"""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from shipharness.ab.demo import (
    ARMS,
    ABDeps,
    ABTask,
    arm_specs,
    phase_changed_files,
    run_arm,
    snapshot_store,
)
from shipharness.ab.demo import session_patches as write_session_patches
from shipharness.ab.mutants import referee_mutants
from shipharness.ab.referee import Referee, RefereeDeps
from shipharness.ab.score import ScoreRecord, evaluator_scores
from shipharness.ab.workspace import create_arm_workspace, new_run_id
from shipharness.events import Arm, EventBus
from shipharness.harness.decisions import LayerName
from shipharness.harness.verify.layer import default_seed
from shipharness.runner.models import AgentRunResult, AgentRunSpec
from shipharness.tracing import write_export

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


@dataclass
class ExperimentPlan:
    dataset: str
    k: int
    harness_layers: frozenset[LayerName]
    split: str | None = None
    batch: str = "batch-1"
    prefix: str = "shipharness"
    day: str = field(default_factory=lambda: date.today().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)
    max_concurrency: int = 1
    disable_evaluator_tracing: bool = False
    from_working_tree: bool = False  # development only: export the working tree, not the tag

    def experiment_prefix(self, arm: Arm) -> str:
        return f"{self.prefix}-{self.batch}-{arm}-{self.day}"


@dataclass
class _LocalRun:
    spec: AgentRunSpec
    result: AgentRunResult
    run_dir: Path
    test_phase_files: list[str]
    session_patches: list[Path]


def _key(inputs: Mapping[str, Any]) -> str:
    return json.dumps(dict(inputs), sort_keys=True, default=str)


def _example_task(example: Any) -> ABTask:
    return ABTask.from_dataset_line(
        {
            "inputs": dict(example.inputs),
            "outputs": dict(getattr(example, "outputs", None) or {}),
            "metadata": dict(getattr(example, "metadata", None) or {}),
        }
    )


class ArmExperiment:
    """Target and evaluator for one arm's `evaluate()` call."""

    def __init__(self, arm: Arm, plan: ExperimentPlan, deps: ABDeps, examples: list[Any]) -> None:
        self.arm, self.plan, self.deps = arm, plan, deps
        self.examples = {_key(e.inputs): e for e in examples}
        self.runs: dict[str, _LocalRun] = {}
        self.records: list[ScoreRecord] = []
        self._referees: dict[str, Referee] = {}
        self._lock = threading.Lock()

    def _mutants(self, task: ABTask) -> list[Any]:
        """Referee mutants from the example's checkpoint commit (or the working tree)."""
        if self.deps.mutant_source_repo is not None:
            return referee_mutants(task.mutant_set, self.deps.mutant_source_repo, self.deps.mutants)
        return referee_mutants(
            task.mutant_set, self.deps.course_repo, self.deps.mutants, ref=self._ref(task)
        )

    def _ref(self, task: ABTask) -> str | None:
        """Each example names its own checkpoint (a git tag in the course repository)."""
        return None if self.plan.from_working_tree else task.checkpoint

    def target(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Runs the arm on one example. Outputs carry no host paths (they go to LangSmith)."""
        task = _example_task(self.examples[_key(inputs)])
        run_id = new_run_id()
        ws = create_arm_workspace(
            run_id,
            self.arm,
            self.deps.course_repo,
            self._ref(task),
            base=self.deps.workspace_base,
        )
        layers = self.plan.harness_layers if self.arm == "harness" else frozenset()
        spec = arm_specs(
            task,
            self.deps.settings,
            ab_id=None,
            harness_layers=layers,
            workspaces={self.arm: ws},
            run_ids={self.arm: run_id},
        )[self.arm]
        run_dir = Path(self.deps.settings.runs_dir) / run_id
        with EventBus(run_dir / "events.jsonl", ab_id=None) as bus:
            result = run_arm(task, spec, self.deps, bus, run_dir)
        local = _LocalRun(
            spec,
            result,
            run_dir,
            phase_changed_files(spec, result, store=snapshot_store(run_dir, self.arm)),
            write_session_patches(
                spec,
                result,
                run_dir / self.arm / "sessions",
                store=snapshot_store(run_dir, self.arm),
            ),
        )
        with self._lock:
            self.runs[run_id] = local
        return {
            "run_id": run_id,
            "arm": self.arm,
            "status": result.status,
            "claim": result.claim,
            "cost_usd": result.cost_usd,
            "turns_total": result.turns_total,
        }

    def _referee(self, task: ABTask) -> Referee:
        key = f"{task.feature_id}|{task.checkpoint}|{task.variant}"
        with self._lock:
            if key not in self._referees:
                # absolute: RUNS_DIR is relative by default, and the referee runs git and
                # its checks in other working directories
                base = Path(self.deps.workspace_base or self.deps.settings.runs_dir).resolve()
                self._referees[key] = Referee(
                    task.referee_task(),
                    RefereeDeps(
                        course_repo=self.deps.course_repo,
                        checkpoint_ref=self._ref(task),
                        sandbox_factory=self.deps.referee_sandbox_factory,
                        exports_dir=Path(self.deps.settings.exports_dir),
                        base_dir=base
                        / "referee"
                        / self.plan.experiment_prefix(self.arm)
                        / re.sub(r"[^A-Za-z0-9_.-]", "_", key),
                        seed=default_seed(task.feature_id, task.checkpoint),
                        tracer=self.deps.tracer,
                        reviewer=self.deps.reviewer,
                        grading_criteria=self.deps.grading_criteria,
                        mutants=self._mutants(task),
                        mutant_runner=self.deps.mutant_runner,
                        baseline_cache_dir=self.deps.baseline_cache_dir,
                        sandboxed=self.deps.sandboxed,
                        container_paths=self.deps.container_paths,
                    ),
                )
            return self._referees[key]

    def evaluator(self, run: Any, example: Any) -> list[dict[str, Any]]:
        """The combined referee evaluator: about 12 scores, ScoreRecord exported first."""
        outputs = getattr(run, "outputs", None) or {}
        local = self.runs[str(outputs["run_id"])]
        task = _example_task(example)
        diff_path = local.result.diff_path
        diff = diff_path.read_bytes() if diff_path and diff_path.exists() else b""
        with EventBus(local.run_dir / "events.jsonl", ab_id=None) as bus:
            verdict = self._referee(task).judge(
                run_id=local.spec.run_id,
                ab_id=None,
                arm=self.arm,
                layers=sorted(local.spec.layers),
                result=local.result,
                diff=diff,
                bus=bus,
                run_log=local.run_dir / "events.jsonl",
                test_phase_files=local.test_phase_files,
                session_patches=local.session_patches,
            )  # judge() writes exports/scores/<run_id>.json before we return
        with self._lock:
            self.records.append(verdict.record)
        return evaluator_scores(verdict.record)


def _stats(records: list[ScoreRecord]) -> dict[str, Any]:
    n = len(records)
    return {
        "runs": n,
        "passed_primary": f"{sum(r.passed_primary for r in records)}/{n}",
        "aborted": sum(1 for r in records if r.status.startswith("ABORTED")),
        "errors": sum(1 for r in records if r.status == "ERROR"),
        "cost_usd": round(sum(r.cost_usd + r.review_cost_usd for r in records), 6),
    }


def run_experiments(
    plan: ExperimentPlan,
    deps: ABDeps,
    client: Any,
    *,
    evaluate_fn: Callable[..., Any] | None = None,
) -> dict[Arm, dict[str, Any]]:
    """Both arms' experiments, concurrently. Returns the export written per arm."""
    if evaluate_fn is None:
        from langsmith import evaluate as evaluate_fn
    kwargs: dict[str, Any] = {"dataset_name": plan.dataset}
    if plan.split:
        kwargs["splits"] = [plan.split]
    examples = list(client.list_examples(**kwargs))
    experiments = {arm: ArmExperiment(arm, plan, deps, examples) for arm in ARMS}

    def one(arm: Arm) -> dict[str, Any]:
        exp = experiments[arm]
        metadata = {
            **plan.metadata,
            "arm": arm,
            "layers": sorted(plan.harness_layers) if arm == "harness" else [],
            "model": deps.settings.openai_model,
            "effort": deps.settings.openai_reasoning_effort,
            "service_tier": deps.settings.openai_service_tier,
            "batch": plan.batch,
            "k": plan.k,
        }
        results = evaluate_fn(
            exp.target,
            data=examples,
            evaluators=[exp.evaluator],
            experiment_prefix=plan.experiment_prefix(arm),
            num_repetitions=plan.k,
            metadata=metadata,
            max_concurrency=plan.max_concurrency,
            client=client,
            disable_evaluator_tracing=plan.disable_evaluator_tracing,
        )
        list(results)  # drain: every row is evaluated before the export is written
        name = str(getattr(results, "experiment_name", plan.experiment_prefix(arm)))
        export = {
            "name": name,
            "url": getattr(results, "url", None),
            "comparison_url": getattr(results, "comparison_url", None),
            "dataset": plan.dataset,
            "split": plan.split,
            "arm": arm,
            "k": plan.k,
            "metadata": metadata,
            "rows": sorted(r.run_id for r in exp.records),
            # checkpoint name -> commit SHA each example was judged at (None: working tree)
            "checkpoint_shas": {r.checkpoint: r.checkpoint_sha for r in exp.records},
            "stats": _stats(exp.records),
        }
        write_export("experiments", name, export, Path(deps.settings.exports_dir))
        return export

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="experiment") as pool:
        futures = {arm: pool.submit(one, arm) for arm in ARMS}
        return {arm: future.result() for arm, future in futures.items()}


def attach_scores(client: Any, trace_url: str | None, record: ScoreRecord) -> int:
    """Attach the 12 scores to an agent trace as feedback without upgrading its retention
    (experiment runs are already extended; direct feedback must not extend)."""
    match = _UUID.search(trace_url or "")
    if match is None:
        return 0
    for score in evaluator_scores(record):
        value = score["score"]
        client.create_feedback(
            run_id=match.group(0),
            key=score["key"],
            score=float(value) if isinstance(value, bool | int | float) else None,
            extend_trace_retention=False,
        )
    return len(evaluator_scores(record))
