"""Every (task, checkpoint) pair of the F manifests, judged the way the referee judges an arm.

For each pair: the checkpoint materializes; the reference applies; with the reference, R1-R7,
existing tests (`regression`), and hidden tests report no new violations against the checkpoint's
own baseline, and every hidden test passes; without it, at least 90% of the hidden tests fail and
the rest are guards (ruling R-7). Every referee mutant of the task's set applies (its original
matches exactly one line) at every pair, to the checkpoint and to the reference build, and is killed
by the visible tests the reference ships for that checkpoint (ruling R-2). Filter mutants are killed
the same way at the start checkpoint.
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from shipharness.ab import checkpoints as cp
from shipharness.ab.mutants import load_referee_mutants
from shipharness.checks._pytest import run_pytest
from shipharness.checks.runner import run_checks
from shipharness.config.prices import REPO_ROOT
from shipharness.filters.mutants import Mutant, apply_mutant, check_against_source, load_mutants
from tests.unit.features import support

RULE_CHECKS = [
    "r1_tenant",
    "r2_roles",
    "r3_conventions",
    "r4_idempotency",
    "r5_audit",
    "r6_layering",
    "r7_migrations",
]
SEED = 20261016
MUTANT_DIR = REPO_ROOT / "platform" / "teamtrack" / "mutants" / "features"


@pytest.fixture(autouse=True)
def _restore_app_modules() -> Iterator[None]:
    """Checks import each build's `app` package; put the bundled TeamTrack modules back after."""
    saved = {k: v for k, v in sys.modules.items() if k == "app" or k.startswith("app.")}
    path = list(sys.path)
    yield
    for name in [k for k in sys.modules if k == "app" or k.startswith("app.")]:
        del sys.modules[name]
    sys.modules.update(saved)
    sys.path[:] = path


def _pair_id(pair: tuple[str, str]) -> str:
    return f"{pair[0]}@{pair[1]}"


@pytest.mark.slow
@pytest.mark.parametrize("pair", support.pairs(), ids=_pair_id)
def test_reference_passes_the_referee_checks(pair: tuple[str, str], tmp_path: Path) -> None:
    task, checkpoint = pair
    files = cp.load_task(task).hidden[checkpoint]
    ids = support.test_ids(files)

    start = support.build(task, checkpoint, tmp_path / "start", reference=False)
    support.install_hidden(start, files)
    existing = support.visible_ids(start)
    baseline_results, crashed = run_checks(
        start,
        [*RULE_CHECKS, "hidden_tests"],
        checkpoint=checkpoint,
        feature_id=task.upper(),
        seed=SEED,
        params={"hidden_tests": ids},
    )
    assert not crashed
    baseline = {r.check: r for r in baseline_results}

    # R-7: at least 90% of the hidden tests fail at the start; only guards may pass.
    hidden_start = baseline["hidden_tests"]
    failing = {f.detail_key.removeprefix("test:") for f in hidden_start.findings if f.counted}
    passing = [i for i in ids if i not in failing]
    assert len(failing) >= 0.9 * len(ids), (len(failing), len(ids))
    assert all(f"/test_{task}_guards.py::" in i for i in passing), passing

    built = support.build(task, checkpoint, tmp_path / "ref", reference=True)
    support.install_hidden(built, files)
    results, crashed = run_checks(
        built,
        [*RULE_CHECKS, "regression", "hidden_tests"],
        checkpoint=checkpoint,
        feature_id=task.upper(),
        seed=SEED,
        params={"hidden_tests": ids, "regression_expected": existing},
        baseline=baseline,
    )
    assert not crashed
    by_check = {r.check: r for r in results}
    problems = {
        r.check: [f.detail for f in r.findings if f.counted and not f.baseline][:5]
        for r in results
        if not r.passed
    }
    assert problems == {}
    hidden = by_check["hidden_tests"]
    assert hidden.total_probes == len(ids)
    assert [f.detail for f in hidden.findings if f.counted] == []  # every hidden test passes
    assert by_check["regression"].total_probes >= len(existing)


def _killed(built: Path, tests: list[str], m: Mutant) -> bool:
    """Apply `m` to the build (found by its text; raises unless it matches exactly one line), run
    the reference's visible tests, and put the file back."""
    target = built / m.file
    original = target.read_bytes()
    target.write_bytes(apply_mutant(original.decode("utf-8"), m).encode("utf-8"))
    try:
        mutated = run_pytest(built, tests)
    finally:
        target.write_bytes(original)
    return bool(mutated.failed) or mutated.returncode != 0


@pytest.mark.slow
@pytest.mark.parametrize("pair", support.pairs(), ids=_pair_id)
def test_referee_mutants_apply_and_are_killed_at_every_pair(
    pair: tuple[str, str], tmp_path: Path
) -> None:
    """Every referee mutant applies at every (task, checkpoint) pair the manifest runs, both to
    the checkpoint and to the reference build there, and the reference's visible tests for that
    checkpoint kill it (R-2, re-validated at alternate checkpoints)."""
    task, checkpoint = pair
    referee = load_referee_mutants(cp.load_task(task).mutant_set, REPO_ROOT)
    assert referee
    start = support.build(task, checkpoint, tmp_path / "start", reference=False)
    for m in referee:
        check_against_source(m, start)  # exactly one matching line at the checkpoint
    built = support.build(task, checkpoint, tmp_path / "ref", reference=True)
    tests = support.reference_test_files(task, checkpoint)
    assert tests, "the reference ships no visible tests"
    clean = run_pytest(built, tests)
    assert clean.outcomes and not clean.failed, clean.failed
    survived = [m.id for m in referee if not _killed(built, tests, m)]
    assert survived == [], f"survived the reference tests at {checkpoint}"


def _filter_cases() -> list[tuple[str, str]]:
    return [
        (task, m.id)
        for task in support.FEATURES
        for m in load_mutants(MUTANT_DIR / f"{task}.jsonl", None)
        if m.set == "filter"
    ]


@pytest.mark.slow
@pytest.mark.parametrize(("task", "mutant_id"), _filter_cases(), ids=lambda v: str(v))
def test_feature_filter_mutants_are_killed_by_the_reference_tests(
    task: str, mutant_id: str, tmp_path: Path
) -> None:
    start_name = cp.load_task(task).start_checkpoint
    start = cp.materialize(REPO_ROOT, start_name, tmp_path / "start")
    mutant = next(m for m in load_mutants(MUTANT_DIR / f"{task}.jsonl", start) if m.id == mutant_id)
    built = support.build(task, start_name, tmp_path / "ref", reference=True)
    tests = support.reference_test_files(task, start_name)
    assert tests, "the reference ships no visible tests"
    clean = run_pytest(built, tests)
    assert clean.outcomes and not clean.failed, clean.failed
    assert _killed(built, tests, mutant), f"{mutant.id} survived the reference tests"
    shutil.rmtree(built, ignore_errors=True)
