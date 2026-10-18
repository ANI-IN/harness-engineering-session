"""features_checks: per-line checks against the course repository, and whole-file checks."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from shipharness.datasets.features_checks import (
    GROUP_COUNTS,
    SPLIT_SIZES,
    check_features_file,
    check_features_line,
    check_mutants_apply,
    checkpoint_names,
    checkpoint_tree,
    collect_tests,
)
from shipharness.layout import find_repo_root

from .features_fixtures import make_repo


@pytest.fixture(scope="module")
def repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_repo(tmp_path_factory.mktemp("course"), real_sources=False)


def f1_line() -> dict[str, Any]:
    return {
        "inputs": {
            "feature_id": "F1",
            "checkpoint": "m1-s1-start",
            "ticket_text": "Fixture canonical ticket for F1.",
            "variant": "canonical",
            "session_budget": [30],
        },
        "outputs": {
            "hidden_test_ids": [
                "tests/hidden/f1/test_f1_fixture.py::test_f1_one",
                "tests/hidden/f1/test_f1_fixture.py::test_f1_two",
            ],
            "allowed_paths": {"build": ["app/api/issues.py"], "test": ["tests/visible/**"]},
            "mutant_set": "features/f1",
            "primary_measure": "r1_new_violations>=1",
        },
        "metadata": {"group": "canonical", "example_id": "F1-canonical", "control": False},
        "split": ["section-1", "smoke"],
    }


def with_change(path: str, value: Any) -> dict[str, Any]:
    line = copy.deepcopy(f1_line())
    target = line
    keys = path.split(".")
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value
    return line


def test_a_valid_line_passes(repo: Path) -> None:
    assert check_features_line(f1_line(), repo) == []


def test_schema_errors_are_reported_not_raised(repo: Path) -> None:
    line = f1_line()
    del line["outputs"]["primary_measure"]
    errors = check_features_line(line, repo)
    assert errors and "primary_measure" in errors[0]


def test_checkpoint_must_be_defined_in_checkpoints_toml(repo: Path) -> None:
    errors = check_features_line(with_change("inputs.checkpoint", "m1-s9-start"), repo)
    assert any("m1-s9-start" in e and "checkpoints.toml" in e for e in errors)


def test_checkpoint_names_reads_the_checkpoints_table(repo: Path) -> None:
    assert {"m1-s1-start", "m1-alt-a", "m1-alt-b", "m1-complete"} <= checkpoint_names(repo)


def test_checkpoint_names_uses_the_checkpoints_module(tmp_path: Path) -> None:
    path = tmp_path / "teamtrack" / "reference" / "checkpoints.toml"
    path.parent.mkdir(parents=True)
    path.write_text('[checkpoints."m1-s1-start"]\ntasks = []\n', encoding="utf-8")
    assert checkpoint_names(tmp_path) == {"m1-s1-start"}


def test_missing_checkpoints_toml_is_an_error(tmp_path: Path) -> None:
    errors = check_features_line(f1_line(), tmp_path)
    assert any("checkpoints.toml" in e for e in errors)


def test_hidden_ids_must_exist_in_their_files(repo: Path) -> None:
    ids = ["tests/hidden/f1/test_f1_fixture.py::test_missing"]
    errors = check_features_line(with_change("outputs.hidden_test_ids", ids), repo)
    assert any("test_missing" in e for e in errors)


def test_hidden_file_must_exist(repo: Path) -> None:
    ids = ["tests/hidden/f1/test_nowhere.py::test_f1_one"]
    errors = check_features_line(with_change("outputs.hidden_test_ids", ids), repo)
    assert any("test_nowhere.py" in e for e in errors)


def test_hidden_ids_are_relative_to_the_teamtrack_root(repo: Path) -> None:
    ids = ["teamtrack/tests/hidden/f1/test_f1_fixture.py::test_f1_one"]
    errors = check_features_line(with_change("outputs.hidden_test_ids", ids), repo)
    assert any("tests/hidden/" in e for e in errors)


def test_feature_lines_need_hidden_ids(repo: Path) -> None:
    errors = check_features_line(with_change("outputs.hidden_test_ids", []), repo)
    assert any("hidden" in e for e in errors)


def test_parametrized_hidden_tests_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "test_p.py"
    path.write_text(
        "import pytest\n\n\n@pytest.mark.parametrize('x', [1, 2])\ndef test_p(x):\n    pass\n\n\n"
        "def test_plain():\n    pass\n\n\nclass TestGroup:\n    def test_inner(self):\n"
        "        pass\n",
        encoding="utf-8",
    )
    expected = {"test_p": True, "test_plain": False, "TestGroup::test_inner": False}
    assert collect_tests(path) == expected


def test_mutant_set_must_resolve_to_referee_mutants(repo: Path) -> None:
    errors = check_features_line(with_change("outputs.mutant_set", "features/nope"), repo)
    assert any("features/nope" in e for e in errors)


def test_mutant_set_without_referee_mutants_is_an_error(repo: Path) -> None:
    filter_only = repo / "teamtrack" / "mutants" / "features" / "filteronly.jsonl"
    filter_only.write_text(
        '{"id": "features.filteronly-m1", "target": "features.filteronly", "set": "filter", '
        '"file": "app/x.py", "line": 1, "original": "a", "replacement": "b", "rationale": "r"}\n',
        encoding="utf-8",
    )
    errors = check_features_line(with_change("outputs.mutant_set", "features/filteronly"), repo)
    assert any("no referee mutants" in e for e in errors)


@pytest.mark.parametrize(
    "measure",
    ["r1_new_violation>=1", "r1_new_violations=>1", "nonsense", "hidden_passed,unknown_field"],
)
def test_primary_measure_must_parse_against_score_record(repo: Path, measure: str) -> None:
    errors = check_features_line(with_change("outputs.primary_measure", measure), repo)
    assert any("primary_measure" in e for e in errors)


def test_primary_measure_follows_the_registered_measure_for_the_feature(repo: Path) -> None:
    errors = check_features_line(with_change("outputs.primary_measure", "continuity_failure"), repo)
    assert any("R-5" in e for e in errors)


def test_bare_primary_field_must_be_boolean(repo: Path) -> None:
    line = with_change("outputs.primary_measure", "hidden_passed")
    assert any("boolean" in e for e in check_features_line(line, repo))


@pytest.mark.parametrize(
    "paths",
    [
        {"build": [], "test": ["tests/visible/**"]},
        {"build": ["app/api/issues.py"]},
        {"build": ["/app/api/issues.py"], "test": ["tests/visible/**"]},
        {"build": ["../app.py"], "test": ["tests/visible/**"]},
        {"build": ["app\\api.py"], "test": ["tests/visible/**"]},
        {"build": [""], "test": ["tests/visible/**"]},
    ],
)
def test_allowed_paths_are_non_empty_relative_globs(repo: Path, paths: dict[str, Any]) -> None:
    errors = check_features_line(with_change("outputs.allowed_paths", paths), repo)
    assert any("allowed_paths" in e for e in errors)


# -- referee mutants apply at the line's checkpoint (M5 fix pass) ---------------

SOURCE = "def f():\n    return 1\n"
MUTANT = {
    "id": "app.x-m1",
    "target": "app.x",
    "set": "referee",
    "file": "app/x.py",
    "line": 2,
    "original": "    return 1",
    "replacement": "    return 0",
    "rationale": "wrong value",
}
PATCHES = {  # task -> patch against the base app/x.py
    "t1": "@@ -1,2 +1,4 @@\n+import os\n+\n def f():\n     return 1\n",  # moves the line down
    "t2": "@@ -1,2 +1,2 @@\n def f():\n-    return 1\n+    return 2\n",  # removes the original
    "t3": "@@ -1,2 +1,6 @@\n def f():\n     return 1\n+\n+\n+def g():\n+    return 1\n",
}


@pytest.fixture
def app_repo(tmp_path: Path) -> Path:
    """A course repository with TeamTrack source: base app/x.py and checkpoints c-one..c-three."""
    tt = tmp_path / "teamtrack"
    (tt / "app").mkdir(parents=True)
    (tt / "app" / "x.py").write_text(SOURCE, encoding="utf-8")
    ref = tt / "reference"
    toml = ['[checkpoints."c-base"]\ntasks = []\n']
    for n, (task, hunk) in enumerate(PATCHES.items(), start=1):
        (ref / task).mkdir(parents=True)
        header = "diff --git a/app/x.py b/app/x.py\n--- a/app/x.py\n+++ b/app/x.py\n"
        (ref / task / f"{task}.patch").write_text(header + hunk, encoding="utf-8")
        toml.append(f'[checkpoints."c-{["one", "two", "three"][n - 1]}"]\ntasks = ["{task}"]\n')
    (ref / "checkpoints.toml").write_text("\n".join(toml), encoding="utf-8")
    (tt / "mutants" / "features").mkdir(parents=True)
    (tt / "mutants" / "features" / "fx.jsonl").write_text(json.dumps(MUTANT) + "\n", "utf-8")
    return tmp_path


def test_referee_mutants_apply_by_text_at_the_checkpoint(app_repo: Path) -> None:
    assert check_mutants_apply("features/fx", "c-base", app_repo) == []
    assert check_mutants_apply("features/fx", "c-one", app_repo) == []  # line 2 is now line 4


def test_a_mutant_whose_original_is_gone_at_the_checkpoint_is_reported(app_repo: Path) -> None:
    errors = check_mutants_apply("features/fx", "c-two", app_repo)
    assert len(errors) == 1
    assert "app.x-m1" in errors[0] and "c-two" in errors[0] and "not found" in errors[0]


def test_a_mutant_that_matches_several_lines_is_reported(app_repo: Path) -> None:
    errors = check_mutants_apply("features/fx", "c-three", app_repo)
    assert len(errors) == 1 and "matches 2 lines" in errors[0]


def test_each_checkpoint_is_materialized_once(
    app_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from shipharness.ab import checkpoints as cp

    calls: list[str] = []
    real = cp.materialize

    def counting(repo: Path, name: str, dest: Path) -> Path:
        calls.append(name)
        return real(repo, name, dest)

    monkeypatch.setattr(cp, "materialize", counting)
    for _ in range(3):
        check_mutants_apply("features/fx", "c-one", app_repo)
        check_mutants_apply("features/fx", "c-base", app_repo)
    assert sorted(calls) == ["c-base", "c-one"]


def test_check_features_line_applies_the_mutants_when_the_source_is_there(app_repo: Path) -> None:
    hidden = app_repo / "teamtrack" / "tests" / "hidden" / "f1"
    hidden.mkdir(parents=True)
    (hidden / "test_f1_fixture.py").write_text(
        "def test_f1_one():\n    pass\n\n\ndef test_f1_two():\n    pass\n", encoding="utf-8"
    )
    line = with_change("inputs.checkpoint", "c-two")
    line["outputs"]["mutant_set"] = "features/fx"
    errors = check_features_line(line, app_repo)
    assert any("app.x-m1" in e and "c-two" in e for e in errors), errors
    line["inputs"]["checkpoint"] = "c-one"
    assert check_features_line(line, app_repo) == []
    # A repository without TeamTrack source (fixture manifests only) skips this check.
    assert check_features_line(line, app_repo, apply_mutants=False) == []


def test_unbuildable_checkpoint_is_reported(app_repo: Path) -> None:
    (app_repo / "teamtrack" / "app" / "x.py").write_text("other\n", encoding="utf-8")
    errors = check_mutants_apply("features/fx", "c-two", app_repo)
    assert errors and "c-two" in errors[0] and "cannot be built" in errors[0]


REAL = find_repo_root(Path(__file__))


def test_f4_mutants_apply_at_m1_alt_b_where_their_line_numbers_moved() -> None:
    from shipharness.ab.mutants import load_referee_mutants
    from shipharness.filters.mutants import source_line

    assert check_mutants_apply("features/f4", "m1-alt-b", REAL) == []
    tree = checkpoint_tree(REAL, "m1-alt-b")
    moved = [
        m.id
        for m in load_referee_mutants("features/f4", REAL)
        if source_line((tree / m.file).read_text(encoding="utf-8"), m.line) != m.original
    ]
    assert "app.services.issues-m401" in moved  # found by its text, not its recorded line


def test_every_manifest_pair_has_referee_mutants_that_apply() -> None:
    from shipharness.ab import checkpoints as cp

    problems = []
    for task in cp.task_names(REAL):
        manifest = cp.load_task(task, REAL)
        for checkpoint in manifest.hidden:
            problems += check_mutants_apply(manifest.mutant_set, checkpoint, REAL)
    assert problems == []


def line_for(group: str, n: int, splits: list[str]) -> dict[str, Any]:
    line = f1_line()
    line["metadata"] = {"group": group, "example_id": f"{group}-{n}", "control": False}
    line["split"] = splits
    return line


def full_file() -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for group, count in GROUP_COUNTS.items():
        lines += [line_for(group, n, ["extended"]) for n in range(count)]
    slots = [name for name, size in SPLIT_SIZES.items() for _ in range(size)]
    for line, name in zip(lines, slots, strict=False):
        line["split"] = [name]
    return lines


def test_file_check_accepts_the_registered_shape() -> None:
    assert sum(GROUP_COUNTS.values()) == 60
    assert check_features_file(full_file()) == []


def test_file_check_reports_group_counts() -> None:
    lines = full_file()
    lines[0]["metadata"]["group"] = "reworded"
    errors = check_features_file(lines)
    assert any("canonical" in e for e in errors) and any("reworded" in e for e in errors)


def test_file_check_reports_split_sizes() -> None:
    lines = full_file()
    lines[0]["split"] = ["section-1"]
    assert any("smoke" in e for e in check_features_file(lines))


def test_file_check_reports_duplicate_example_ids() -> None:
    lines = full_file()
    lines[1]["metadata"]["example_id"] = lines[0]["metadata"]["example_id"]
    assert any("duplicate" in e for e in check_features_file(lines))


def test_file_check_reports_the_total() -> None:
    assert any("60" in e for e in check_features_file(full_file()[:-1]))
