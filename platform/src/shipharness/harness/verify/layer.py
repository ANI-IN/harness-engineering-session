"""VerifyLayer (S4): the gate on finish(claim="done") and the test filters at the end of the test
phase. Contract I-8 (hooks), §13 (gate), §14 (filters)."""

from __future__ import annotations

import hashlib
import json
import shlex
from pathlib import Path
from typing import Any, ClassVar

from shipharness.checks import params as P
from shipharness.harness import suite_cache
from shipharness.harness.base import BaseLayer, LayerContext, register_layer
from shipharness.harness.decisions import HarnessDecision, LayerName
from shipharness.harness.verify import checkrun, testphase
from shipharness.harness.verify.checkrun import (
    RunnerOutputError,
    new_nonce,
    parse_runner_output,
    write_container_file,
)
from shipharness.harness.verify.checkrun import runner_command as _runner_command
from shipharness.harness.verify.clean_state import DEFAULT_RUFF_SELECT
from shipharness.harness.verify.gate import GATE_CHECKS, GateConfig, run_gate
from shipharness.harness.verify.models import GateResult
from shipharness.runner import git
from shipharness.runner.tools import iter_workspace_files

PREFIX = """\
Verification: when you call finish with claim="done", a gate runs in your sandbox before the \
phase can end: the visible tests, the existing tests, House rules 1 to 7, the board, and a clean \
state check (all work committed, ruff clean on changed Python files, one migration head, no debug \
output). If any item fails, finish returns the first three failures and the phase continues. Tests \
you write in the test phase are kept only if they pass the test filters."""
# The same text for a repository without migrations (no alembic.ini, no migrations/versions).
PREFIX_NO_MIGRATIONS = PREFIX.replace(" one migration head,", "")


def has_migrations(workspace: Path) -> bool:
    """Whether the repository has a migration configuration: an alembic.ini at its root, or the
    migrations/versions directory TeamTrack's adapter uses. Links are not followed."""
    root = Path(workspace)
    ini = root / "alembic.ini"
    versions = root / "migrations" / "versions"
    return (ini.is_file() and not ini.is_symlink()) or (
        versions.is_dir() and not versions.is_symlink()
    )


def has_ruff_config(workspace: Path) -> bool:
    """Whether the repository configures ruff itself: ruff.toml or .ruff.toml at its root, or a
    [tool.ruff] table in pyproject.toml. Links are not followed."""
    root = Path(workspace)
    for name in ("ruff.toml", ".ruff.toml"):
        path = root / name
        if path.is_file() and not path.is_symlink():
            return True
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file() or pyproject.is_symlink():
        return False
    text = pyproject.read_text(encoding="utf-8", errors="replace")
    return any(line.strip().startswith("[tool.ruff") for line in text.splitlines())


def default_seed(feature_id: str, checkpoint: str) -> int:
    """Fixed seed per task, so the gate's property-based checks are reproducible."""
    digest = hashlib.sha256(f"{feature_id}@{checkpoint}".encode()).hexdigest()
    return int(digest[:8], 16)


@register_layer
class VerifyLayer(BaseLayer):
    name: ClassVar[LayerName] = "verify"

    def __init__(
        self,
        *,
        checks: tuple[str, ...] = GATE_CHECKS,
        seed: int | None = None,
        exemptions: dict[str, list[str]] | None = None,
        baseline_json: str | None = None,
        compute_baseline: bool = True,
        pipeline: testphase.Pipeline | None = None,
        gate_timeout_s: int = 600,
        gate_baseline_cache_dir: Path | str | None = None,
        max_filtered_tests: int | None = None,
        **_ignored: Any,
    ) -> None:
        self.checks = tuple(checks)
        self.seed = seed
        # None: the check runner uses the adapter's documented exemptions for the checkpoint.
        self.exemptions = dict(exemptions) if exemptions is not None else None
        self.baseline_json = baseline_json
        self.compute_baseline = compute_baseline
        self.pipeline = pipeline or testphase.filters_pipeline
        self.gate_timeout_s = gate_timeout_s
        # Baselines reused across runs that start from the same checkpoint commit (M6 pilot).
        self.gate_baseline_cache_dir = (
            Path(gate_baseline_cache_dir) if gate_baseline_cache_dir is not None else None
        )
        self.existing_tests: list[str] = []
        # Decided from the checkpoint workspace in prepare_workspace, so files the agent adds or
        # deletes later cannot switch the migration head check on or off. None: not decided yet
        # (the check runs, as on TeamTrack).
        self.migrations: bool | None = None
        self.ruff_config: bool | None = None  # decided the same way, from the checkpoint
        self.gate_count = 0
        # Demo setting (`make show-4`, never an A/B): only the first N proposed tests go through
        # the filters; the rest are removed with a reason. None: every proposed test is filtered.
        self.max_filtered_tests = max_filtered_tests
        self._phase_start: dict[str, tuple[dict[str, str], dict[str, str]]] = {}

    # -- helpers -------------------------------------------------------------------------------

    def _seed(self, ctx: LayerContext) -> int:
        if self.seed is None:
            return default_seed(ctx.spec.feature_id, ctx.spec.checkpoint)
        return self.seed

    def _params(self, ctx: LayerContext) -> dict[str, Any]:
        params: dict[str, Any] = {
            P.REGRESSION_TARGETS: list(self.existing_tests),
            P.ALLOWED_PATHS: {k: list(v) for k, v in ctx.spec.allowed_paths.items()},
        }
        if self.exemptions is not None:
            params[P.EXEMPTIONS] = self.exemptions
        return params

    def _config(self, ctx: LayerContext) -> GateConfig:
        return GateConfig(
            checkpoint=ctx.spec.checkpoint,
            feature=ctx.spec.feature_id,
            seed=self._seed(ctx),
            checks=self.checks,
            params=self._params(ctx),
            baseline_json=self.baseline_json,
            timeout_s=self.gate_timeout_s,
            time_left=ctx.time_left,
            visible_tests_dir=ctx.spec.visible_tests_dir,
            migrations=self.migrations is not False,
            ruff_select=None if self.ruff_config else DEFAULT_RUFF_SELECT,
        )

    def _publish(self, ctx: LayerContext, type_: str, data: Any) -> None:
        if ctx.bus is not None:
            ctx.bus.publish(type_, data, run_id=ctx.spec.run_id, arm=ctx.spec.arm)  # type: ignore[arg-type]

    @staticmethod
    def _limit(ctx: LayerContext, own_s: int) -> int:
        left = ctx.time_left()
        return own_s if left is None else max(1, min(own_s, int(left)))

    # -- hooks ---------------------------------------------------------------------------------

    @staticmethod
    def _visible_tests(root: Path, visible_tests_dir: str) -> list[str]:
        return sorted(
            p.relative_to(root).as_posix()
            for p in iter_workspace_files(root / visible_tests_dir)
            if p.suffix == ".py"
        )

    def cached_baseline_path(self, ctx: LayerContext) -> Path | None:
        """Where prepare_workspace reads and writes this workspace's gate baseline (`make warm`
        plans with it before any container starts)."""
        self.existing_tests = self._visible_tests(ctx.workspace, ctx.spec.visible_tests_dir)
        return self._baseline_cache_path(ctx)

    def prepare_workspace(self, ctx: LayerContext) -> list[HarnessDecision]:
        self.existing_tests = self._visible_tests(ctx.workspace, ctx.spec.visible_tests_dir)
        self.migrations = has_migrations(ctx.workspace)
        self.ruff_config = has_ruff_config(ctx.workspace)
        if self.baseline_json is not None or not self.compute_baseline:
            return []
        if "build" not in ctx.spec.phases:
            # The baseline serves the house-rule checks, which only the build-phase gate runs
            # (a testgen run has the test phase only).
            return []
        cached = self._baseline_cache_path(ctx)
        if cached is not None and cached.is_file():
            self.baseline_json = cached.read_text(encoding="utf-8")
            note = "gate baseline reused (same checkpoint commit)"
            return [HarnessDecision(kind="note", layer="verify", message=note)]
        self.baseline_json = self._baseline(ctx)
        if self.baseline_json and cached is not None:
            cached.parent.mkdir(parents=True, exist_ok=True)
            partial = cached.with_suffix(".part")
            partial.write_text(self.baseline_json, encoding="utf-8")
            partial.replace(cached)
        note = "gate baseline recorded" if self.baseline_json else "gate baseline unavailable"
        return [HarnessDecision(kind="note", layer="verify", message=note)]

    def _baseline_cache_path(self, ctx: LayerContext) -> Path | None:
        """Keyed by the checkpoint commit's tree, the task, the seed, the checks, the gate
        parameters, and the check code; None without a cache directory or a checkpoint commit."""
        if self.gate_baseline_cache_dir is None:
            return None
        tree = git.root_tree(ctx.workspace)
        if not tree:
            return None
        import shipharness.checks as checks_package

        code = hashlib.sha256()
        for path in sorted(Path(checks_package.__file__).parent.glob("*.py")):
            code.update(path.name.encode() + b"\0" + path.read_bytes())
        code.update(Path(checkrun.__file__).read_bytes())
        key = {
            "checkpoint_tree": tree,
            "checkpoint": ctx.spec.checkpoint,
            "feature": ctx.spec.feature_id,
            "seed": self._seed(ctx),
            "checks": list(self.checks),
            "params": self._params(ctx),
            "code": code.hexdigest(),
        }
        digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:32]
        return self.gate_baseline_cache_dir / f"{digest}.json"

    def _baseline(self, ctx: LayerContext) -> str | None:
        """Runner output on the untouched workspace, so the gate counts only new violations."""
        root = f"/tmp/shipharness-gate-baseline-{ctx.spec.run_id}"
        ctx.sandbox.exec(
            f"rm -rf {root} && mkdir -p {root}/build && cp -a ./. {root}/build/",
            self._limit(ctx, 300),
        )
        # Same params as every gate run, so exemptions and targets match the gate's baseline key.
        params = {**self._params(ctx), P.ARTIFACTS_DIR: f"{root}/artifacts"}
        try:
            write_container_file(
                ctx.sandbox,
                f"{root}/params.json",
                json.dumps(params, sort_keys=True),
                self._limit(ctx, 30),
            )
        except RuntimeError:
            ctx.sandbox.exec(f"rm -rf {root}", self._limit(ctx, 60))
            return None
        command = _runner_command(
            build=f"{root}/build",
            checks=list(self.checks),
            checkpoint=ctx.spec.checkpoint,
            feature=ctx.spec.feature_id,
            seed=self._seed(ctx),
            params=f"{root}/params.json",
            nonce=(nonce := new_nonce()),
        )
        output = ctx.sandbox.exec(f"cd {root} && {command}", self._limit(ctx, self.gate_timeout_s))
        ctx.sandbox.exec(f"rm -rf {root}", self._limit(ctx, 60))
        try:
            results, _ = parse_runner_output(output.output, nonce=nonce)
        except RunnerOutputError:
            return None
        return json.dumps({"results": [r.model_dump(mode="json") for r in results]})

    def context_prefix(self, ctx: LayerContext) -> list[str]:
        if ctx.phase not in self._phase_start:  # first hook of each phase: remember its start
            self._phase_start[ctx.phase] = testphase.snapshot(
                ctx.workspace, ctx.spec.visible_tests_dir
            )
        return [PREFIX if self.migrations is not False else PREFIX_NO_MIGRATIONS]

    def on_claim_done(self, ctx: LayerContext) -> HarnessDecision | None:
        self.gate_count += 1
        gate_id = f"{ctx.spec.run_id}-g{self.gate_count}"

        def update(result: GateResult) -> None:
            self._publish(ctx, "gate_result", result)

        def progress(item: dict[str, Any]) -> None:
            self._publish(ctx, "check_progress", item)

        cfg = self._config(ctx)
        # Taken just before the gate copies the workspace: the content its visible tests run on.
        cfg.visible_reuse = (ctx.state, suite_cache.content_key(ctx.workspace))
        result = run_gate(
            ctx.sandbox,
            cfg,
            gate_id=gate_id,
            # The arm's own changes start after the harness setup commit (placed artifacts).
            base_sha=str(ctx.state.get("harness.setup_sha") or git.initial_sha(ctx.workspace)),
            phase=ctx.phase,
            on_update=update,
            on_progress=progress,
        )
        ctx.state["verify.gate"] = result.model_dump(mode="json")
        data = {"gate_id": gate_id, "seed": self._seed(ctx)}
        if result.passed:
            return HarnessDecision(
                kind="gate_pass", layer="verify", message=f"gate {gate_id} passed", data=data
            )
        return HarnessDecision(kind="gate_fail", layer="verify", message=result.feedback, data=data)

    def on_phase_end(self, ctx: LayerContext) -> list[HarnessDecision]:
        if ctx.phase != "test":
            return []
        where = ctx.spec.visible_tests_dir
        shas, texts = self._phase_start.get("test") or testphase.snapshot(ctx.workspace, where)
        candidates, broken = testphase.find_candidates(ctx.workspace, texts, where)
        testphase.delete_files(ctx.workspace, list(broken), where)
        discarded = {f"{rel}::<file>": reason for rel, reason in broken.items()}
        over: dict[str, str] = {}
        cap = self.max_filtered_tests
        if cap is not None and len(candidates) > cap:
            note = f"not filtered: this demo filters only the first {cap} proposed tests"
            over = {c["test_id"]: note for c in candidates[cap:]}
            candidates = candidates[:cap]
        if over:
            by_file_over: dict[str, list[str]] = {}
            for test_id in over:
                rel, name = test_id.split("::", 1)
                by_file_over.setdefault(rel, []).append(name)
            testphase.remove_tests(ctx.workspace, by_file_over, where)
            discarded.update(over)
        if not candidates:
            return [self._filter_note(ctx, [], discarded, "no new tests to filter")]
        try:
            results = self.pipeline(candidates, ctx, shas)
        except testphase.PipelineUnavailable as exc:
            kept = [c["test_id"] for c in candidates]
            return [self._filter_note(ctx, kept, discarded, f"test filters unavailable: {exc}")]
        reasons = testphase.discarded_reasons(results)
        by_file: dict[str, list[str]] = {}
        for c in candidates:
            if c["test_id"] in reasons:
                by_file.setdefault(c["file"], []).append(c["test_id"].split("::", 1)[1])
        testphase.remove_tests(ctx.workspace, by_file, where)
        kept = [c["test_id"] for c in candidates if c["test_id"] not in reasons]
        discarded.update(reasons)
        return [self._filter_note(ctx, kept, discarded, "")]

    def _filter_note(
        self, ctx: LayerContext, kept: list[str], discarded: dict[str, str], extra: str
    ) -> HarnessDecision:
        if kept or discarded:
            ctx.sandbox.exec(
                f"git add -A {shlex.quote(ctx.spec.visible_tests_dir)} && git commit -q -m "
                f"'test: keep {len(kept)} tests that passed the filters' || true",
                120,
            )
        message = f"test filters: kept {len(kept)}, discarded {len(discarded)}"
        return HarnessDecision(
            kind="note",
            layer="verify",
            message=f"{message}; {extra}" if extra else message,
            data={"kept": kept, "discarded": discarded},
        )
