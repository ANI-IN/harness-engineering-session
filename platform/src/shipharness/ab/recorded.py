"""Swap test and replay: both work from a finished A/B's run directory, with no model calls.

Swap test: each arm's shipped diff is judged again under the other arm's label. The referee never
looks at the label, so every judged measure must come out identical; the class sees that the
result belongs to the code, not the arm.

Replay: the recorded events are re-emitted with `recorded=True` (RECORDING badge in the console),
the recorded diffs are applied to a fresh checkpoint export, and the referee runs live.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shipharness.ab.demo import AB_RECORD, ARMS, ABTask, export_single_arm, keep_constructed
from shipharness.ab.mutants import referee_mutants
from shipharness.ab.referee import Referee, RefereeDeps, Reviewer, SandboxFactory
from shipharness.ab.score import ScoreRecord
from shipharness.ab.workspace import new_ab_id
from shipharness.events import Arm, EventBus, replay
from shipharness.runner.models import AgentRunResult
from shipharness.tracing import NullTracer, Tracer

JUDGED_FIELDS: tuple[str, ...] = (
    "r1_new_violations",
    "r1_leaks",
    "r2_new_violations",
    "r3_new_failures",
    "r4_duplicates",
    "r5_audit_missing",
    "r6_ok",
    "r7_ok",
    "regression_passed",
    "regression_total",
    "hidden_passed",
    "hidden_total",
    "mutants_killed",
    "mutants_total",
    "shipped_tests",
    "flaky_tests",
    "out_of_scope_files",
    "test_phase_source_edits",
    "continuity_failure",
    "board_ok",
    "primary",
    "passed_primary",
)


class SingleArmRecord(ValueError):
    """The record is a single-arm run (`ab --arms harness`) or a constructed example
    (`shipharness example`): there is no other arm to swap with."""


class UnpinnedRecord(ValueError):
    """The A/B record has no `checkpoint_sha`: it predates SHA pinning, so the tree its arms
    started from cannot be recovered with certainty (the tag may have moved since)."""


@dataclass
class RecordedDeps:
    """Swap and replay export the checkpoint from the A/B record's `checkpoint_sha`, never from a
    tag name."""

    course_repo: Path
    referee_sandbox_factory: SandboxFactory
    runs_dir: Path
    exports_dir: Path
    tracer: Tracer = field(default_factory=NullTracer)
    reviewer: Reviewer | None = None
    grading_criteria: str = ""
    mutants: list[Any] = field(default_factory=list)
    sandboxed: bool = True
    container_paths: bool = True


@dataclass
class LoadedArm:
    spec: dict[str, Any]
    result: AgentRunResult
    diff: bytes
    test_phase_files: list[str]
    session_patches: list[Path] = field(default_factory=list)


@dataclass
class LoadedAB:
    ab_id: str
    run_dir: Path
    task: ABTask
    seed: int
    arms: dict[Arm, LoadedArm]
    checkpoint_sha: str | None = None
    from_working_tree: bool = False
    pinned: bool = False  # False: the record predates checkpoint_sha
    single_arm: bool = False  # the harness arm alone ("harness in action")
    constructed: bool = False  # a constructed example (scripted steps, no model)

    def export_ref(self) -> str | None:
        """What swap and replay export: the recorded commit (None = the working tree, for an
        A/B that ran from it). Refuses a record without a pinned commit."""
        if self.from_working_tree:
            return None
        if not self.pinned or not self.checkpoint_sha:
            raise UnpinnedRecord(
                f"{self.ab_id} predates checkpoint SHA pinning: its ab.json has no "
                f"checkpoint_sha, and the tag {self.task.checkpoint} may have moved since, so "
                "swap and replay cannot be sure to judge the tree the arms started from; "
                "run the A/B again"
            )
        return self.checkpoint_sha


def load_ab(run_dir: Path) -> LoadedAB:
    data = json.loads((run_dir / AB_RECORD).read_text(encoding="utf-8"))
    arms: dict[Arm, LoadedArm] = {}
    for arm, entry in data["arms"].items():
        diff_file = run_dir / entry["diff"]
        arms[arm] = LoadedArm(
            spec=entry["spec"],
            result=AgentRunResult.model_validate({**entry["result"], "diff_path": None}),
            diff=diff_file.read_bytes() if diff_file.is_file() else b"",
            test_phase_files=list(entry.get("test_phase_files", [])),
            session_patches=[run_dir / p for p in entry.get("session_patches", [])],
        )
    return LoadedAB(
        run_dir.name,
        run_dir,
        ABTask(**data["task"]),
        int(data["seed"]),
        arms,
        checkpoint_sha=data.get("checkpoint_sha"),
        from_working_tree=bool(data.get("from_working_tree", False)),
        pinned="checkpoint_sha" in data,
        single_arm=bool(data.get("single_arm", False)),
        constructed=bool(data.get("constructed", False)),
    )


def latest_ab_dir(runs_dir: Path, section: str | None) -> Path:
    """The most recent recorded A/B (ab ids start with a sortable time stamp), limited to one
    section (demo-N or final) when `section` is given. Single-arm runs (`make show-N`) and
    constructed examples (`make example-N`) are not A/Bs and are skipped."""
    for record in sorted(Path(runs_dir).glob(f"ab-*/{AB_RECORD}"), reverse=True):
        try:
            data = json.loads(record.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if data.get("single_arm") or data.get("constructed"):
            continue
        if section is None or data.get("section") == section:
            return record.parent
    where = f" for section {section}" if section else ""
    raise FileNotFoundError(f"no recorded A/B{where} under {runs_dir}")


def find_run_dir(runs_dir: Path, run_or_ab_id: str, *, section: str | None = None) -> Path:
    """The A/B directory for an ab id, for one of its run ids, or for `latest` (the most recent
    A/B, of `section` when given)."""
    if run_or_ab_id == "latest":
        return latest_ab_dir(runs_dir, section)
    direct = Path(runs_dir) / run_or_ab_id
    if (direct / AB_RECORD).is_file():
        return direct
    for record in sorted(Path(runs_dir).glob(f"*/{AB_RECORD}")):
        data = json.loads(record.read_text(encoding="utf-8"))
        if any(a["spec"]["run_id"] == run_or_ab_id for a in data["arms"].values()):
            return record.parent
    raise FileNotFoundError(f"no recorded A/B for {run_or_ab_id!r} under {runs_dir}")


def _referee(ab: LoadedAB, deps: RecordedDeps, base: Path, reviewer: Reviewer | None) -> Referee:
    return Referee(
        ab.task.referee_task(),
        RefereeDeps(
            course_repo=deps.course_repo,
            checkpoint_ref=ab.export_ref(),  # the recorded commit, never the tag name
            sandbox_factory=deps.referee_sandbox_factory,
            exports_dir=deps.exports_dir,
            base_dir=base,
            seed=ab.seed,  # the recorded seed: the referee is deterministic for a given build
            tracer=deps.tracer,
            reviewer=reviewer,
            grading_criteria=deps.grading_criteria,
            mutants=referee_mutants(
                ab.task.mutant_set, deps.course_repo, deps.mutants, ref=ab.export_ref()
            ),
            sandboxed=deps.sandboxed,
            container_paths=deps.container_paths,
        ),
    )


@dataclass
class SwapReport:
    ab_id: str
    differences: dict[str, dict[str, tuple[Any, Any]]]  # arm -> field -> (original, swapped)
    swapped: dict[str, ScoreRecord]

    @property
    def identical(self) -> bool:
        return not any(self.differences.values())


def swap_test(run_dir: Path, deps: RecordedDeps) -> SwapReport:
    ab = load_ab(run_dir)
    if ab.constructed:
        raise SingleArmRecord(
            f"{ab.ab_id} is a constructed example (scripted steps, no model): the swap test needs "
            "an A/B; pass the id of an A/B"
        )
    if ab.single_arm:
        raise SingleArmRecord(
            f"{ab.ab_id} is a single-arm run (harness in action): the swap test needs both arms; "
            "pass the id of an A/B"
        )
    referee = _referee(ab, deps, run_dir / "swap" / "referee", reviewer=None)
    other: dict[str, Arm] = {"bare": "harness", "harness": "bare"}
    swapped: dict[str, ScoreRecord] = {}
    differences: dict[str, dict[str, tuple[Any, Any]]] = {}
    with EventBus(run_dir / "swap" / "events.jsonl", ab_id=ab.ab_id) as bus:
        for arm in ARMS:
            loaded = ab.arms[arm]
            verdict = referee.judge(
                run_id=f"{loaded.spec['run_id']}-swap",
                ab_id=ab.ab_id,
                arm=other[arm],
                layers=[],
                result=loaded.result,
                diff=loaded.diff,
                bus=bus,
                run_log=run_dir / "events.jsonl",
                test_phase_files=loaded.test_phase_files,
                session_patches=loaded.session_patches,
                export=False,
                log_run_id=loaded.spec["run_id"],  # the recorded log holds the original ids
            )
            swapped[arm] = verdict.record
            original = json.loads(
                (deps.exports_dir / "scores" / f"{loaded.spec['run_id']}.json").read_text(
                    encoding="utf-8"
                )
            )
            new = verdict.record.model_dump(mode="json")
            differences[arm] = {
                f: (original.get(f), new[f]) for f in JUDGED_FIELDS if original.get(f) != new[f]
            }
    return SwapReport(ab.ab_id, differences, swapped)


@dataclass
class ReplayResult:
    ab_id: str
    source_ab_id: str
    events_replayed: int
    records: dict[str, ScoreRecord]
    run_dir: Path


def replay_ab(run_dir: Path, deps: RecordedDeps, *, ab_id: str | None = None) -> ReplayResult:
    """Re-emit the recorded run with recorded=True and re-judge the recorded diffs live."""
    ab = load_ab(run_dir)
    new_id = ab_id or new_ab_id()
    new_dir = Path(deps.runs_dir) / new_id
    referee = _referee(ab, deps, new_dir / "referee", reviewer=deps.reviewer)
    records: dict[str, ScoreRecord] = {}
    with EventBus(new_dir / "events.jsonl", ab_id=new_id) as bus:
        count = replay(run_dir / "events.jsonl", bus)
        for arm in [a for a in ARMS if a in ab.arms]:  # a single-arm run has the harness only
            loaded = ab.arms[arm]
            (new_dir / arm).mkdir(parents=True, exist_ok=True)
            source_diff = run_dir / arm / "diff.patch"
            if source_diff.is_file():
                shutil.copyfile(source_diff, new_dir / arm / "diff.patch")
            verdict = referee.judge(
                run_id=f"{loaded.spec['run_id']}-replay-{new_id[-6:]}",
                ab_id=new_id,
                arm=arm,
                layers=list(loaded.spec.get("layers", [])),
                result=loaded.result,
                diff=loaded.diff,
                bus=bus,
                run_log=run_dir / "events.jsonl",
                test_phase_files=loaded.test_phase_files,
                session_patches=loaded.session_patches,
                recorded=True,
                log_run_id=loaded.spec["run_id"],  # continuity counts the original run's sessions
                export=not ab.single_arm,
            )
            if ab.constructed:  # a replayed constructed example stays out of exports/ too
                records[arm] = keep_constructed(verdict.record, new_dir / arm)
            elif ab.single_arm:
                records[arm] = export_single_arm(verdict.record, deps.exports_dir)
            else:
                records[arm] = verdict.record
    return ReplayResult(new_id, ab.ab_id, count, records, new_dir)
