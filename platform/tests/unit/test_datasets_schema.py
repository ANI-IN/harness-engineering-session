from __future__ import annotations

import json
from pathlib import Path

import pytest

from shipharness.datasets import (
    build_examples,
    load_lines,
    validate_file,
)

FEATURE_LINE = {
    "inputs": {
        "feature_id": "F1",
        "checkpoint": "m1-s1-start",
        "ticket_text": "List issues with filters and cursor pagination.",
        "variant": "canonical",
        "session_budget": [30],
    },
    "outputs": {
        "hidden_test_ids": ["teamtrack/tests/hidden/f1/test_list.py::test_cursor_stable"],
        "allowed_paths": {"build": ["app/api/issues.py"], "test": ["tests/visible/**"]},
        "mutant_set": "f1",
        "primary_measure": "r1_new_violations>=1",
    },
    "metadata": {"group": "canonical", "example_id": "F1-canonical", "control": False},
    "split": ["section-1", "smoke"],
}

TESTGEN_LINE = {
    "inputs": {
        "target_id": "TG-boltons-mathutils",
        "repo": "boltons",
        "pin": "26.2.0",
        "module": "boltons/mathutils.py",
        "existing_tests": ["tests/test_mathutils.py"],
    },
    "outputs": {
        "filter_mutants": "datasets/mutants/boltons/mathutils.jsonl#filter",
        "referee_mutants": "datasets/mutants/boltons/mathutils.jsonl#referee",
        "known_failures": [],
    },
    "metadata": {"source": "library", "license": "BSD-3-Clause"},
    "split": ["testgen"],
}


def write_jsonl(path: Path, lines: list[dict]) -> Path:  # type: ignore[type-arg]
    path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    return path


def test_valid_feature_line_passes(tmp_path: Path) -> None:
    path = write_jsonl(tmp_path / "f.jsonl", [FEATURE_LINE])
    assert validate_file(path, "features") == []


def test_feature_line_missing_primary_measure_fails(tmp_path: Path) -> None:
    bad = json.loads(json.dumps(FEATURE_LINE))
    del bad["outputs"]["primary_measure"]
    errors = validate_file(write_jsonl(tmp_path / "f.jsonl", [bad]), "features")
    assert len(errors) == 1
    assert "line 1" in errors[0] and "primary_measure" in errors[0]


def test_valid_testgen_line_passes(tmp_path: Path) -> None:
    assert validate_file(write_jsonl(tmp_path / "t.jsonl", [TESTGEN_LINE]), "testgen") == []


def test_invalid_json_line_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "f.jsonl"
    path.write_text("{not json}\n", encoding="utf-8")
    errors = validate_file(path, "features")
    assert errors and "line 1" in errors[0]


def test_build_examples_carries_splits_and_reference_outputs(tmp_path: Path) -> None:
    path = write_jsonl(tmp_path / "f.jsonl", [FEATURE_LINE])
    examples = build_examples(load_lines(path, "features"))
    assert examples == [
        {
            "inputs": FEATURE_LINE["inputs"],
            "outputs": FEATURE_LINE["outputs"],
            "metadata": FEATURE_LINE["metadata"],
            "split": ["section-1", "smoke"],
        }
    ]


def test_unknown_kind_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        validate_file(write_jsonl(tmp_path / "x.jsonl", [FEATURE_LINE]), "other")  # type: ignore[arg-type]
