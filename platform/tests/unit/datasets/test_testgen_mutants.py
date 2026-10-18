"""Library mutant files (datasets/mutants/<library>/*.jsonl) and their validation record.

These checks need no network: the slow tests in test_testgen_libs.py re-apply every mutant to the
pinned source and confirm the recorded kill. The uniqueness check below reads the pinned source in
.shipharness/libs and is skipped when it is absent.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from shipharness.filters.mutants import Mutant, load_mutants
from shipharness.filters.pytest_cmd import SAFE_TEST_ID

from .testgen_support import LIBRARIES, MUTANTS, VALIDATION, load_script

FETCH = load_script("fetch_testgen_libs")


def files(library: str) -> list[Path]:
    return sorted((MUTANTS / library).glob("*.jsonl"))


def library_mutants() -> list[Mutant]:
    return [m for lib in LIBRARIES for path in files(lib) for m in load_mutants(path, None)]


def pinned_source(library: str) -> Path:
    try:
        problems = FETCH.check(FETCH.LIBS[library])
    except (OSError, RuntimeError) as exc:
        problems = [str(exc)]
    if problems:
        pytest.skip(f"{library} is not fetched: uv run python scripts/fetch_testgen_libs.py")
    return FETCH.source_dir(library)


@pytest.mark.parametrize("library", LIBRARIES)
def test_every_original_matches_exactly_one_line_of_the_pinned_source(library: str) -> None:
    # The runner finds a mutant by its `original` text; a line that occurs twice is refused.
    src = pinned_source(library)
    wrong = []
    for path in files(library):
        for m in load_mutants(path, None):
            lines = (src / m.file).read_bytes().decode("utf-8").splitlines()
            found = [n for n, line in enumerate(lines, start=1) if line == m.original]
            if found != [m.line]:
                wrong.append(f"{m.id}: recorded line {m.line}, original found at {found}")
    assert not wrong, "\n".join(wrong)


@pytest.mark.parametrize("library", LIBRARIES)
def test_ten_modules_per_library_each_with_both_sets(library: str) -> None:
    paths = files(library)
    assert len(paths) == 10
    for path in paths:
        mutants = load_mutants(path, None)
        assert 4 <= len(mutants) <= 6, path.name
        assert {m.set for m in mutants} == {"filter", "referee"}, path.name
        target = mutants[0].target
        assert target == f"{library}.{path.stem}"
        assert [m.id for m in mutants] == [f"{target}-m{n}" for n in range(1, len(mutants) + 1)]
        for m in mutants:
            assert m.target == target
            dotted = re.sub(r"^src/", "", m.file).removesuffix(".py").replace("/", ".")
            assert dotted == target
            assert m.replacement != m.original
            assert m.rationale.strip()


def test_filter_and_referee_sets_never_share_a_change() -> None:
    mutants = library_mutants()
    filter_changes = {(m.file, m.line, m.replacement) for m in mutants if m.set == "filter"}
    referee_changes = {(m.file, m.line, m.replacement) for m in mutants if m.set == "referee"}
    assert not filter_changes & referee_changes
    assert len({(m.file, m.line) for m in mutants}) == len(mutants)  # one mutant per line


def test_about_four_mutants_per_module() -> None:
    per_library = Counter(m.target.split(".")[0] for m in library_mutants())
    assert 40 <= per_library["boltons"] <= 60, per_library
    assert 40 <= per_library["wtforms"] <= 60, per_library


def test_validation_record_covers_every_library_mutant() -> None:
    record = json.loads(VALIDATION.read_text(encoding="utf-8"))
    mutants = library_mutants()
    assert set(record["mutants"]) == {m.id for m in mutants}
    assert record["libraries"]["boltons"]["commit"] == "4332b35a278d694f30c99881faa61cde695c7a96"
    assert record["libraries"]["wtforms"]["commit"] == "ea57c11591556333b4f0ac494d1e5d3f250ab305"
    for m in mutants:
        entry = record["mutants"][m.id]
        library = m.target.split(".")[0]
        assert entry["library"] == library
        killer = entry["killed_by"]
        assert SAFE_TEST_ID.match(killer), killer
        assert killer not in record["libraries"][library]["known_failures"]
        assert killer.startswith("tests/")
