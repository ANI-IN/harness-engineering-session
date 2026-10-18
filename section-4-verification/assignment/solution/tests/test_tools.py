"""Tests for the filter-6 report CLI and the skill's report summary script."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest
from a4_verification import apply_filter

SKILL_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skill"
    / "testgen-evidence"
    / "scripts"
    / "summarize_report.py"
)
EXISTING = "def test_old(client):\n    assert client.get('/a').status_code == 200\n"
KEPT = (
    "def test_copy(client):\n    assert client.get('/a').status_code == 200\n\n\n"
    "def test_new(client):\n    assert client.get('/b').status_code == 404\n"
)
REPORT = {
    "run_id": "tg-1",
    "status": "done",
    "kept": ["tests/test_gen.py::test_copy", "tests/test_gen.py::test_new"],
    "not_evaluated": ["tests/test_gen.py::test_late"],
    "results": [
        {"test_id": "tests/test_gen.py::test_copy", "filter": 1, "passed": True, "reason": "ok"},
        {"test_id": "tests/test_gen.py::test_new", "filter": 1, "passed": True, "reason": "ok"},
        {"test_id": "tests/test_gen.py::test_bad", "filter": 1, "passed": False, "reason": "boom"},
        {"test_id": "tests/test_gen.py::test_flaky", "filter": 1, "passed": True, "reason": "ok"},
        {
            "test_id": "tests/test_gen.py::test_flaky",
            "filter": 2,
            "passed": False,
            "reason": "flaky",
        },
    ],
}


def _layout(tmp_path: Path) -> tuple[Path, Path]:
    repo, kept = tmp_path / "repo", tmp_path / "kept"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_old.py").write_text(EXISTING, encoding="utf-8")
    (kept / "tests").mkdir(parents=True)
    (kept / "tests" / "test_gen.py").write_text(KEPT, encoding="utf-8")
    (kept / "testgen-report.json").write_text(json.dumps(REPORT), encoding="utf-8")
    return repo, kept


def test_apply_filter_reports_duplicates_among_kept_tests(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, kept = _layout(tmp_path)
    code = apply_filter.main(["--repo", str(repo), "--kept", str(kept), "--existing", "tests"])
    out = capsys.readouterr().out
    assert code == 0
    assert "- tests/test_gen.py::test_copy: filter 6: duplicate of existing test" in out
    assert "+ tests/test_gen.py::test_new: filter 6" in out
    assert "filter 6 kept 1 of 2 kept tests (1 existing tests compared" in out


def test_apply_filter_update_report_appends_filter_6_rows_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, kept = _layout(tmp_path)
    args = ["--repo", str(repo), "--kept", str(kept), "--existing", "tests", "--update-report"]
    assert apply_filter.main(args) == 0
    assert apply_filter.main(args) == 0  # a second run replaces its rows, it does not add more
    report = json.loads((kept / "testgen-report.json").read_text(encoding="utf-8"))
    assert report["results"][: len(REPORT["results"])] == REPORT["results"]
    rows = report["results"][len(REPORT["results"]) :]
    assert [(r["test_id"], r["filter"], r["passed"]) for r in rows] == [
        ("tests/test_gen.py::test_copy", 6, False),
        ("tests/test_gen.py::test_new", 6, True),
    ]
    assert report["kept"] == REPORT["kept"]
    assert report["filter6"] == {"kept": ["tests/test_gen.py::test_new"], "existing_tests": 1}
    assert "report updated:" in capsys.readouterr().out


def test_apply_filter_leaves_the_report_alone_without_the_flag(tmp_path: Path) -> None:
    repo, kept = _layout(tmp_path)
    assert apply_filter.main(["--repo", str(repo), "--kept", str(kept), "--existing", "tests"]) == 0
    assert json.loads((kept / "testgen-report.json").read_text(encoding="utf-8")) == REPORT


def test_summary_counts_the_tests_filter_6_kept_when_present() -> None:
    report = {**REPORT, "filter6": {"kept": ["tests/test_gen.py::test_new"], "existing_tests": 1}}
    assert "| Kept after filter 6 | 1 |" in _script().summarize(report)
    assert not any("filter 6" in line for line in _script().summarize(REPORT))


def test_apply_filter_rejects_a_missing_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = apply_filter.main(["--repo", str(tmp_path), "--kept", str(tmp_path), "--existing", "."])
    assert code == 1
    assert capsys.readouterr().out.startswith("ERROR ")


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("summarize_report", SKILL_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_summary_table_counts_proposed_kept_and_discards_per_filter(tmp_path: Path) -> None:
    lines = _script().summarize(REPORT)
    assert lines[:2] == ["| Measure | Value |", "|---|---|"]
    assert "| Proposed tests (evaluated) | 4 |" in lines
    assert "| Kept by testgen (filters 1-5) | 2 |" in lines
    assert "| Not evaluated (over --max-tests) | 1 |" in lines
    assert "| Discarded by filter 1 | 1 |" in lines
    assert "| Discarded by filter 2 | 1 |" in lines
    assert "- tests/test_gen.py::test_flaky: filter 2: flaky" in lines


def test_summary_script_prints_error_for_a_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _script().main([str(tmp_path / "none.json")]) == 1
    assert capsys.readouterr().out.startswith("ERROR ")
