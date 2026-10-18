"""`make warm` planning: what would be built and what would be cached, decided
without a container runtime. A second warm-up after a complete one has nothing left to do."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from shipharness.ab import warm
from shipharness.ab.demo import ABTask
from shipharness.config.prices import REPO_ROOT
from shipharness.harness.base import BaseLayer
from shipharness.harness.verify.layer import VerifyLayer

from .test_demo import LINE, Clients, make_deps
from .test_referee import Factory, all_green

AGENT, REFEREE = "shipharness-agent:1", "shipharness-referee:1"


def test_a_baseline_step_names_its_feature() -> None:
    from types import SimpleNamespace

    plan = SimpleNamespace(kind="referee", section="demo-1", feature="F1")
    assert warm._label(plan) == "referee baseline demo-1 (Feature 1: Org-wide issue search)"  # type: ignore[arg-type]


# -- images ---------------------------------------------------------------------------------------


def ids(**known: str | None):  # type: ignore[no-untyped-def]
    return lambda image: known.get(image.split(":")[0].split("-")[1])


@pytest.mark.parametrize(
    ("stamp", "image_ids", "expected"),
    [
        ({}, ids(agent=None, referee=None), {AGENT: "image missing", REFEREE: "image missing"}),
        ({}, ids(agent="sha:a", referee="sha:r"),
         {AGENT: "no record of its source", REFEREE: "no record of its source"}),
        ({AGENT: {"source": "old", "id": "sha:a"}, REFEREE: {"source": "d1", "id": "sha:r"}},
         ids(agent="sha:a", referee="sha:r"), {AGENT: "source changed", REFEREE: ""}),
        ({AGENT: {"source": "d1", "id": "sha:a"}, REFEREE: {"source": "d1", "id": "sha:r"}},
         ids(agent="sha:other", referee="sha:r"), {AGENT: "image replaced", REFEREE: ""}),
        ({AGENT: {"source": "d1", "id": "sha:a"}, REFEREE: {"source": "d1", "id": "sha:r"}},
         ids(agent="sha:a", referee="sha:r"), {AGENT: "", REFEREE: ""}),
    ],
    ids=["missing", "no-stamp", "source-changed", "replaced", "up-to-date"],
)  # fmt: skip
def test_an_image_is_built_only_when_missing_or_its_source_changed(
    stamp: dict[str, Any], image_ids: Any, expected: dict[str, str]
) -> None:
    plans = warm.plan_images([AGENT, REFEREE], "d1", stamp, image_ids)
    assert {p.image: (p.reason if p.build else "") for p in plans} == expected


def test_the_stamp_records_source_and_image_so_the_next_plan_builds_nothing(
    tmp_path: Path,
) -> None:
    stamp_file = tmp_path / "images.json"
    image_ids = ids(agent="sha:a", referee="sha:r")
    warm.write_stamp(stamp_file, [AGENT, REFEREE], "d1", image_ids)
    plans = warm.plan_images([AGENT, REFEREE], "d1", warm.read_stamp(stamp_file), image_ids)
    assert not any(p.build for p in plans)
    assert warm.read_stamp(tmp_path / "absent.json") == {}


def test_the_source_digest_follows_the_image_build_context(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    for rel, text in {
        "platform/sandbox/Dockerfile": "FROM x\n",
        "pyproject.toml": "[project]\n",
        "uv.lock": "lock\n",
        "platform/src/pkg/a.py": "A = 1\n",
        "platform/src/pkg/__pycache__/a.cpython-312.pyc": "bytes",
        "README.md": "readme\n",
    }.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    first = warm.image_source_digest(root)
    (root / "README.md").write_text("changed\n", encoding="utf-8")  # not in the image
    (root / "platform/src/pkg/__pycache__/a.cpython-312.pyc").write_text("other", encoding="utf-8")
    assert warm.image_source_digest(root) == first
    for rel in (
        "platform/src/pkg/a.py",
        "platform/sandbox/Dockerfile",
        "uv.lock",
        "pyproject.toml",
    ):
        before = warm.image_source_digest(root)
        (root / rel).write_text((root / rel).read_text(encoding="utf-8") + "#\n", encoding="utf-8")
        assert warm.image_source_digest(root) != before, rel


# -- class tasks and baselines -----------------------------------------------------------------


def test_the_class_tasks_are_the_canonical_demo_tasks_and_the_final_features() -> None:
    tasks = warm.class_tasks(REPO_ROOT / "platform" / "datasets" / "teamtrack-features-v1.jsonl")
    assert [(t.section, t.task.feature_id) for t in tasks] == [
        ("demo-1", "F1"), ("demo-2", "F2"), ("demo-3", "F4"), ("demo-4", "F4"),
        ("final", "F5"), ("final", "F6"), ("final", "F7"),
    ]  # fmt: skip
    assert {t.task.variant for t in tasks} == {"canonical"}
    assert [t.section for t in tasks if t.gate] == ["demo-4", "final", "final", "final"]


def test_the_s3_class_task_shares_its_baselines_with_demo_4(setup, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """S3 runs F4 on the demo-3 stack (no verify layer): its referee baseline is demo-4 F4's file,
    and demo-4 F4 brings the F4 gate baseline, so warm computes nothing more for S3."""
    deps, _tasks, _r, _g = setup
    task = ABTask.from_dataset_line(LINE)
    pairs = [warm.ClassTask("demo-3", task), warm.ClassTask("demo-4", task)]
    plan = warm.plan_baselines(pairs, deps, tmp_path / "warm")
    try:
        assert [(b.kind, b.section, b.duplicate) for b in plan] == [
            ("referee", "demo-3", False),
            ("referee", "demo-4", True),
            ("gate", "demo-4", False),
        ]
        assert plan[0].path == plan[1].path
    finally:
        warm.discard(plan)


class NoOp(BaseLayer):
    def __init__(self, **_kw: Any) -> None:
        pass


def noop(layer: str) -> type[BaseLayer]:
    return type(f"NoOp_{layer}", (NoOp,), {"name": layer})


REGISTRY = {
    "instructions": noop("instructions"),
    "state": noop("state"),
    "scope": noop("scope"),
    "verify": VerifyLayer,
}


@pytest.fixture
def setup(course_repo: Path, tmp_path: Path):  # type: ignore[no-untyped-def]
    referee_factory = Factory(all_green())
    gate_factory = Factory(all_green())
    deps = make_deps(
        course_repo,
        tmp_path,
        Clients(),
        referee_sandbox_factory=referee_factory,
        sandbox_factory=lambda arm, ws, bus, run_id: gate_factory(ws, [], arm),
        layer_registry=REGISTRY,
        baseline_cache_dir=tmp_path / "cache" / "referee-baseline",
        harness_kwargs={"gate_baseline_cache_dir": tmp_path / "cache" / "gate-baseline"},
    )
    task = ABTask.from_dataset_line(LINE)
    tasks = [warm.ClassTask("demo-1", task), warm.ClassTask("demo-4", task)]
    return deps, tasks, referee_factory, gate_factory


def test_a_cold_cache_plans_every_baseline_and_a_warm_one_none(setup, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    deps, tasks, referee_factory, gate_factory = setup
    plan = warm.plan_baselines(tasks, deps, tmp_path / "warm")
    try:
        assert [(b.kind, b.section, b.cached) for b in plan] == [
            ("referee", "demo-1", False),
            ("referee", "demo-4", False),
            ("gate", "demo-4", False),
        ]
        assert all(b.path is not None for b in plan)
        # The same task in two sections has one referee baseline: one key, one file.
        assert plan[0].path == plan[1].path
        assert not referee_factory.calls and not gate_factory.calls  # planning starts nothing
    finally:
        warm.discard(plan)
    report = warm.run_baselines(warm.plan_baselines(tasks, deps, tmp_path / "warm"), deps, jobs=2)
    assert {(r.kind, r.ok) for r in report} == {("referee", True), ("gate", True)}
    again = warm.plan_baselines(tasks, deps, tmp_path / "warm")
    try:
        assert all(b.cached for b in again)
    finally:
        warm.discard(again)
    assert not (tmp_path / "warm").exists() or not any((tmp_path / "warm").iterdir())


def test_the_gate_baseline_warm_caches_is_the_one_a_harness_run_reads(
    setup, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    from shipharness.ab.demo import _harness, arm_specs, section_layers
    from shipharness.ab.workspace import create_arm_workspace
    from shipharness.harness.base import LayerContext

    deps, tasks, _r, _g = setup
    warm.run_baselines(warm.plan_baselines(tasks[1:], deps, tmp_path / "warm"), deps, jobs=1)
    task = tasks[1].task
    ws = create_arm_workspace("ab-x", "harness", deps.course_repo, "m1-s1-start",
                              base=tmp_path / "ws")  # fmt: skip
    spec = arm_specs(task, deps.settings, ab_id="ab-x", harness_layers=section_layers("demo-4"),
                     workspaces={"bare": tmp_path / "b", "harness": ws},
                     run_ids={"bare": "r-b", "harness": "r-h"})["harness"]  # fmt: skip
    harness = _harness(task, spec, deps, spec.layers)
    verify = next(layer for layer in harness.layers if layer.name == "verify")
    ctx = LayerContext(spec=spec, phase="build", session_index=0, turn=0, workspace=ws,
                       sandbox=None)  # type: ignore[arg-type]  # fmt: skip
    decisions = verify.prepare_workspace(ctx)  # no sandbox call: the cached baseline is read
    assert [d.message for d in decisions] == ["gate baseline reused (same checkpoint commit)"]


class FakeHost(warm.WarmHost):
    """Images exist once built; every runtime call is recorded."""

    def __init__(self) -> None:
        super().__init__(runtime="docker")
        self.built: dict[str, str] = {}
        self.calls: list[str] = []

    def image_id(self, image: str) -> str | None:
        return self.built.get(image)

    def build(self, command: str, cwd: Path) -> bool:
        self.calls.append(f"build {command}")
        self.built = {AGENT: f"sha:a{len(self.calls)}", REFEREE: f"sha:r{len(self.calls)}"}
        return True

    def page_in(self, image: str) -> bool:
        self.calls.append(f"page-in {image}")
        return True


def test_a_second_warm_up_builds_nothing_and_computes_nothing(setup, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    deps, tasks, referee_factory, gate_factory = setup
    host, lines = FakeHost(), []

    def warm_once() -> bool:
        return warm.warm_up(
            images=[AGENT, REFEREE],
            digest="d1",
            stamp_path=tmp_path / "cache" / "images.json",
            host=host,
            images_command="make images RUNTIME=docker",
            repo=tmp_path,
            tasks=tasks,
            deps=deps,
            base=tmp_path / "warm",
            jobs=2,
            echo=lines.append,
        )

    assert warm_once()
    first = list(host.calls)
    assert first[0].startswith("build make images RUNTIME=docker AGENT_IMAGE=")
    assert first[1:] == [f"page-in {AGENT}", f"page-in {REFEREE}"]
    container_starts = len(referee_factory.calls) + len(gate_factory.calls)
    assert container_starts == 2  # one referee baseline (shared key), one gate baseline
    lines.clear()
    host.calls.clear()
    assert warm_once()
    assert host.calls == [f"page-in {AGENT}", f"page-in {REFEREE}"]  # nothing rebuilt
    assert len(referee_factory.calls) + len(gate_factory.calls) == container_starts
    text = "\n".join(lines)
    assert "nothing built" in text and "cached" in text
    assert lines and all(line.endswith(" s)") for line in lines)  # every step with its timing


# -- class date --------------------------------------------------------------


def _warm_app(monkeypatch: pytest.MonkeyPatch, day: str | None):  # type: ignore[no-untyped-def]
    """`shipharness warm` with settings carrying `day`; any work it starts exits with code 7."""
    import typer

    from shipharness.ab import commands
    from shipharness.config import Settings

    if day is None:
        monkeypatch.delenv("SHIPHARNESS_CLASS_DATE", raising=False)
    else:
        monkeypatch.setenv("SHIPHARNESS_CLASS_DATE", day)
    monkeypatch.setattr(commands, "_settings", lambda: Settings(_env_file=None))

    def started(*_a: object, **_k: object) -> None:
        raise typer.Exit(7)

    monkeypatch.setattr(commands, "_runtime", started)
    monkeypatch.setattr(warm, "warm_up", started)
    app = typer.Typer()

    @app.callback()
    def main() -> None:
        """test app"""

    commands.register(app)
    return app


@pytest.mark.parametrize("day", [None, "", "20-10-2026", "2026-02-30"])
def test_warm_for_class_refuses_without_a_valid_class_date_before_any_work(
    monkeypatch: pytest.MonkeyPatch, day: str | None
) -> None:
    from typer.testing import CliRunner

    app = _warm_app(monkeypatch, day)
    for argv in (["warm"], ["warm", "--purpose", "class"]):
        result = CliRunner().invoke(app, argv)
        assert result.exit_code == 2, result.output  # never 7: no image, container, or baseline
        assert "SHIPHARNESS_CLASS_DATE" in result.output
        assert "SHIPHARNESS_CLASS_DATE=YYYY-MM-DD" in result.output  # the .env line
        assert "export SHIPHARNESS_CLASS_DATE=YYYY-MM-DD" in result.output
        assert "shipharness-class-<date>" in result.output
        assert "--purpose pilot" in result.output or "PURPOSE=pilot" in result.output


@pytest.mark.parametrize("purpose", ["pilot", "assignment"])
def test_warm_for_pilot_or_assignment_needs_no_class_date(
    monkeypatch: pytest.MonkeyPatch, purpose: str
) -> None:
    from typer.testing import CliRunner

    result = CliRunner().invoke(_warm_app(monkeypatch, None), ["warm", "--purpose", purpose])
    assert result.exit_code == 7, result.output  # past the date check: the work starts


def test_warm_with_a_class_date_starts_the_work(monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    result = CliRunner().invoke(_warm_app(monkeypatch, "2026-10-20"), ["warm"])
    assert result.exit_code == 7, result.output


def test_warm_refuses_an_unknown_purpose(monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    result = CliRunner().invoke(_warm_app(monkeypatch, "2026-10-20"), ["warm", "--purpose", "x"])
    assert result.exit_code == 2
    assert "class, pilot, or assignment" in result.output
