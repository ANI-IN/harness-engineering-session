"""`make warm`: prepare the class machine so a class launch pays no start-up cost. No model calls.

Steps, each timed: build the sandbox images only when their source changed (through the existing
`make images` target), start and remove one container per image so its layers are paged in, and
cache the referee baseline of every class task (the canonical demo-1, demo-2 and demo-4 tasks, F4
on the demo-3 stack for the S3 A/B, and the final features F5-F7) and the gate baseline of every
class task whose layer stack has the verify layer.
The caches are the ones a class run reads (`Runtime.ab_deps`), filled by the same code a run uses,
so a second warm-up finds everything in place and does nothing but page the images in again.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import shlex
import shutil
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from shipharness.ab.demo import ABDeps, ABTask, _harness, arm_specs, make_referee, section_layers
from shipharness.ab.referee import Referee
from shipharness.ab.workspace import create_arm_workspace, new_ab_id, new_run_id, resolve_commit
from shipharness.datasets.names import feature_label
from shipharness.events import EventBus
from shipharness.harness.base import Harness, LayerContext

# (section, feature): the tasks class runs use (make show-N, make final with the poll's features).
# S3 is the live A/B `make demo-3 FEATURE=F4`: its referee baseline is the same file as demo-4 F4's
# and the demo-3 stack has no verify layer, so it adds nothing to compute. F3 is left out: no class
# step runs it, and its referee baseline would be one more container run on the class machine.
CLASS_TASKS: tuple[tuple[str, str], ...] = (
    ("demo-1", "F1"),
    ("demo-2", "F2"),
    ("demo-3", "F4"),
    ("demo-4", "F4"),
    ("final", "F5"),
    ("final", "F6"),
    ("final", "F7"),
)
# What the image build context copies (platform/sandbox/Dockerfile); .dockerignore drops caches
# and DBs.
IMAGE_SOURCES = ("platform/sandbox/Dockerfile", "pyproject.toml", "uv.lock")
IMAGE_SOURCE_DIRS = ("platform/src",)
_SKIP_PARTS = {"__pycache__"}
_SKIP_SUFFIXES = {".pyc", ".db"}
IMAGE_STAMP = "images.json"


# -- images ---------------------------------------------------------------------------------------


def image_source_digest(root: Path) -> str:
    """Hash of every file the image build copies: a change means the images are stale."""
    digest = hashlib.sha256()
    files = [root / rel for rel in IMAGE_SOURCES]
    for folder in IMAGE_SOURCE_DIRS:
        files += [
            p
            for p in (root / folder).rglob("*")
            if p.is_file() and not _SKIP_PARTS & set(p.parts) and p.suffix not in _SKIP_SUFFIXES
        ]
    for path in sorted(files):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes() if path.is_file() else b"<absent>")
        digest.update(b"\0")
    return digest.hexdigest()


@dataclass(frozen=True)
class ImagePlan:
    image: str
    build: bool
    reason: str  # why it is (re)built; "up to date" otherwise


def plan_images(
    images: Sequence[str],
    digest: str,
    stamp: Mapping[str, Mapping[str, str]],
    image_id: Callable[[str], str | None],
) -> list[ImagePlan]:
    """Build an image when it is missing, when no warm-up recorded the source it was built from,
    when that source changed, or when another build replaced it since."""
    plans: list[ImagePlan] = []
    for image in images:
        current = image_id(image)
        record = stamp.get(image) or {}
        if current is None:
            plans.append(ImagePlan(image, True, "image missing"))
        elif not record:
            plans.append(ImagePlan(image, True, "no record of its source"))
        elif record.get("source") != digest:
            plans.append(ImagePlan(image, True, "source changed"))
        elif record.get("id") != current:
            plans.append(ImagePlan(image, True, "image replaced"))
        else:
            plans.append(ImagePlan(image, False, "up to date"))
    return plans


def read_stamp(path: Path) -> dict[str, dict[str, str]]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_stamp(
    path: Path, images: Sequence[str], digest: str, image_id: Callable[[str], str | None]
) -> None:
    data = read_stamp(path)
    for image in images:
        current = image_id(image)
        if current:
            data[image] = {"source": digest, "id": current}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


# -- class tasks and baselines -----------------------------------------------------------------


@dataclass(frozen=True)
class ClassTask:
    section: str
    task: ABTask

    @property
    def gate(self) -> bool:
        """The section's harness arm runs the verify layer, so it needs a gate baseline."""
        return "verify" in section_layers(self.section)


def class_tasks(dataset: Path, pairs: Sequence[tuple[str, str]] = CLASS_TASKS) -> list[ClassTask]:
    lines = [json.loads(line) for line in Path(dataset).read_text(encoding="utf-8").splitlines()]
    canonical = {
        line["inputs"]["feature_id"]: line
        for line in lines
        if line and line["inputs"].get("variant", "canonical") == "canonical"
    }
    missing = [feature for _section, feature in pairs if feature not in canonical]
    if missing:
        raise ValueError(f"no canonical task for {', '.join(missing)} in {dataset}")
    return [ClassTask(section, ABTask.from_dataset_line(canonical[f])) for section, f in pairs]


@dataclass
class BaselinePlan:
    kind: Literal["referee", "gate"]
    section: str
    feature: str
    path: Path | None  # the cache file a class run reads
    cached: bool
    referee: Referee | None = None
    harness: Harness | None = None
    ctx: LayerContext | None = None
    scratch: Path | None = None  # removed once the baseline is done
    duplicate: bool = False  # the same cache file as an earlier item: nothing more to compute


def plan_baselines(tasks: Sequence[ClassTask], deps: ABDeps, base: Path) -> list[BaselinePlan]:
    """One referee baseline per class task and one gate baseline per class task with the verify
    layer, each with the cache file a class run looks up and whether it is already there. Builds
    the referee and the harness arm's workspace exactly as an A/B does; starts no container."""
    plans: list[BaselinePlan] = []
    gates: list[BaselinePlan] = []
    seen: set[Path] = set()
    for item in tasks:
        sha = resolve_commit(deps.course_repo, item.task.checkpoint)
        scratch = Path(base) / new_ab_id()
        referee = make_referee(item.task, deps, sha, scratch / "referee")
        path = referee._baseline_cache_path()
        plans.append(
            BaselinePlan(
                "referee",
                item.section,
                item.task.feature_id,
                path,
                bool(path and path.is_file()),
                referee=referee,
                scratch=scratch,
                duplicate=path in seen,
            )
        )
        if path is not None:
            seen.add(path)
        if item.gate:
            gates.append(_gate_plan(item, deps, sha, scratch))
    for gate in gates:
        gate.duplicate = gate.path in seen
        if gate.path is not None:
            seen.add(gate.path)
    return plans + gates


def _gate_plan(item: ClassTask, deps: ABDeps, sha: str | None, scratch: Path) -> BaselinePlan:
    run_id = new_run_id()
    ws = create_arm_workspace(
        scratch.name,
        "harness",
        deps.course_repo,
        sha,
        base=scratch.parent,
        label=item.task.checkpoint,
    )
    spec = arm_specs(
        item.task,
        deps.settings,
        ab_id=scratch.name,
        harness_layers=section_layers(item.section),
        workspaces={"harness": ws},
        run_ids={"harness": run_id},
        run_cost_limit_usd=deps.cost.caps.run,
        profile=deps.profile,
    )["harness"]
    harness = _harness(item.task, spec, deps, spec.layers)
    ctx = LayerContext(
        spec=spec,
        phase=spec.phases[0],
        session_index=0,
        turn=0,
        workspace=ws,
        sandbox=None,  # type: ignore[arg-type]
    )
    verify = next(layer for layer in harness.layers if layer.name == "verify")
    path = verify.cached_baseline_path(ctx)  # type: ignore[attr-defined]
    return BaselinePlan(
        "gate",
        item.section,
        item.task.feature_id,
        path,
        bool(path and path.is_file()),
        harness=harness,
        ctx=ctx,
        scratch=scratch,
    )


@dataclass
class StepReport:
    kind: str
    label: str
    ok: bool
    seconds: float
    detail: str = ""


def _referee_baseline(plan: BaselinePlan) -> tuple[bool, str]:
    assert plan.referee is not None
    baseline = plan.referee.baseline()
    if baseline is None:
        return False, "the referee baseline could not be computed (see the log)"
    return bool(plan.path and plan.path.is_file()), "computed"


def _gate_baseline(plan: BaselinePlan, deps: ABDeps, bus: EventBus) -> tuple[bool, str]:
    """The harness arm's workspace preparation, as at the start of a run (the verify layer
    computes and caches the gate baseline in the arm's container)."""
    assert plan.harness is not None and plan.ctx is not None
    ctx = plan.ctx
    sandbox = deps.sandbox_factory("harness", ctx.workspace, bus, ctx.spec.run_id)
    sandbox.start()
    try:
        ctx.sandbox, ctx.bus = sandbox, bus
        plan.harness.prepare_workspace(ctx)
    finally:
        sandbox.stop()
    if plan.path is not None and plan.path.is_file():
        return True, "computed"
    return False, "the gate baseline could not be computed (see the log)"


def run_baselines(
    plans: Sequence[BaselinePlan], deps: ABDeps, *, jobs: int = 4
) -> list[StepReport]:
    """Compute the missing baselines, `jobs` at a time; cached ones are reported and skipped."""
    reports: list[StepReport] = []
    todo = [p for p in plans if not p.cached and not p.duplicate]
    for plan in plans:
        if plan.cached or plan.duplicate:
            note = "cached" if plan.cached else "same baseline as above"
            reports.append(StepReport(plan.kind, _label(plan), True, 0.0, note))
    base = next((p.scratch.parent for p in plans if p.scratch is not None), None)
    log = (base or Path(".")) / "warm-events.jsonl"
    try:
        with EventBus(log, ab_id=None) as bus:

            def one(plan: BaselinePlan) -> StepReport:
                started = time.monotonic()
                try:
                    if plan.kind == "referee":
                        ok, detail = _referee_baseline(plan)
                    else:
                        ok, detail = _gate_baseline(plan, deps, bus)
                except Exception as exc:  # noqa: BLE001 - reported as one failed step
                    ok, detail = False, f"{type(exc).__name__}: {exc}"[:300]
                return StepReport(plan.kind, _label(plan), ok, time.monotonic() - started, detail)

            with ThreadPoolExecutor(max_workers=max(1, jobs), thread_name_prefix="warm") as pool:
                reports += list(pool.map(one, todo))
    finally:
        discard(plans)
        with contextlib.suppress(OSError):
            log.unlink()
            log.parent.rmdir()
    return reports


def discard(plans: Sequence[BaselinePlan]) -> None:
    """Remove the scratch exports and workspaces the plan made."""
    for scratch in {p.scratch for p in plans if p.scratch is not None}:
        shutil.rmtree(scratch, ignore_errors=True)


def _label(plan: BaselinePlan) -> str:
    """'referee baseline demo-1 (Feature 1: Org-wide issue search)'."""
    return f"{plan.kind} baseline {plan.section} ({feature_label(plan.feature)})"


# -- the whole warm-up ------------------------------------------------------------------------


@dataclass
class WarmHost:
    """Container runtime calls, injectable for tests."""

    runtime: str = "docker"
    run: Callable[..., subprocess.CompletedProcess[str]] = field(default=subprocess.run)

    def image_id(self, image: str) -> str | None:
        out = self.run(
            [self.runtime, "image", "inspect", "--format", "{{.Id}}", image],
            capture_output=True,
            text=True,
            check=False,
        )
        if out.returncode != 0:
            return None
        return out.stdout.strip() or None

    def page_in(self, image: str) -> bool:
        out = self.run(
            [self.runtime, "run", "--rm", "--network", "none", image, "true"],
            capture_output=True,
            text=True,
            check=False,
        )
        return out.returncode == 0

    def build(self, command: str, cwd: Path) -> bool:
        return self.run(command, shell=True, cwd=cwd, check=False).returncode == 0


def timed(fn: Callable[[], Any]) -> tuple[Any, float]:
    started = time.monotonic()
    value = fn()
    return value, time.monotonic() - started


def warm_up(
    *,
    images: Sequence[str],
    digest: str,
    stamp_path: Path,
    host: WarmHost,
    images_command: str,
    repo: Path,
    tasks: Sequence[ClassTask],
    deps: ABDeps,
    base: Path,
    jobs: int,
    echo: Callable[[str], None],
) -> bool:
    """The whole warm-up; one line per step with its timing. False if any step failed."""
    started = time.monotonic()
    ok = True
    plans, seconds = timed(
        lambda: plan_images(images, digest, read_stamp(stamp_path), host.image_id)
    )
    stale = [p for p in plans if p.build]
    if stale:
        why = "; ".join(f"{p.image}: {p.reason}" for p in stale)
        command = images_command + "".join(
            f" {name}={shlex.quote(image)}"
            for name, image in zip(("AGENT_IMAGE", "REFEREE_IMAGE"), images, strict=False)
        )
        built, seconds = timed(lambda: host.build(command, repo))
        if not built:
            echo(f"x images: build failed ({why}) ({seconds:.1f} s)")
            return False
        write_stamp(stamp_path, images, digest, host.image_id)
        echo(f"images: built ({why}) ({seconds:.1f} s)")
    else:
        echo(f"images: up to date, nothing built ({', '.join(images)}) ({seconds:.1f} s)")
    for image in images:
        paged, seconds = timed(lambda image=image: host.page_in(image))
        ok = ok and paged
        echo(f"{'page-in' if paged else 'x page-in failed'} {image} ({seconds:.1f} s)")
    baselines, seconds = timed(lambda: plan_baselines(tasks, deps, base))
    todo = sum(not (b.cached or b.duplicate) for b in baselines)
    echo(f"plan: {todo} baselines to compute ({seconds:.1f} s)")
    for report in run_baselines(baselines, deps, jobs=jobs):
        ok = ok and report.ok
        mark = "" if report.ok else "x "
        echo(f"{mark}{report.label}: {report.detail} ({report.seconds:.1f} s)")
    echo(f"warm: {'done' if ok else 'incomplete'} ({time.monotonic() - started:.1f} s)")
    return ok
