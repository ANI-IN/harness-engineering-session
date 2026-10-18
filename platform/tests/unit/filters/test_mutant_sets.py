"""D-4 across files: no mutation is in both the filter and the referee set, in any mutant file."""

from __future__ import annotations

import json
from pathlib import Path

from shipharness.filters.mutant_sets import MUTANTS_DIR, mutant_files, overlaps


def record(mid: str, kind: str, original: str, replacement: str, file: str = "app/x.py") -> dict:
    target = mid.rsplit("-m", 1)[0]
    return {
        "id": mid,
        "target": target,
        "set": kind,
        "file": file,
        "line": 3,
        "original": original,
        "replacement": replacement,
        "rationale": "test",
    }


def write(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def test_a_mutation_in_both_sets_across_files_is_reported(tmp_path: Path) -> None:
    module = write(
        tmp_path / "app.x.jsonl", [record("app.x-m1", "filter", "    a = 1", "    a = 2")]
    )
    feature = write(
        tmp_path / "features" / "f1.jsonl",
        [record("app.x-m101", "referee", "    a  =  1", "    a = 2 ")],  # whitespace differs
    )
    problems = overlaps([module, feature])
    assert len(problems) == 1
    assert "app.x-m1" in problems[0] and "app.x-m101" in problems[0]
    assert "app/x.py" in problems[0]


def test_the_same_mutation_twice_in_one_set_is_allowed(tmp_path: Path) -> None:
    a = write(tmp_path / "a.jsonl", [record("app.x-m1", "referee", "    a = 1", "    a = 2")])
    b = write(tmp_path / "b.jsonl", [record("app.x-m2", "referee", "    a = 1", "    a = 2")])
    assert overlaps([a, b]) == []


def test_different_replacements_of_one_line_do_not_overlap(tmp_path: Path) -> None:
    rows = [
        record("app.x-m1", "filter", "    a = 1", "    a = 2"),
        record("app.x-m2", "referee", "    a = 1", "    a = 3"),
    ]
    assert overlaps([write(tmp_path / "a.jsonl", rows)]) == []


def test_the_same_change_in_another_file_does_not_overlap(tmp_path: Path) -> None:
    rows = [
        record("app.x-m1", "filter", "    a = 1", "    a = 2"),
        record("app.y-m1", "referee", "    a = 1", "    a = 2", file="app/y.py"),
    ]
    assert overlaps([write(tmp_path / "a.jsonl", rows)]) == []


def test_duplicate_ids_across_files_are_reported(tmp_path: Path) -> None:
    a = write(tmp_path / "a.jsonl", [record("app.x-m1", "filter", "    a = 1", "    a = 2")])
    b = write(tmp_path / "b.jsonl", [record("app.x-m1", "filter", "    b = 1", "    b = 2")])
    problems = overlaps([a, b])
    assert any("duplicate id app.x-m1" in p for p in problems)


def test_mutant_files_cover_modules_and_features() -> None:
    files = mutant_files()
    names = {p.relative_to(MUTANTS_DIR).as_posix() for p in files}
    assert "app.services.issues.jsonl" in names
    assert {f"features/f{n}.jsonl" for n in range(1, 8)} <= names


def test_teamtrack_filter_and_referee_sets_are_disjoint() -> None:
    assert overlaps(mutant_files()) == []
