"""Control tasks C1-C8: manifests, specs for both arms (ruling R-4), the referee on the reference.

The slow tests have the shape of B-features' proof for F1-F7: with the reference applied, the rule
checks (R1-R7), the existing tests, and the hidden tests report no new violations against the
checkpoint's own baseline; without it, at least 90% of the hidden tests fail (R-7); every referee
mutant applies to the start checkpoint and is killed by the reference's own visible tests (R-2).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

from shipharness.ab import checkpoints
from shipharness.ab.mutants import load_referee_mutants
from shipharness.datasets.features_checks import hidden_test_ids
from shipharness.filters.mutants import check_against_source, run_mutant_detailed
from shipharness.layout import find_repo_root
from tests.unit.filters.helpers import PY, local_sandbox

REPO = find_repo_root(Path(__file__))
TT = REPO / "platform" / "teamtrack"
CONTROLS = [f"c{n}" for n in range(1, 9)]
RULES = ["r1_tenant", "r2_roles", "r3_conventions", "r4_idempotency", "r5_audit"]
RULES += ["r6_layering", "r7_migrations"]
START = "m1-s1-start"


def manifest(task: str) -> dict[str, Any]:
    return tomllib.loads((TT / "reference" / task / "task.toml").read_text(encoding="utf-8"))


def patch_path(task: str) -> Path:
    return TT / "reference" / task / f"{task}.patch"


def touched_files(task: str) -> list[str]:
    text = patch_path(task).read_text(encoding="utf-8")
    return re.findall(r"^\+\+\+ b/(\S+)$", text, flags=re.MULTILINE)


def new_visible_tests(task: str) -> list[str]:
    text = patch_path(task).read_text(encoding="utf-8")
    return re.findall(r"^\+\+\+ b/(tests/visible/test_\S+\.py)$", text, flags=re.MULTILINE)


# -- fast checks --------------------------------------------------------------------------------


@pytest.mark.parametrize("task", CONTROLS)
def test_manifest_describes_a_control_on_the_base_checkpoint(task: str) -> None:
    data = manifest(task)
    assert data["id"] == task.upper()
    assert data["section"] == "control"
    assert data["start_checkpoint"] == START
    assert data["primary_measure"] == ""
    assert data["session_budget"] and all(n > 0 for n in data["session_budget"])
    assert data["canonical_ticket"].strip()
    assert f"docs/features/{task}.md" in data["canonical_ticket"]
    assert set(data["allowed_paths"]) == {"build", "test"}
    assert data["allowed_paths"]["test"] == ["tests/visible/**"]
    assert "tests/visible/**" in data["allowed_paths"]["build"]
    assert list(data["hidden"]) == [START]
    assert patch_path(task).is_file()


@pytest.mark.parametrize("task", CONTROLS)
def test_spec_is_the_same_for_both_arms(task: str) -> None:
    shared = TT / "docs" / "features" / f"{task}.md"
    harness = TT / "harness" / "instructions" / "docs" / "product-specs" / f"{task}.md"
    assert shared.read_bytes() == harness.read_bytes()


@pytest.mark.parametrize("task", CONTROLS)
def test_hidden_tests_follow_the_referee_rules(task: str) -> None:
    files = manifest(task)["hidden"][START]
    ids = hidden_test_ids(REPO, files)
    assert len(ids) >= 6
    for rel in files:
        text = (TT / rel).read_text(encoding="utf-8")
        assert rel.startswith(f"tests/hidden/{task}/test_{task}_")  # unique module names
        assert "from hidden_support import" in text
        assert "conftest" not in text.replace("tests/hidden/conftest.py", "")
        assert "tests/visible" not in text and "tests.visible" not in text


@pytest.mark.parametrize("task", CONTROLS)
def test_reference_adds_visible_tests_and_no_hidden_or_harness_files(task: str) -> None:
    touched = touched_files(task)
    assert new_visible_tests(task)
    assert all(not p.startswith(("tests/hidden/", "harness/", "reference/")) for p in touched)
    allowed = manifest(task)["allowed_paths"]["build"]
    for path in touched:
        assert any(Path(path).match(glob) or path.startswith(glob[:-2]) for glob in allowed), path


@pytest.mark.parametrize("task", CONTROLS)
def test_referee_mutant_set_is_not_in_a_file_the_reference_changes(task: str) -> None:
    mutants = load_referee_mutants(manifest(task)["mutant_set"], REPO)
    touched = set(touched_files(task))
    assert mutants
    assert not {m.file for m in mutants} & touched


# -- slow: the referee on the reference --------------------------------------------------------


def materialize(dest: Path, task: str | None) -> Path:
    """The start checkpoint plus, when given, the control's reference patch."""
    checkpoints.materialize(REPO, START, dest)
    if task is not None:
        checkpoints.apply_reference(task, START, dest, REPO)
    return dest


def add_hidden(build: Path, task: str) -> None:
    hidden = build / "tests" / "hidden"
    hidden.mkdir(parents=True, exist_ok=True)
    for name in ("conftest.py", "hidden_support.py"):
        shutil.copy2(TT / "tests" / "hidden" / name, hidden / name)
    shutil.copytree(TT / "tests" / "hidden" / task, hidden / task)


def run_checks(
    build: Path, checks: list[str], params: dict[str, Any], tmp: Path, **kw: Path
) -> Any:
    params_file = tmp / "params.json"
    params_file.write_text(json.dumps({"r3_max_examples": 5, **params}), encoding="utf-8")
    args = [sys.executable, "-m", "shipharness.checks.runner", "--build", str(build)]
    args += ["--checks", ",".join(checks), "--checkpoint", START, "--feature", "control"]
    args += ["--seed", "7", "--params", str(params_file)]
    if "baseline" in kw:
        args += ["--baseline", str(kw["baseline"])]
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=900)
    assert proc.stdout.strip(), proc.stderr[-2000:]
    return json.loads(proc.stdout)["results"]


@pytest.fixture(scope="module")
def baseline(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("baseline")
    build = materialize(tmp / "teamtrack", None)
    results = run_checks(build, RULES, {}, tmp)
    path = tmp / "baseline.json"
    path.write_text(json.dumps({"results": results}), encoding="utf-8")
    return path


def hidden_ids(task: str) -> list[str]:
    return hidden_test_ids(REPO, manifest(task)["hidden"][START])


@pytest.mark.slow
@pytest.mark.parametrize("task", CONTROLS)
def test_reference_passes_the_referee(task: str, baseline: Path, tmp_path: Path) -> None:
    build = materialize(tmp_path / "teamtrack", task)
    add_hidden(build, task)
    ids = hidden_ids(task)
    checks = [*RULES, "regression", "hidden_tests"]
    results = run_checks(build, checks, {"hidden_tests": ids}, tmp_path, baseline=baseline)
    by_check = {r["check"]: r for r in results}
    assert list(by_check) == checks
    failing = {
        name: [f["detail"] for f in r["findings"] if not f["baseline"] and f["severity"] != "info"]
        for name, r in by_check.items()
        if not r["passed"]
    }
    assert failing == {}
    assert by_check["hidden_tests"]["total_probes"] == len(ids)
    assert by_check["regression"]["total_probes"] > 140  # existing tests plus the control's own


@pytest.mark.slow
@pytest.mark.parametrize("task", CONTROLS)
def test_hidden_tests_fail_on_the_start_checkpoint(task: str, tmp_path: Path) -> None:
    build = materialize(tmp_path / "teamtrack", None)
    add_hidden(build, task)
    ids = hidden_ids(task)
    (result,) = run_checks(build, ["hidden_tests"], {"hidden_tests": ids}, tmp_path)
    failed = {f["detail_key"] for f in result["findings"]}
    assert len(failed) >= 0.9 * len(ids), sorted(set(ids) - {k[5:] for k in failed})


@pytest.mark.slow
@pytest.mark.parametrize("task", CONTROLS)
def test_referee_mutants_apply_and_are_killed_by_the_reference_tests(
    task: str, tmp_path: Path
) -> None:
    base = materialize(tmp_path / "base", None)
    build = materialize(tmp_path / "teamtrack", task)
    tests = new_visible_tests(task)
    outcomes = {}
    for mutant in load_referee_mutants(manifest(task)["mutant_set"], REPO):
        check_against_source(mutant, base)  # applies to the start checkpoint
        result = run_mutant_detailed(mutant, tests, build, local_sandbox(build), 180, python=PY)
        outcomes[mutant.id] = result.outcome if result.outcome == "killed" else result.detail
    assert outcomes and set(outcomes.values()) == {"killed"}, outcomes
