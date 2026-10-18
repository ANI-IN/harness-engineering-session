"""Each filter has a pass test and a discard test. Filters 1-3 run real pytest in a LocalSandbox
on a temporary repo written by the test (trusted code)."""

from __future__ import annotations

from pathlib import Path

import pytest

from shipharness.filters.coverage import measure_coverage
from shipharness.filters.filters import (
    AddsCoverageOrKillsMutant,
    ImportsAndRuns,
    NoSourceChange,
    PassesFiveRuns,
    RealAssertionsNoMocking,
)
from shipharness.filters.models import CandidateTest, CoverageMap, FilterContext
from shipharness.filters.mutants import Mutant
from shipharness.filters.source import source_shas
from shipharness.sandbox import ExecResult, FakeSandbox

from .helpers import PY, local_sandbox, make_repo

ADD_ZERO_MUTANT = Mutant(
    id="calc-m1",
    target="calc",
    set="filter",
    file="calc.py",
    line=2,
    original="    return a + b",
    replacement="    return a + b if a != 0 else b + 1",
    rationale="wrong result when the first operand is zero",
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return make_repo(tmp_path / "repo")


def context(repo: Path, sandbox: object, **overrides: object) -> FilterContext:
    base: dict[str, object] = dict(
        workspace=repo,
        sandbox=sandbox,
        baseline_coverage=CoverageMap(),
        filter_mutants=[],
        source_shas_at_phase_start=source_shas(repo),
        existing_tests=["tests/test_calc.py"],
        target_module="calc",
        python=PY,
        timeout_s=60,
    )
    base.update(overrides)
    return FilterContext(**base)  # type: ignore[arg-type]


def candidate(repo: Path, body: str, name: str = "test_new", file: str = "tests/test_new.py"):  # type: ignore[no-untyped-def]
    source = f"from calc import add, clamp, sign\n\n\ndef {name}():\n{body}"
    path = repo / file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return CandidateTest(test_id=f"{file}::{name}", file=file, source=source)


# -- filter 1 --------------------------------------------------------------------------------


def test_filter1_passes_a_collectable_test(repo: Path) -> None:
    cand = candidate(repo, "    assert clamp(5, 0, 3) == 3\n")
    result = ImportsAndRuns().evaluate(cand, context(repo, local_sandbox(repo)))
    assert result.passed, result.reason
    assert result.filter == 1
    assert result.reason == "collected 1 test"


def test_filter1_discards_an_import_error(repo: Path) -> None:
    source = "import no_such_module\n\n\ndef test_x():\n    assert no_such_module.f() == 1\n"
    (repo / "tests" / "test_bad.py").write_text(source, encoding="utf-8")
    cand = CandidateTest(
        test_id="tests/test_bad.py::test_x", file="tests/test_bad.py", source=source
    )
    result = ImportsAndRuns().evaluate(cand, context(repo, local_sandbox(repo)))
    assert not result.passed
    assert "no_such_module" in result.reason


def test_filter1_discards_missing_and_unsafe_ids(repo: Path) -> None:
    cand = candidate(repo, "    assert add(1, 1) == 2\n")
    missing = cand.model_copy(update={"test_id": "tests/test_new.py::test_absent"})
    result = ImportsAndRuns().evaluate(missing, context(repo, local_sandbox(repo)))
    assert not result.passed
    assert "not found" in result.reason or "no test" in result.reason
    sandbox = FakeSandbox()
    unsafe = cand.model_copy(update={"test_id": 'tests/test_new.py::test_new"; whoami'})
    result = ImportsAndRuns().evaluate(unsafe, context(repo, sandbox))
    assert not result.passed
    assert result.reason.startswith("unsafe test id")
    assert sandbox.commands == []


# -- filter 2 --------------------------------------------------------------------------------


def test_filter2_passes_five_runs(repo: Path) -> None:
    cand = candidate(repo, "    assert clamp(5, 0, 3) == 3\n")
    sandbox = FakeSandbox(default=ExecResult(exit_code=0, output="1 passed in 0.1s", duration_ms=1))
    result = PassesFiveRuns().evaluate(cand, context(repo, sandbox))
    assert result.passed, result.reason
    assert result.reason == "passed 5 of 5 runs"
    assert len(sandbox.commands) == 5  # five separate executions


def test_filter2_discards_a_failing_test(repo: Path) -> None:
    cand = candidate(repo, "    assert clamp(5, 0, 3) == 4\n")
    result = PassesFiveRuns().evaluate(cand, context(repo, local_sandbox(repo)))
    assert not result.passed
    assert result.reason.startswith("failed on run 1 of 5")
    assert "assert 3 == 4" in result.reason


def test_filter2_discards_a_flaky_test(repo: Path) -> None:
    outputs = iter(["1 passed in 0.1s", "1 passed in 0.1s", "FAILED t::x - AssertionError"])

    def script(_command: str) -> ExecResult:
        text = next(outputs)
        return ExecResult(exit_code=0 if "passed" in text else 1, output=text, duration_ms=1)

    cand = candidate(repo, "    assert add(1, 1) == 2\n")
    result = PassesFiveRuns().evaluate(cand, context(repo, FakeSandbox(script)))
    assert not result.passed
    assert result.reason.startswith("flaky: passed 2 of 5 runs")


def test_filter2_discards_timeouts_and_skips(repo: Path) -> None:
    cand = candidate(repo, "    assert add(1, 1) == 2\n")
    slow = FakeSandbox(default=ExecResult(exit_code=124, output="", duration_ms=1, timed_out=True))
    assert "timed out" in PassesFiveRuns().evaluate(cand, context(repo, slow)).reason
    skip = FakeSandbox(default=ExecResult(exit_code=0, output="1 skipped in 0.1s", duration_ms=1))
    assert "skipped" in PassesFiveRuns().evaluate(cand, context(repo, skip)).reason


# -- filter 3 --------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def calc3(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, CoverageMap]:
    """One repo and one baseline coverage run shared by the filter 3 tests."""
    repo = make_repo(tmp_path_factory.mktemp("f3") / "repo")
    run = measure_coverage(repo, local_sandbox(repo), ["tests/test_calc.py"], python=PY)
    assert run.ok, run.detail
    return repo, run.coverage


def f3_context(calc3: tuple[Path, CoverageMap], **overrides: object) -> FilterContext:
    repo, coverage = calc3
    return context(repo, local_sandbox(repo), baseline_coverage=coverage, **overrides)


def test_filter3_passes_a_test_that_adds_coverage(calc3) -> None:  # type: ignore[no-untyped-def]
    cand = candidate(calc3[0], "    assert clamp(5, 0, 3) == 3\n", file="tests/test_a.py")
    result = AddsCoverageOrKillsMutant().evaluate(cand, f3_context(calc3))
    assert result.passed, result.reason
    assert result.reason.startswith("adds 3 covered lines: calc.py:14,16-17")


def test_filter3_discards_a_test_that_adds_nothing(calc3) -> None:  # type: ignore[no-untyped-def]
    ctx = f3_context(
        calc3, filter_mutants=[ADD_ZERO_MUTANT], surviving_mutant_ids=frozenset({"calc-m1"})
    )
    cand = candidate(calc3[0], "    assert add(1, 1) == 2\n", file="tests/test_b.py")
    result = AddsCoverageOrKillsMutant().evaluate(cand, ctx)
    assert not result.passed
    assert result.reason == (
        "adds no line coverage over the existing suite and kills no filter-set mutant "
        "that the existing tests miss (1 checked)"
    )


def test_filter3_passes_a_test_that_kills_a_surviving_mutant(calc3) -> None:  # type: ignore[no-untyped-def]
    # surviving_mutant_ids is not given, so the filter first runs the existing tests on the mutant.
    ctx = f3_context(calc3, filter_mutants=[ADD_ZERO_MUTANT])
    cand = candidate(calc3[0], "    assert add(0, 4) == 4\n", file="tests/test_c.py")
    result = AddsCoverageOrKillsMutant().evaluate(cand, ctx)
    assert result.passed, result.reason
    assert result.reason == "kills filter-set mutant calc-m1 that no existing test kills"


def test_filter3_ignores_mutants_the_existing_tests_already_kill(calc3) -> None:  # type: ignore[no-untyped-def]
    ctx = f3_context(calc3, filter_mutants=[ADD_ZERO_MUTANT], surviving_mutant_ids=frozenset())
    cand = candidate(calc3[0], "    assert add(0, 4) == 4\n", file="tests/test_d.py")
    result = AddsCoverageOrKillsMutant().evaluate(cand, ctx)
    assert not result.passed
    assert "(0 checked)" in result.reason


# -- filter 4 --------------------------------------------------------------------------------


def test_filter4_passes_real_assertions(repo: Path) -> None:
    cand = candidate(repo, "    assert sign(0) == 0\n")
    result = RealAssertionsNoMocking().evaluate(cand, context(repo, FakeSandbox()))
    assert result.passed, result.reason
    assert result.filter == 4


def test_filter4_discards_mocking_the_unit(repo: Path) -> None:
    source = (
        "import calc\n\n\ndef test_new(monkeypatch):\n"
        '    monkeypatch.setattr(calc, "sign", lambda x: 0)\n    assert calc.sign(5) == 0\n'
    )
    (repo / "tests" / "test_new.py").write_text(source, encoding="utf-8")
    cand = CandidateTest(
        test_id="tests/test_new.py::test_new", file="tests/test_new.py", source=source
    )
    result = RealAssertionsNoMocking().evaluate(cand, context(repo, FakeSandbox()))
    assert not result.passed
    assert result.reason.startswith("mocks the unit under test (calc)")


def test_filter4_discards_a_vacuous_test(repo: Path) -> None:
    cand = candidate(repo, "    clamp(1, 0, 3)\n    assert True\n")
    result = RealAssertionsNoMocking().evaluate(cand, context(repo, FakeSandbox()))
    assert not result.passed
    assert result.reason.startswith("no real assertion")


# -- filter 5 --------------------------------------------------------------------------------


def test_filter5_passes_when_no_source_changed(repo: Path) -> None:
    ctx = context(repo, FakeSandbox())
    cand = candidate(repo, "    assert add(1, 1) == 2\n")
    result = NoSourceChange().evaluate(cand, ctx)
    assert result.passed, result.reason
    assert result.reason == "no source file changed during the test phase"


def test_filter5_discards_when_source_changed(repo: Path) -> None:
    ctx = context(repo, FakeSandbox())
    (repo / "calc.py").write_text("def add(a, b):\n    return 0\n", encoding="utf-8")
    (repo / "helper.py").write_text("x = 1\n", encoding="utf-8")
    cand = candidate(repo, "    assert add(1, 1) == 0\n")
    result = NoSourceChange().evaluate(cand, ctx)
    assert not result.passed
    assert result.reason == (
        "source files changed during the test phase: calc.py (modified), helper.py (added)"
    )
