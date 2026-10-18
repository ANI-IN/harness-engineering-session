"""Shared paths and loaders for the testgen-targets-v1 tests (scripts are not a package)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from shipharness.layout import find_repo_root

REPO = find_repo_root(Path(__file__))
DATASET = REPO / "platform" / "datasets" / "testgen-targets-v1.jsonl"
SOURCES = REPO / "platform" / "datasets" / "sources" / "testgen.toml"
MUTANTS = REPO / "platform" / "datasets" / "mutants"
VALIDATION = MUTANTS / "validation.json"
LIBRARIES = ("boltons", "wtforms")


def load_script(name: str) -> ModuleType:
    path = REPO / "platform" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_script_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


def committed_lines() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in DATASET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
