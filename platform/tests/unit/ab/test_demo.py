from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from shipharness.ab.demo import ABDeps, ABTask, arm_specs, run_ab, section_layers
from shipharness.config import DEFAULT_PRICES_FILE, Prices, Settings
from shipharness.cost import Caps, CostTracker, Usage
from shipharness.events import read_events
from shipharness.harness.base import BaseLayer, LayerContext
from shipharness.harness.decisions import HarnessDecision
from shipharness.runner.model import ScriptedModelClient, Step, tool_step
from shipharness.sandbox import FakeSandbox
from shipharness.tracing import NullTracer, read_exports

from .test_referee import Factory, all_green

LINE = {
    "inputs": {
        "feature_id": "F1",
        "checkpoint": "m1-s1-start",
        "ticket_text": "Add cursor pagination to GET /projects/{id}/issues.",
        "variant": "canonical",
        "session_budget": [6],
    },
    "outputs": {
        "hidden_test_ids": ["teamtrack/tests/hidden/f1/test_secret.py::test_secret"],
        "allowed_paths": {
            "build": ["app/api/**", "tests/visible/**"],
            "test": ["tests/visible/**"],
        },
        "mutant_set": "f1",
        "primary_measure": "r1_new_violations>=1",
    },
    "metadata": {
        "group": "canonical",
        "example_id": "F1-canonical",
        "category": "api",
        "description": "Cursor pagination",
        "steps": ["GET returns next_cursor"],
    },
    "split": ["section-1"],
}


class FakeInstructions(BaseLayer):
    name = "instructions"
    seen_kwargs: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, **kwargs: Any) -> None:
        FakeInstructions.seen_kwargs.append(kwargs)

    def prepare_workspace(self, ctx: LayerContext) -> list[HarnessDecision]:
        (ctx.workspace / "AGENTS.md").write_bytes(b"# Map\n")
        return [HarnessDecision(kind="note", layer="instructions", paths=["AGENTS.md"])]


def steps() -> list[Step]:
    return [
        tool_step("list_dir", path=".", depth=None),
        tool_step("finish", claim="done", summary="built"),
        tool_step("finish", claim="done", summary="tests"),
    ]


class Clients:
    def __init__(self, barrier: threading.Barrier | None = None, **per_arm: list[Step]) -> None:
        self.barrier = barrier
        self.per_arm = per_arm
        self.clients: dict[str, ScriptedModelClient] = {}

    def __call__(self, arm: str) -> ScriptedModelClient:
        barrier = self.barrier

        class Client(ScriptedModelClient):
            def respond(self, *a: Any, **kw: Any):  # type: ignore[no-untyped-def]
                if barrier is not None and not self.inputs:
                    barrier.wait()  # both arms must be in their first turn at the same time
                return super().respond(*a, **kw)

        client = Client(self.per_arm.get(arm, steps()))
        self.clients[arm] = client
        return client


def make_deps(course_repo: Path, tmp_path: Path, clients: Clients, **kw: Any) -> ABDeps:
    settings = Settings(
        _env_file=None, runs_dir=tmp_path / "runs", exports_dir=tmp_path / "exports"
    )
    cost = CostTracker(
        Prices.load(DEFAULT_PRICES_FILE),
        Caps(0.2, 0.04, 2.5, 2.5, 25.0),
        tmp_path / "ledger.jsonl",
        session_id="t",
    )
    sandboxes: dict[str, FakeSandbox] = {}

    def sandbox_factory(arm, ws, bus, run_id):  # type: ignore[no-untyped-def]
        sandboxes[arm] = FakeSandbox()
        return sandboxes[arm]

    base: dict[str, Any] = dict(
        settings=settings,
        course_repo=course_repo,
        checkpoint_ref="m1-s1-start",
        client_factory=clients,
        sandbox_factory=sandbox_factory,
        referee_sandbox_factory=Factory(all_green()),
        cost=cost,
        tracer=NullTracer(),
        workspace_base=tmp_path / "ws",
        layer_registry={"instructions": FakeInstructions},
    )
    base.update(kw)
    deps = ABDeps(**base)
    deps.sandboxes = sandboxes  # type: ignore[attr-defined]
    return deps


def test_task_from_dataset_line() -> None:
    task = ABTask.from_dataset_line(LINE)
    assert task.feature_id == "F1" and task.session_budget == [6]
    assert task.allowed_paths["build"] == ["app/api/**", "tests/visible/**"]
    assert task.primary_measure == "r1_new_violations>=1"
    assert task.harness_kwargs()["feature_steps"] == ["GET returns next_cursor"]


def test_a_line_without_steps_lets_the_layers_take_the_ticket_steps() -> None:
    # The dataset lines carry no metadata steps. Passing [] made the state and scope layers write a
    # feature list and exec plan with no steps; None makes them use the ticket's bullet lines.
    import copy

    line = copy.deepcopy(LINE)
    line.get("metadata", {}).pop("steps", None)
    line.get("inputs", {}).get("metadata", {}).pop("steps", None)
    task = ABTask.from_dataset_line(line)
    assert "steps" not in task.metadata
    assert task.harness_kwargs()["feature_steps"] is None


def test_real_dataset_tickets_never_give_the_layers_an_empty_step_list() -> None:
    import json

    from shipharness.config.prices import REPO_ROOT

    path = REPO_ROOT / "platform" / "datasets" / "teamtrack-features-v1.jsonl"
    lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]
    for line in lines:
        steps = ABTask.from_dataset_line(line).harness_kwargs()["feature_steps"]
        assert steps is None or steps, line["metadata"].get("example_id")


@pytest.mark.parametrize(
    ("section", "modifier", "expected"),
    [
        ("demo-1", None, {"instructions"}),
        ("demo-2", None, {"instructions", "state"}),
        ("demo-3", None, {"instructions", "state", "scope"}),
        ("demo-4", None, {"instructions", "state", "scope", "verify"}),
        ("final", None, {"instructions", "state", "scope", "verify"}),
        ("demo-3", "-state", {"instructions", "scope"}),
    ],
)
def test_section_layer_stacks_follow_design_6_6(
    section: str, modifier: str | None, expected: set[str]
) -> None:
    assert section_layers(section, modifier) == frozenset(expected)


def test_both_arms_get_identical_inputs(tmp_path: Path) -> None:
    task = ABTask.from_dataset_line(LINE)
    settings = Settings(_env_file=None)
    specs = arm_specs(
        task,
        settings,
        ab_id="ab-1",
        harness_layers=frozenset({"instructions"}),
        workspaces={"bare": tmp_path / "b", "harness": tmp_path / "h"},
        run_ids={"bare": "r-b", "harness": "r-h"},
    )
    bare, harness = specs["bare"].public_dict(), specs["harness"].public_dict()
    for differing in ("arm", "run_id", "layers"):
        bare.pop(differing)
        harness.pop(differing)
    assert bare == harness
    assert specs["bare"].layers == frozenset()


def test_run_ab_runs_both_arms_in_parallel_and_scores_both(
    course_repo: Path, tmp_path: Path
) -> None:
    clients = Clients(barrier=threading.Barrier(2, timeout=20))
    deps = make_deps(course_repo, tmp_path, clients)
    FakeInstructions.seen_kwargs.clear()
    result = run_ab(ABTask.from_dataset_line(LINE), frozenset({"instructions"}), deps)
    assert set(result.arms) == {"bare", "harness"}
    for arm_run in result.arms.values():
        assert arm_run.result.status == "completed"
        assert arm_run.record.arm == arm_run.spec.arm
    log = tmp_path / "runs" / result.ab_id / "events.jsonl"
    events = list(read_events(log))
    starts = {e.arm for e in events if e.type == "run_start"}
    assert starts == {"bare", "harness"}
    assert {e.arm for e in events if e.type == "verdict"} == {"bare", "harness"}
    scores = read_exports("scores", tmp_path / "exports")
    assert {s["run_id"] for s in scores} == {a.spec.run_id for a in result.arms.values()}
    assert FakeInstructions.seen_kwargs[-1]["feature_category"] == "api"


def test_each_arm_gets_a_primary_verdict_before_its_full_verdict(
    course_repo: Path, tmp_path: Path
) -> None:
    deps = make_deps(course_repo, tmp_path, Clients())
    result = run_ab(ABTask.from_dataset_line(LINE), frozenset({"instructions"}), deps)
    events = list(read_events(tmp_path / "runs" / result.ab_id / "events.jsonl"))
    for arm, arm_run in result.arms.items():
        [early] = [e for e in events if e.type == "primary_verdict" and e.arm == arm]
        [final] = [e for e in events if e.type == "verdict" and e.arm == arm]
        [ended] = [e for e in events if e.type == "run_end" and e.arm == arm]
        assert ended.seq < early.seq < final.seq
        assert early.data["run_id"] == arm_run.spec.run_id == early.run_id
        assert early.data["passed"] == arm_run.record.passed_primary
        assert early.data["values"] == arm_run.record.primary
        assert early.data["primary_measure"] == "r1_new_violations>=1"
        assert early.data["elapsed_s"] >= 0 and early.recorded is False
    from shipharness.ab.demo import _ARM_ENDED

    assert not {a.spec.run_id for a in result.arms.values()} & set(_ARM_ENDED)  # used, not kept


def test_workspaces_are_outside_the_course_checkout_and_bare_has_no_harness_files(
    course_repo: Path, tmp_path: Path
) -> None:
    deps = make_deps(course_repo, tmp_path, Clients())
    result = run_ab(ABTask.from_dataset_line(LINE), frozenset({"instructions"}), deps)
    bare_ws = result.arms["bare"].spec.workspace
    harness_ws = result.arms["harness"].spec.workspace
    assert course_repo.resolve() not in bare_ws.resolve().parents
    assert not (bare_ws / "AGENTS.md").exists()
    assert (harness_ws / "AGENTS.md").exists()
    assert not (harness_ws / "tests" / "hidden").exists()


def test_an_aborted_arm_is_kept_and_scored(course_repo: Path, tmp_path: Path) -> None:
    pricey = Usage(input_tokens=1000, output_tokens=500_000)
    clients = Clients(bare=[tool_step("list_dir", path=".", depth=None, usage=pricey)])
    deps = make_deps(course_repo, tmp_path, clients)
    result = run_ab(ABTask.from_dataset_line(LINE), frozenset({"instructions"}), deps)
    assert result.arms["bare"].result.status == "ABORTED: cap"
    assert result.arms["bare"].record.status == "ABORTED: cap"


def test_sandbox_failure_becomes_an_error_run_that_is_still_scored(
    course_repo: Path, tmp_path: Path
) -> None:
    class Broken(FakeSandbox):
        def start(self) -> str:
            raise RuntimeError("docker run failed")

    deps = make_deps(
        course_repo,
        tmp_path,
        Clients(),
        sandbox_factory=lambda arm, ws, bus, run_id: Broken() if arm == "bare" else FakeSandbox(),
    )
    result = run_ab(ABTask.from_dataset_line(LINE), frozenset({"instructions"}), deps)
    assert result.arms["bare"].result.status == "ERROR"
    assert "docker run failed" in (result.arms["bare"].result.error or "")
    assert result.arms["bare"].record.status == "ERROR"


def test_final_section_specs_carry_the_final_run_cap(tmp_path: Path) -> None:
    task = ABTask.from_dataset_line(LINE)
    settings = Settings(_env_file=None)
    specs = arm_specs(
        task,
        settings,
        ab_id="ab-1",
        harness_layers=frozenset({"instructions"}),
        workspaces={"bare": tmp_path / "b", "harness": tmp_path / "h"},
        run_ids={"bare": "r-b", "harness": "r-h"},
        run_cost_limit_usd=settings.max_final_run_cost_usd,
    )
    assert {s.cost_limit_usd for s in specs.values()} == {0.25}


def test_final_section_ab_runs_to_the_final_cap_not_the_run_cap(
    course_repo: Path, tmp_path: Path
) -> None:
    settings = Settings(_env_file=None)
    final = CostTracker(
        Prices.load(DEFAULT_PRICES_FILE),
        Caps.from_settings(settings, final=True),  # what `shipharness ab --section final` builds
        tmp_path / "ledger.jsonl",
        session_id="t",
    )
    per_call = Usage(input_tokens=0, output_tokens=8_000)  # $0.004, within the pre-check estimate
    burner = [tool_step("list_dir", path=".", depth=None, usage=per_call)] * 90
    line = {**LINE, "inputs": {**LINE["inputs"], "session_budget": [90]}}
    deps = make_deps(course_repo, tmp_path, Clients(bare=burner), cost=final)
    result = run_ab(ABTask.from_dataset_line(line), frozenset({"instructions"}), deps)
    bare = result.arms["bare"]
    assert {run.spec.cost_limit_usd for run in result.arms.values()} == {0.25}
    assert bare.result.status == "ABORTED: cap"
    assert 0.20 < bare.result.cost_usd <= 0.25  # spent past $0.20, stopped by the $0.25 cap


def test_harness_timeout_setting_defaults_to_120_seconds() -> None:
    assert Settings(_env_file=None).harness_timeout_s == 120


def test_session_patches_come_from_snapshots_when_the_arm_never_commits(tmp_path: Path) -> None:
    import subprocess

    from shipharness.ab.demo import session_patches
    from shipharness.runner import git as run_git
    from shipharness.runner.models import SessionResult

    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "app.py").write_text("a = 1\n", encoding="utf-8")
    ident = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false"]
    subprocess.run(["git", *ident, "init", "-q"], cwd=ws, check=True)
    subprocess.run(["git", *ident, "add", "-A"], cwd=ws, check=True)
    subprocess.run(["git", *ident, "commit", "-qm", "base"], cwd=ws, check=True)
    sha = run_git.head_sha(ws)
    store = tmp_path / "run" / "harness" / "snapshots" / "store.git"
    t0 = run_git.snapshot_tree(ws, store)
    (ws / "app.py").write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")  # session 1
    t1 = run_git.snapshot_tree(ws, store)
    (ws / "app.py").write_text("a = 1\n", encoding="utf-8")  # session 2 undoes session 1
    t2 = run_git.snapshot_tree(ws, store)
    sessions = [
        SessionResult(index=1, phase="build", turns=3, ended_by="turn_budget",
                      start_sha=sha, end_sha=sha, start_tree=t0, end_tree=t1),
        SessionResult(index=2, phase="build", turns=3, ended_by="turn_budget",
                      start_sha=sha, end_sha=sha, start_tree=t1, end_tree=t2),
    ]  # fmt: skip
    spec = SimpleNamespace(workspace=ws)
    result = SimpleNamespace(sessions=sessions)
    out_dir = tmp_path / "run" / "harness" / "sessions"
    patches = session_patches(spec, result, out_dir, store=store)  # type: ignore[arg-type]
    texts = [p.read_text(encoding="utf-8") for p in patches]
    assert "+b = 2" in texts[0] and "-b = 2" in texts[1]


def test_referee_baseline_runs_while_the_arms_work(course_repo: Path, tmp_path: Path) -> None:
    import threading

    from .test_referee import Factory as RefereeFactory
    from .test_referee import all_green

    started = threading.Event()

    class Baseline(RefereeFactory):
        def __call__(self, build, mounts, arm):  # type: ignore[no-untyped-def]
            if build.parent.name == "baseline":
                started.set()
            return super().__call__(build, mounts, arm)

    seen: list[bool] = []

    class Waiting(Clients):
        def __call__(self, arm: str):  # type: ignore[no-untyped-def]
            client = super().__call__(arm)
            original = client.respond

            def respond(*a, **kw):  # type: ignore[no-untyped-def]
                if not seen or len(seen) < 2:
                    seen.append(started.wait(10))
                return original(*a, **kw)

            client.respond = respond  # type: ignore[method-assign]
            return client

    deps = make_deps(
        course_repo, tmp_path, Waiting(), referee_sandbox_factory=Baseline(all_green())
    )
    run_ab(ABTask.from_dataset_line(LINE), frozenset({"instructions"}), deps)
    assert seen and all(seen)  # the arms saw the baseline already started


def test_test_phase_files_ignore_uncommitted_build_work(tmp_path: Path) -> None:
    # M6 pilot: the bare arm never commits, so comparing the working tree with HEAD at the start
    # of the test phase counted all of its build-phase work as test-phase source edits (S3).
    import subprocess

    from shipharness.ab.demo import phase_changed_files
    from shipharness.runner import git as run_git
    from shipharness.runner.models import SessionResult

    ws = tmp_path / "ws"
    (ws / "app").mkdir(parents=True)
    (ws / "app" / "a.py").write_text("a = 1\n", encoding="utf-8")
    ident = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false"]
    subprocess.run(["git", *ident, "init", "-q"], cwd=ws, check=True)
    subprocess.run(["git", *ident, "add", "-A"], cwd=ws, check=True)
    subprocess.run(["git", *ident, "commit", "-qm", "base"], cwd=ws, check=True)
    sha = run_git.head_sha(ws)
    store = tmp_path / "run" / "bare" / "snapshots" / "store.git"
    t0 = run_git.snapshot_tree(ws, store)
    (ws / "app" / "a.py").write_text("a = 2\n", encoding="utf-8")  # build session, no commit
    t1 = run_git.snapshot_tree(ws, store)
    (ws / "tests" / "visible").mkdir(parents=True)
    (ws / "tests" / "visible" / "test_a.py").write_text("def test_a():\n    pass\n", "utf-8")
    t2 = run_git.snapshot_tree(ws, store)
    sessions = [
        SessionResult(index=1, phase="build", turns=3, ended_by="turn_budget",
                      start_sha=sha, end_sha=sha, start_tree=t0, end_tree=t1),
        SessionResult(index=2, phase="test", turns=3, ended_by="turn_budget",
                      start_sha=sha, end_sha=sha, start_tree=t1, end_tree=t2),
    ]  # fmt: skip
    spec = SimpleNamespace(workspace=ws)
    result = SimpleNamespace(sessions=sessions, phase_shas={"test": (sha, sha)})
    assert phase_changed_files(spec, result) == ["app/a.py", "tests/visible/test_a.py"]  # type: ignore[arg-type]
    assert phase_changed_files(spec, result, store=store) == ["tests/visible/test_a.py"]  # type: ignore[arg-type]


def test_each_arm_is_judged_as_soon_as_it_finishes(course_repo: Path, tmp_path: Path) -> None:
    # Approved after pilot run 2: no idle wait for the other arm before judging.
    from .test_referee import Factory as RefereeFactory
    from .test_referee import all_green

    bare_judged = threading.Event()

    class Watching(RefereeFactory):
        def __call__(self, build, mounts, arm):  # type: ignore[no-untyped-def]
            if arm == "bare" and build.parent.name != "baseline":
                bare_judged.set()
            return super().__call__(build, mounts, arm)

    seen: list[bool] = []

    class SlowHarness(Clients):
        def __call__(self, arm: str):  # type: ignore[no-untyped-def]
            client = super().__call__(arm)
            if arm == "harness":
                original = client.respond

                def respond(*a, **kw):  # type: ignore[no-untyped-def]
                    if not seen:
                        seen.append(bare_judged.wait(5))
                    return original(*a, **kw)

                client.respond = respond  # type: ignore[method-assign]
            return client

    deps = make_deps(
        course_repo, tmp_path, SlowHarness(), referee_sandbox_factory=Watching(all_green())
    )
    result = run_ab(ABTask.from_dataset_line(LINE), frozenset({"instructions"}), deps)
    assert seen == [True]  # the bare arm was being judged while the harness arm still ran
    assert {arm: run.record.arm for arm, run in result.arms.items()} == {
        "bare": "bare",
        "harness": "harness",
    }
