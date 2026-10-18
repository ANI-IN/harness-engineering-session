"""Filter data models."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, SkipValidation

from shipharness.filters.mutants import Mutant


class CoverageMap(BaseModel):
    """Executed source lines per workspace-relative POSIX path (test files excluded)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    files: dict[str, frozenset[int]] = {}

    def lines(self, path: str) -> frozenset[int]:
        return self.files.get(path, frozenset())

    def new_lines(self, baseline: CoverageMap) -> dict[str, list[int]]:
        """Lines executed here that `baseline` never executed, per file."""
        added = {path: sorted(lines - baseline.lines(path)) for path, lines in self.files.items()}
        return {path: lines for path, lines in sorted(added.items()) if lines}

    def total(self) -> int:
        return sum(len(lines) for lines in self.files.values())


class CandidateTest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    test_id: str  # "<file>::<name>" (or "<file>::<Class>::<name>")
    file: str
    source: str  # full text of the test file


class FilterResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    test_id: str
    filter: int  # 1..5
    passed: bool
    reason: str


class FilterContext(BaseModel):
    """Everything the filters need, captured at the start of the test phase.

    Fields after `source_shas_at_phase_start` are later additions with defaults.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    workspace: Path
    sandbox: SkipValidation[Any]  # a shipharness.sandbox.Sandbox
    baseline_coverage: CoverageMap
    filter_mutants: list[Mutant]  # filter set only
    source_shas_at_phase_start: dict[str, str]
    existing_tests: list[str] = []  # pytest targets of the existing suite; [] = configured suite
    surviving_mutant_ids: frozenset[str] | None = None  # filter mutants no existing test kills
    target_module: str | None = None  # dotted module under test, for filter 4
    python: str = "python"  # interpreter command inside the sandbox
    timeout_s: int = 120  # per pytest invocation
    runs: int = 5  # filter 2: consecutive passing runs required
    # Existing-suite runs (baseline coverage, mutant kills by existing tests) pass
    # `--doctest-modules`, so doctests count in the baseline. Candidates never do.
    doctest_modules: bool = False


class Filter(Protocol):
    number: int
    name: str

    def evaluate(self, cand: CandidateTest, ctx: FilterContext) -> FilterResult: ...
