"""F task manifests, specs (R-4), hidden test files (R-1, R-7), and feature mutants (R-2)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from shipharness.ab import checkpoints as cp
from shipharness.ab.artifacts import glob_match
from shipharness.ab.mutants import load_referee_mutants
from shipharness.ab.score import ScoreRecord, evaluate_primary
from shipharness.config.prices import REPO_ROOT
from shipharness.filters.mutants import load_mutants
from tests.unit.features import support

TEAMTRACK = REPO_ROOT / "platform" / "teamtrack"
SPECS = TEAMTRACK / "docs" / "features"
HARNESS_SPECS = TEAMTRACK / "harness" / "instructions" / "docs" / "product-specs"
PRIMARY = {  # ruling R-5
    "f1": "r1_new_violations>=1",
    "f2": "continuity_failure",
    "f3": "out_of_scope_files>=1 or test_phase_source_edits>=1",
    "f4": "hidden_passed,mutants_killed",
    "f5": "",
    "f6": "",
    "f7": "",
}
START = {
    "f1": "m1-s1-start",
    "f2": "m1-s2-start",
    "f3": "m1-s3-start",
    "f4": "m1-s4-start",
    "f5": "m1-final-start",
    "f6": "m1-final-start",
    "f7": "m1-final-start",
}
TWO_SESSIONS = {"f2", "f6", "f7"}


@pytest.fixture(params=support.FEATURES)
def task(request: pytest.FixtureRequest) -> cp.TaskManifest:
    return cp.load_task(request.param)


def test_task_names_cover_f1_to_f7() -> None:
    assert cp.task_names(prefix="f") == support.FEATURES


def test_manifest_basics(task: cp.TaskManifest) -> None:
    assert task.id == task.task.upper()
    assert task.start_checkpoint == START[task.task]
    assert task.start_checkpoint in task.hidden
    assert set(task.hidden) <= set(cp.load_checkpoints())
    assert task.canonical_ticket.strip()
    assert f"docs/features/{task.task}.md" in task.canonical_ticket
    assert len(task.session_budget) == (2 if task.task in TWO_SESSIONS else 1)
    if len(task.session_budget) == 2:
        assert task.session_budget[0] < task.session_budget[1]


def test_alternate_checkpoints_for_f1_to_f4(task: cp.TaskManifest) -> None:
    expected = {task.start_checkpoint}
    if task.task in {"f1", "f2", "f3", "f4"}:
        expected |= {"m1-alt-a", "m1-alt-b"}
    assert set(task.hidden) == expected


def test_primary_measure_follows_r5(task: cp.TaskManifest) -> None:
    assert task.primary_measure == PRIMARY[task.task]
    fields = {name: 0 for name in ScoreRecord.model_fields}
    fields.update(continuity_failure=False, hidden_total=0, mutants_total=0)
    evaluate_primary(task.primary_measure, fields)  # every name is a ScoreRecord field


def test_allowed_paths_cover_the_reference(task: cp.TaskManifest) -> None:
    globs = task.allowed_paths["build"]
    assert task.allowed_paths["test"] == ["tests/visible/**"]
    for checkpoint in task.hidden:
        text = cp.patch_for(task.task, checkpoint).read_text(encoding="utf-8")
        paths = set(re.findall(r"^\+\+\+ b/(\S+)", text, re.MULTILINE))
        outside = sorted(p for p in paths if not any(glob_match(p, g) for g in globs))
        assert outside == [], (checkpoint, outside)
    assert not any(glob_match("app/api/middleware.py", g) for g in globs)


def test_reference_patches_name_known_checkpoints(task: cp.TaskManifest) -> None:
    folder = TEAMTRACK / "reference" / task.task
    names = set(cp.load_checkpoints())
    for patch in folder.glob(f"{task.task}.*.patch"):
        assert patch.name.removeprefix(f"{task.task}.").removesuffix(".patch") in names


# -- hidden test files ------------------------------------------------------------------------


def test_hidden_files_exist_and_follow_the_naming_rules(task: cp.TaskManifest) -> None:
    checkpoints = cp.load_checkpoints()
    for checkpoint, files in task.hidden.items():
        for rel in files:
            assert (TEAMTRACK / rel).is_file(), rel
            assert rel.startswith(f"tests/hidden/{task.task}/test_{task.task}_"), rel
            other = re.fullmatch(rf"tests/hidden/{task.task}/test_{task.task}_with_(f\d)\.py", rel)
            if other:  # combined tests only where the other feature exists (R-7)
                assert other.group(1) in checkpoints[checkpoint].tasks, (checkpoint, rel)
        guards = f"tests/hidden/{task.task}/test_{task.task}_guards.py"
        assert guards in files


def test_every_hidden_file_is_used(task: cp.TaskManifest) -> None:
    listed = {rel for files in task.hidden.values() for rel in files}
    present = {
        p.relative_to(TEAMTRACK).as_posix()
        for p in (TEAMTRACK / "tests" / "hidden" / task.task).glob("*.py")
    }
    assert present == listed


def test_hidden_basenames_are_unique_and_there_are_no_packages() -> None:
    hidden = TEAMTRACK / "tests" / "hidden"
    names = [p.name for p in hidden.glob("*/test_*.py")]
    assert len(names) == len(set(names))
    assert not list(hidden.glob("*/__init__.py"))


def test_hidden_tests_are_plain_functions(task: cp.TaskManifest) -> None:
    for rel in {r for files in task.hidden.values() for r in files}:
        source = (TEAMTRACK / rel).read_text(encoding="utf-8")
        tree = ast.parse(source)
        assert "parametrize" not in source, rel  # the referee looks up file::name ids
        assert not [n for n in tree.body if isinstance(n, ast.ClassDef)], rel
        imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
        assert "conftest" not in imports and not any("visible" in m for m in imports), rel


def test_hidden_test_counts(task: cp.TaskManifest) -> None:
    for checkpoint, files in task.hidden.items():
        ids = support.test_ids(files)
        guards = [i for i in ids if f"test_{task.task}_guards.py::" in i]
        assert len(ids) >= 40, (checkpoint, len(ids))
        assert len(guards) <= 0.1 * len(ids), (checkpoint, len(guards), len(ids))


def test_hidden_ids_are_unique(task: cp.TaskManifest) -> None:
    for files in task.hidden.values():
        ids = support.test_ids(files)
        assert len(ids) == len(set(ids))


# -- specs (R-4) --------------------------------------------------------------------------------


def test_specs_exist_in_both_places_byte_for_byte(task: cp.TaskManifest) -> None:
    spec = SPECS / f"{task.task}.md"
    mirror = HARNESS_SPECS / f"{task.task}.md"
    assert spec.read_bytes() == mirror.read_bytes()


def test_product_spec_index_lists_every_feature() -> None:
    index = (HARNESS_SPECS / "index.md").read_text(encoding="utf-8")
    for name in support.FEATURES:
        assert f"]({name}.md)" in index


def test_specs_are_exported_to_both_arms() -> None:
    from shipharness.ab.workspace import excluded

    assert not excluded("docs/features/f1.md")
    assert excluded("reference/f1/f1.patch")
    assert excluded("tests/hidden/f1/test_f1_search.py")


# -- mutants (R-2) ------------------------------------------------------------------------------


def test_mutant_set_resolves_to_a_referee_set(task: cp.TaskManifest) -> None:
    referee = load_referee_mutants(task.mutant_set, REPO_ROOT)
    assert len(referee) >= 3
    assert task.mutant_set == f"features/{task.task}"


def test_mutants_apply_to_the_start_checkpoint(task: cp.TaskManifest, tmp_path: Path) -> None:
    start = cp.materialize(REPO_ROOT, task.start_checkpoint, tmp_path / "start")
    mutants = load_mutants(TEAMTRACK / "mutants" / "features" / f"{task.task}.jsonl", start)
    assert {m.set for m in mutants} == {"filter", "referee"}


def test_mutant_ids_are_unique_across_teamtrack() -> None:
    ids: list[str] = []
    for path in (TEAMTRACK / "mutants").rglob("*.jsonl"):
        ids += [m.id for m in load_mutants(path, None)]
    assert len(ids) == len(set(ids))
