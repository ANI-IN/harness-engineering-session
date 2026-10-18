"""Visible tests for the learner's own tests, own skill, and portfolio files (structure, and the
LangSmith page's link to a trace of the live A/B)."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest
from a4_live import trace_link_problems
from a4_support import (
    CASE_STUDY,
    EVIDENCE,
    LANGSMITH,
    doc_problems,
    skill_problems,
)

MIN_OWN_TESTS = 8


def _own_test_names(root: Path) -> list[str]:
    names: list[str] = []
    for path in sorted((root / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
                "test"
            ):
                names.append(f"{path.name}::{node.name}")
    return names


@pytest.mark.criterion("own-tests")
def test_at_least_eight_own_tests(impl_path: Path) -> None:
    names = _own_test_names(impl_path)
    assert len(names) >= MIN_OWN_TESTS, f"tests/ has {len(names)} test functions: {names}"


@pytest.mark.criterion("own-tests")
def test_own_tests_pass(impl_path: Path) -> None:
    tests = impl_path / "tests"
    assert tests.is_dir(), "tests/ is missing"
    extra = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(impl_path), *extra])}
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(tests)],
        capture_output=True,
        text=True,
        env=env,
        timeout=1200,
    )
    lines = [line for line in run.stdout.splitlines() if line.strip()]
    summary = lines[-1] if lines else f"pytest exit {run.returncode}"
    failed = [line for line in lines if line.startswith(("FAILED", "ERROR"))]
    assert run.returncode == 0, f"tests/: {summary}; {'; '.join(failed[:3])}"


@pytest.mark.criterion("skill")
def test_own_skill_is_valid_and_not_the_template(impl_path: Path) -> None:
    problems = skill_problems(impl_path)
    assert not problems, "\n".join(problems)


@pytest.mark.criterion("portfolio-evidence")
def test_evidence_report_structure(impl_path: Path) -> None:
    problems = doc_problems(impl_path, EVIDENCE)
    assert not problems, "\n".join(problems)


@pytest.mark.criterion("portfolio-langsmith")
def test_langsmith_page_structure(impl_path: Path) -> None:
    problems = doc_problems(impl_path, LANGSMITH)
    page = impl_path / LANGSMITH.file
    if page.is_file():
        problems += trace_link_problems(impl_path, page.read_text(encoding="utf-8"))
    assert not problems, "\n".join(problems)


@pytest.mark.criterion("portfolio-case-study")
def test_case_study_structure(impl_path: Path) -> None:
    problems = doc_problems(impl_path, CASE_STUDY)
    assert not problems, "\n".join(problems)
