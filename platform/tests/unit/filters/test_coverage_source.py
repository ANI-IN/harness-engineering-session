from __future__ import annotations

import json
from pathlib import Path

from shipharness.filters.coverage import measure_coverage, parse_coverage_json
from shipharness.filters.models import CoverageMap
from shipharness.filters.source import changed_sources, is_test_path, source_shas
from shipharness.sandbox import ExecResult, FakeSandbox

from .helpers import PY, local_sandbox, make_repo


def test_coverage_map_new_lines() -> None:
    base = CoverageMap(files={"calc.py": frozenset({1, 2})})
    cand = CoverageMap(files={"calc.py": frozenset({1, 2, 5, 6}), "util.py": frozenset({3})})
    assert cand.new_lines(base) == {"calc.py": [5, 6], "util.py": [3]}
    assert base.new_lines(cand) == {}
    assert cand.total() == 5


def test_parse_coverage_json_keeps_source_files_only(tmp_path: Path) -> None:
    text = json.dumps(
        {
            "files": {
                "calc.py": {"executed_lines": [1, 2, 3]},
                "tests\\test_calc.py": {"executed_lines": [1, 2]},
                "pkg\\mod.py": {"executed_lines": [4, "x", 5]},
                "conftest.py": {"executed_lines": [1]},
                "../outside.py": {"executed_lines": [1]},
                ".shipharness-mutant-abc/calc.py": {"executed_lines": [1]},
            }
        }
    )
    cov = parse_coverage_json(text, tmp_path)
    assert cov.files == {"calc.py": frozenset({1, 2, 3}), "pkg/mod.py": frozenset({4, 5})}


def test_parse_coverage_json_tolerates_garbage(tmp_path: Path) -> None:
    assert parse_coverage_json("not json", tmp_path).files == {}
    assert parse_coverage_json('{"files": []}', tmp_path).files == {}


def test_measure_coverage_runs_in_the_sandbox(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    run = measure_coverage(repo, local_sandbox(repo), ["tests/test_calc.py"], python=PY)
    assert run.ok, run.detail
    lines = run.coverage.files["calc.py"]
    assert {2, 6, 7} <= lines  # add() body and the negative branch of sign()
    assert 15 not in lines  # clamp() is never called
    assert "tests/test_calc.py" not in run.coverage.files
    assert not [p for p in repo.iterdir() if p.name.startswith(".shipharness-")]


def test_measure_coverage_reports_pytest_errors(tmp_path: Path) -> None:
    sandbox = FakeSandbox(default=ExecResult(exit_code=4, output="usage error", duration_ms=1))
    run = measure_coverage(tmp_path, sandbox, ["tests"], python="python")
    assert not run.ok
    assert "exit code 4" in run.detail


def test_is_test_path() -> None:
    assert is_test_path("tests/visible/test_x.py")
    assert is_test_path("tests/helpers.py")
    assert is_test_path("pkg/test_mod.py")
    assert is_test_path("pkg/mod_test.py")
    assert is_test_path("conftest.py")
    assert not is_test_path("app/services/issues.py")
    assert not is_test_path("app/testing_utils.py")


def test_source_shas_and_changes(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    (repo / "notes.md").write_text("x", encoding="utf-8")
    before = source_shas(repo)
    assert set(before) == {"calc.py", "pytest.ini"}
    (repo / "tests" / "test_new.py").write_text("def test_a(): pass\n", encoding="utf-8")
    (repo / "notes.md").write_text("y", encoding="utf-8")
    assert changed_sources(before, repo) == []
    (repo / "calc.py").write_text("def add(a, b):\n    return 5\n", encoding="utf-8")
    (repo / "extra.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "pytest.ini").unlink()
    assert changed_sources(before, repo) == [
        ("calc.py", "modified"),
        ("extra.py", "added"),
        ("pytest.ini", "deleted"),
    ]
