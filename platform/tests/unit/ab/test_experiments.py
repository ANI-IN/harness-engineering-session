from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from shipharness.ab.experiments import ExperimentPlan, attach_scores, run_experiments
from shipharness.ab.score import SCORE_KEYS
from shipharness.tracing import read_exports

from .test_demo import LINE, Clients, make_deps


class FakeLangSmith:
    def __init__(self, examples: list[Any]) -> None:
        self.examples = examples
        self.list_calls: list[dict[str, Any]] = []
        self.feedback: list[dict[str, Any]] = []

    def list_examples(self, **kwargs: Any) -> list[Any]:
        self.list_calls.append(kwargs)
        return self.examples

    def create_feedback(self, **kwargs: Any) -> None:
        self.feedback.append(kwargs)


class FakeEvaluate:
    """Mimics langsmith.evaluate: target per example x repetitions, then each evaluator."""

    def __init__(self, export_dir: Path) -> None:
        self.calls: list[dict[str, Any]] = []
        self.scores: list[list[dict[str, Any]]] = []
        self.export_dir = export_dir
        self.exported_before_return: list[bool] = []
        self.lock = threading.Lock()

    def __call__(self, target: Any, *, data: Any, evaluators: list[Any], **kwargs: Any) -> Any:
        with self.lock:
            self.calls.append(kwargs)
        rows = []
        for _ in range(kwargs["num_repetitions"]):
            for example in data:
                outputs = target(dict(example.inputs))
                run = SimpleNamespace(outputs=outputs)
                for evaluator in evaluators:
                    scores = evaluator(run, example)
                    path = self.export_dir / "scores" / f"{outputs['run_id']}.json"
                    with self.lock:
                        self.scores.append(scores)
                        self.exported_before_return.append(path.exists())
                rows.append({"run": run})
        prefix = kwargs["experiment_prefix"]
        return Results(
            experiment_name=f"{prefix}-0001",
            comparison_url=f"https://smith.example/compare/{prefix}",
            url=f"https://smith.example/exp/{prefix}",
            rows=rows,
        )


class Results(SimpleNamespace):
    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.rows)


def example() -> SimpleNamespace:
    return SimpleNamespace(
        id="ex-1", inputs=LINE["inputs"], outputs=LINE["outputs"], metadata=LINE["metadata"]
    )


def test_experiments_run_both_arms_with_k_repetitions_and_export_scores(
    course_repo: Path, tmp_path: Path
) -> None:
    deps = make_deps(course_repo, tmp_path, Clients())
    deps.client_factory = lambda arm: Clients()(arm)  # a fresh script per run
    client = FakeLangSmith([example()])
    fake = FakeEvaluate(tmp_path / "exports")
    evaluate = fake

    plan = ExperimentPlan(
        dataset="teamtrack-features-v1",
        split="section-1",
        k=2,
        harness_layers=frozenset({"instructions"}),
        batch="batch-1",
        day="2026-10-16",
    )
    exports = run_experiments(plan, deps, client, evaluate_fn=evaluate)
    assert set(exports) == {"bare", "harness"}
    assert client.list_calls == [{"dataset_name": "teamtrack-features-v1", "splits": ["section-1"]}]
    prefixes = sorted(c["experiment_prefix"] for c in fake.calls)
    assert prefixes == [
        "shipharness-batch-1-bare-2026-10-16",
        "shipharness-batch-1-harness-2026-10-16",
    ]
    assert all(c["num_repetitions"] == 2 for c in fake.calls)
    assert {c["metadata"]["model"] for c in fake.calls} == {deps.settings.openai_model}
    # one combined evaluator, 12 scores, ScoreRecord on disk before it returned
    assert all([s["key"] for s in scores] == list(SCORE_KEYS) for scores in fake.scores)
    assert fake.exported_before_return == [True] * 4
    scores = read_exports("scores", tmp_path / "exports")
    assert len(scores) == 4 and {s["arm"] for s in scores} == {"bare", "harness"}
    experiments = read_exports("experiments", tmp_path / "exports")
    assert {e["arm"] for e in experiments} == {"bare", "harness"}
    harness = next(e for e in experiments if e["arm"] == "harness")
    assert harness["k"] == 2 and len(harness["rows"]) == 2
    assert harness["comparison_url"].startswith("https://smith.example/compare/")
    assert harness["stats"]["passed_primary"] == "2/2"
    assert harness["metadata"]["layers"] == ["instructions"]


def test_a_relative_runs_dir_still_lets_the_referee_apply_the_patch(
    course_repo: Path, tmp_path: Path, monkeypatch: Any
) -> None:
    # The CLI's default RUNS_DIR is relative (".shipharness/runs") and `shipharness experiments`
    # sets no workspace base, so the referee's product.patch path was relative. `git apply` runs in
    # the referee build folder, could not open it, and every run of an experiment was unjudged
    # (hidden 0, "referee could not judge the build"). Bug fix, applies to both arms.
    # The referee side is tested in test_referee.py
    # (test_a_relative_referee_dir_still_applies_the_patch).
    from shipharness.ab.experiments import ArmExperiment, _example_task
    from shipharness.config import Settings

    monkeypatch.chdir(tmp_path)
    deps = make_deps(course_repo, tmp_path, Clients(), workspace_base=None)
    deps.settings = Settings(
        _env_file=None, runs_dir=Path(".shipharness/runs"), exports_dir=tmp_path / "exports"
    )
    plan = ExperimentPlan(dataset="d", k=1, harness_layers=frozenset({"instructions"}))
    for arm in ("bare", "harness"):
        experiment = ArmExperiment(arm, plan, deps, [example()])  # type: ignore[arg-type]
        referee = experiment._referee(_example_task(example()))
        assert referee.deps.base_dir.is_absolute(), referee.deps.base_dir
        assert referee.deps.base_dir.is_relative_to(tmp_path.resolve() / ".shipharness" / "runs")


def test_target_outputs_carry_no_host_paths(course_repo: Path, tmp_path: Path) -> None:
    deps = make_deps(course_repo, tmp_path, Clients())
    deps.client_factory = lambda arm: Clients()(arm)
    seen: list[dict[str, Any]] = []

    def evaluate(target: Any, *, data: Any, evaluators: list[Any], **kwargs: Any) -> Any:
        for ex in data:
            out = target(dict(ex.inputs))
            seen.append(out)
            evaluators[0](SimpleNamespace(outputs=out), ex)
        return Results(rows=[], experiment_name=kwargs["experiment_prefix"])

    plan = ExperimentPlan(dataset="d", k=1, harness_layers=frozenset({"instructions"}))
    run_experiments(plan, deps, FakeLangSmith([example()]), evaluate_fn=evaluate)
    text = repr(seen)
    assert str(tmp_path) not in text and "\\" not in text


def test_attach_scores_never_extends_trace_retention(tmp_path: Path) -> None:
    from .score_fixtures import record

    client = FakeLangSmith([])
    url = "https://smith.langchain.com/o/x/projects/p/y/r/0b8f1f6e-3c1a-4b9e-9a51-2a1f0c3d4e5f"
    assert attach_scores(client, url, record()) == 12
    assert all(f["extend_trace_retention"] is False for f in client.feedback)
    assert {f["run_id"] for f in client.feedback} == {"0b8f1f6e-3c1a-4b9e-9a51-2a1f0c3d4e5f"}
    assert attach_scores(client, None, record()) == 0


def test_experiment_summary_records_each_checkpoint_commit(
    course_repo: Path, tmp_path: Path
) -> None:
    import subprocess

    sha = subprocess.run(
        ["git", "rev-parse", "m1-s1-start^{commit}"],
        cwd=course_repo, capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip
    deps = make_deps(course_repo, tmp_path, Clients())
    deps.client_factory = lambda arm: Clients()(arm)
    plan = ExperimentPlan(
        dataset="teamtrack-features-v1",
        split="section-1",
        k=1,
        harness_layers=frozenset({"instructions"}),
        batch="batch-1",
        day="2026-10-16",
    )
    exports = run_experiments(
        plan, deps, FakeLangSmith([example()]), evaluate_fn=FakeEvaluate(tmp_path / "exports")
    )
    for export in exports.values():
        assert export["checkpoint_shas"] == {"m1-s1-start": sha}
    rows = read_exports("scores", tmp_path / "exports")
    assert rows and {row["checkpoint_sha"] for row in rows} == {sha}
