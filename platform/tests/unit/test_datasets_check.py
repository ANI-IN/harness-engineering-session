"""`check_file`: schema plus the semantic checks (checkpoints, hidden ids, mutant sets, counts), and
an upload that never duplicates examples."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from shipharness.config.prices import REPO_ROOT
from shipharness.datasets import STANDARD_DATASETS, check_file, upload, validate_file


def _first_line(kind: str) -> dict[str, Any]:
    path = STANDARD_DATASETS[kind][1]  # type: ignore[index]
    return json.loads(path.read_text(encoding="utf-8").splitlines()[0])


@pytest.mark.parametrize("kind", ["features", "testgen"])
def test_committed_datasets_pass_every_check(kind: str) -> None:
    path = STANDARD_DATASETS[kind][1]  # type: ignore[index]
    assert check_file(path, kind, REPO_ROOT) == []  # type: ignore[arg-type]


def test_unknown_mutant_set_passes_the_schema_but_not_the_checks(tmp_path: Path) -> None:
    line = _first_line("features")
    line["outputs"]["mutant_set"] = "features/f99"
    path = tmp_path / "f.jsonl"
    path.write_text(json.dumps(line) + "\n", encoding="utf-8")
    assert validate_file(path, "features") == []
    errors = check_file(path, "features", REPO_ROOT)
    assert any("f99" in e for e in errors)


def test_missing_testgen_mutant_file_fails_the_checks(tmp_path: Path) -> None:
    line = _first_line("testgen")
    line["outputs"]["referee_mutants"] = "datasets/mutants/none/nothing.jsonl#referee"
    path = tmp_path / "t.jsonl"
    path.write_text(json.dumps(line) + "\n", encoding="utf-8")
    assert validate_file(path, "testgen") == []
    assert check_file(path, "testgen", REPO_ROOT)


@pytest.mark.parametrize("change", ["drop", "add"])
def test_file_checks_run_whatever_the_line_count(tmp_path: Path, change: str) -> None:
    lines = STANDARD_DATASETS["features"][1].read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    duplicate = json.loads(lines[1])
    duplicate["metadata"]["example_id"] = first["metadata"]["example_id"]
    lines[1] = json.dumps(duplicate)
    if change == "drop":
        lines = lines[:-1]  # 59 lines
    else:
        lines.append(lines[-1])  # 61 lines (and a second duplicate)
    path = tmp_path / "f.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    errors = check_file(path, "features", REPO_ROOT)
    assert any(f"found {len(lines)}" in e and "expected 60 lines" in e for e in errors), errors
    assert any(f"duplicate example_id {first['metadata']['example_id']!r}" in e for e in errors)


class FakeClient:
    def __init__(self, existing: int | None, listed: int | None = None) -> None:
        self.existing = existing
        self.listed = existing or 0 if listed is None else listed
        self.created: list[Any] = []

    def has_dataset(self, *, dataset_name: str) -> bool:
        return self.existing is not None or self.listed > 0

    def read_dataset(self, *, dataset_name: str) -> Any:
        return SimpleNamespace(id="d1", example_count=self.existing)

    def list_examples(self, *, dataset_id: str, limit: int | None = None) -> Any:
        count = self.listed if limit is None else min(self.listed, limit)
        return iter([SimpleNamespace(id=f"e{i}") for i in range(count)])

    def create_dataset(self, name: str, description: str = "") -> Any:
        return SimpleNamespace(id="d1", example_count=0)

    def create_examples(self, *, dataset_id: str, examples: list[Any]) -> None:
        self.created.extend(examples)


def test_upload_refuses_to_add_to_a_dataset_that_already_has_examples() -> None:
    client = FakeClient(existing=60)
    with pytest.raises(ValueError, match="already has 60 examples"):
        upload(client, "teamtrack-features-v1", [{"inputs": {}}])
    assert client.created == []


def test_upload_fills_an_empty_or_new_dataset() -> None:
    for existing in (None, 0):
        client = FakeClient(existing=existing)
        assert upload(client, "x", [{"inputs": {}}, {"inputs": {}}]) == 2
        assert len(client.created) == 2


def test_upload_refuses_when_the_server_reports_no_count_but_lists_examples() -> None:
    client = FakeClient(existing=None, listed=1)  # example_count=None from the server
    with pytest.raises(ValueError, match="already has examples"):
        upload(client, "teamtrack-features-v1", [{"inputs": {}}])
    assert client.created == []
