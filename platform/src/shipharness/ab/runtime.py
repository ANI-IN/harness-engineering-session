"""Production wiring for the commands: cost tracker, tracer, model clients, sandboxes, reviewer.
Kept in one place so the commands stay thin and tests can swap the whole runtime for fakes."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shipharness.ab.clients import make_openai_client
from shipharness.ab.demo import ABDeps
from shipharness.ab.referee import Reviewer
from shipharness.config import Prices, Settings
from shipharness.config.prices import REPO_ROOT
from shipharness.config.profiles import apply_profile
from shipharness.console.preview import BoardPreview
from shipharness.cost import Caps, CostTracker
from shipharness.events import Arm, EventBus
from shipharness.reviewer import ReviewInput, ReviewOutcome, grading_criteria, run_review
from shipharness.runner.model import ModelClient, OpenAIModelClient
from shipharness.runner.models import AgentRunSpec
from shipharness.sandbox import DockerSandbox, LocalSandbox, default_policy, render_policy
from shipharness.sandbox.base import Sandbox
from shipharness.sandbox.policy import Mount
from shipharness.tracing import Tracer, make_tracer

LEDGER = Path(".shipharness") / "ledger.jsonl"


class PreviewHandle:
    """Runs a BoardPreview until stopped, optionally captures the two-tab conflict view (S4),
    then stops its container."""

    def __init__(self, preview: BoardPreview, sandbox: Sandbox, *, capture_conflict: bool) -> None:
        self.preview = preview
        self.sandbox = sandbox
        self.capture_conflict = capture_conflict

    def start_server(self) -> None:
        try:
            self.preview.start_server()
        except BaseException:
            self.sandbox.stop()  # run() never happens, so nothing else would stop the container
            raise

    def run(self, stop: threading.Event) -> int:
        try:
            frames = self.preview.run(stop)
            if self.capture_conflict:
                self.preview.capture("conflict")
            return frames
        finally:
            self.sandbox.stop()

    def close(self) -> None:
        """Stop the container now, also while `run()` is still capturing (the capture then fails
        and `run()` returns). Safe to call more than once."""
        self.sandbox.stop()


@dataclass
class Runtime:
    settings: Settings
    cost: CostTracker
    tracer: Tracer
    client_factory: Callable[[Arm], ModelClient]
    sandbox_factory: Callable[[Arm, Path, EventBus, str], Sandbox]
    referee_sandbox_factory: Callable[[Path, list[Mount], Arm], Sandbox]
    reviewer: Reviewer | None
    sandboxed: bool
    policy_summary: str
    course_repo: Path = REPO_ROOT
    preview_factory: Callable[[Arm, EventBus, AgentRunSpec], Any] | None = None
    profile: str = "standard"  # run profile already applied to `settings` (config/profiles.py)

    def ab_deps(self, checkpoint_ref: str | None, *, reviewer: bool = True, **kw: Any) -> ABDeps:
        return ABDeps(
            settings=self.settings,
            course_repo=self.course_repo,
            checkpoint_ref=checkpoint_ref,
            client_factory=self.client_factory,
            sandbox_factory=self.sandbox_factory,
            referee_sandbox_factory=self.referee_sandbox_factory,
            cost=self.cost,
            tracer=self.tracer,
            reviewer=self.reviewer if reviewer else None,
            grading_criteria=grading_criteria(),
            sandboxed=self.sandboxed,
            container_paths=self.sandboxed,
            policy_summary=self.policy_summary,
            profile=kw.pop("profile", self.profile),
            preview_factory=kw.pop("preview_factory", self.preview_factory),
            baseline_cache_dir=kw.pop(
                "baseline_cache_dir",
                Path(self.settings.runs_dir).parent / "cache" / "referee-baseline",
            ),
            harness_kwargs={
                "gate_baseline_cache_dir": Path(self.settings.runs_dir).parent
                / "cache"
                / "gate-baseline",
                **kw.pop("harness_kwargs", {}),
            },
            **kw,
        )


def build_runtime(
    settings: Settings,
    *,
    project: str,
    experiment: bool = False,
    final: bool = False,
    session_id: str | None = None,
    profile: str = "standard",
) -> Runtime:
    """`profile` overrides settings for both arms alike (config/profiles.py); the reviewer keeps
    its own model, effort, and the standard tier."""
    settings = apply_profile(settings, profile)
    prices = Prices.load(settings.prices_file)
    # Startup error, before any call: a tier the prices file cannot price (OPENAI_SERVICE_TIER=fast
    # for a model without Fast rates).
    prices.check_tier(settings.openai_model, settings.openai_service_tier)
    cost = CostTracker(
        prices,
        Caps.from_settings(settings, final=final),
        LEDGER,
        session_id=session_id if session_id is not None else settings.shipharness_class_date,
        experiment=experiment,
    )
    tracer = make_tracer(settings, project)
    policy = default_policy(settings)
    sandboxed = settings.sandbox_mode == "docker"
    shared: dict[str, Any] = {}

    def openai() -> Any:
        if "client" not in shared:  # one client, wrapped once, shared by both arms
            shared["client"] = tracer.wrap_openai(make_openai_client(settings))
        return shared["client"]

    def client_factory(_arm: Arm) -> ModelClient:
        return OpenAIModelClient(openai())

    def sandbox_factory(arm: Arm, ws: Path, bus: EventBus, run_id: str) -> Sandbox:
        if sandboxed:
            return DockerSandbox(
                policy,
                settings.sandbox_image_agent,
                ws,
                bus,
                run_id,
                arm,
                runtime=settings.sandbox_runtime,
            )
        return LocalSandbox(policy, ws, bus, run_id, arm)

    def referee_sandbox_factory(build: Path, mounts: list[Mount], arm: Arm) -> Sandbox:
        if sandboxed:
            return DockerSandbox(
                policy,
                settings.sandbox_image_referee,
                build,
                None,
                f"referee-{arm}",
                arm,
                runtime=settings.sandbox_runtime,
                extra_mounts=mounts,
                name_prefix="referee",
            )
        return LocalSandbox(policy, build, None, f"referee-{arm}", arm)

    def preview_factory(arm: Arm, bus: EventBus, spec: AgentRunSpec) -> PreviewHandle:
        """Board preview container for one arm: referee image (has Chromium), network none,
        the arm's workspace mounted, screenshots written to the run directory."""
        sandbox = DockerSandbox(
            policy.model_copy(update={"workspace_read_only": True}),  # never changes the diff
            settings.sandbox_image_referee,
            spec.workspace,
            None,
            f"preview-{arm}",
            arm,
            runtime=settings.sandbox_runtime,
        )
        sandbox.start()
        try:
            preview = BoardPreview(
                sandbox, bus, Path(bus.log_path).parent, run_id=spec.run_id, arm=arm
            )
        except BaseException:
            sandbox.stop()
            raise
        return PreviewHandle(preview, sandbox, capture_conflict=spec.feature_id == "F4")

    def reviewer(inp: ReviewInput) -> ReviewOutcome:
        return run_review(
            inp,
            cost,
            tracer,
            client=openai(),
            model=settings.openai_eval_model,
            effort=settings.openai_eval_reasoning_effort,
        )

    return Runtime(
        settings=settings,
        cost=cost,
        tracer=tracer,
        client_factory=client_factory,
        sandbox_factory=sandbox_factory,
        referee_sandbox_factory=referee_sandbox_factory,
        reviewer=reviewer,
        sandboxed=sandboxed,
        policy_summary=render_policy(policy),
        preview_factory=preview_factory if sandboxed else None,  # never run arm code on the host
        profile=profile,
    )


def cost_line(cost: CostTracker) -> str:
    summary = cost.summary()
    scope = "experiment" if summary.experiment else "session"
    total = summary.experiment_total_usd if summary.experiment else summary.session_total_usd
    cap = summary.caps.experiment if summary.experiment else summary.caps.session
    models = ", ".join(f"{m} ${v:.6f}" for m, v in sorted(summary.by_model.items())) or "no calls"
    build_left = summary.caps.build - summary.build_total_usd
    return (
        f"Cost: ${summary.batch_total_usd:.6f} (this command: {models}; "
        f"{scope} ${total:.6f} of ${cap:.2f}; "
        f"build ${summary.build_total_usd:.6f} of ${summary.caps.build:.2f} "
        f"(${build_left:.6f} left))"
    )
