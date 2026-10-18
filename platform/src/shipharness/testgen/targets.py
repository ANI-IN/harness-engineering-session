"""Targets from `platform/datasets/testgen-targets-v1.jsonl` for `shipharness testgen --target`.

A target's line names the repository, the module, its existing tests, the filter mutants, and the
metadata (`baseline_includes_doctests`, ...). Library targets run in the fetched clone
`.shipharness/libs/<library>/src` with that library's `.venv` python; TeamTrack targets run in
`platform/teamtrack/`.
"""

from __future__ import annotations

import json
import os
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shipharness.config.prices import REPO_ROOT
from shipharness.layout import DATASETS_DIR, app_dir_at, resolve

TARGETS_FILE = REPO_ROOT / DATASETS_DIR / "testgen-targets-v1.jsonl"
FETCH_COMMAND = "uv run python platform/scripts/fetch_testgen_libs.py"
TEAMTRACK = "teamtrack"


class TargetError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedTarget:
    target_id: str
    repo: Path
    module: str
    existing_tests: list[str]
    mutants: Path | None  # the filter mutant file
    mutant_set: str | None  # the set its ref selects ("filter")
    python: str | None  # shell-quoted interpreter; None = the caller's default
    metadata: dict[str, Any] = field(default_factory=dict)


def _venv_python(lib: Path) -> Path:
    if os.name == "nt":
        return lib / ".venv" / "Scripts" / "python.exe"
    return lib / ".venv" / "bin" / "python"


def find_line(target_id: str, dataset: Path = TARGETS_FILE) -> dict[str, Any]:
    if not Path(dataset).is_file():
        raise TargetError(f"targets file not found: {dataset}")
    for number, raw in enumerate(Path(dataset).read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            line = json.loads(raw)
        except ValueError as exc:
            raise TargetError(f"{Path(dataset).name}:{number}: not valid JSON ({exc})") from None
        if line.get("inputs", {}).get("target_id") == target_id:
            return dict(line)
    raise TargetError(f"no target {target_id!r} in {dataset}")


def resolve_target(
    target_id: str,
    dataset: Path = TARGETS_FILE,
    course_root: Path = REPO_ROOT,
    *,
    need_python: bool = True,
) -> ResolvedTarget:
    """Everything testgen needs for one dataset target. `need_python=False` (a docker sandbox, or
    an explicit --python) skips the library venv requirement."""
    line = find_line(target_id, dataset)
    inputs, outputs = line["inputs"], line.get("outputs", {})
    metadata = dict(line.get("metadata", {}))
    name = str(inputs["repo"])
    python: str | None = None
    if name == TEAMTRACK:
        repo = Path(course_root) / app_dir_at(Path(course_root))
    else:
        lib = Path(course_root) / ".shipharness" / "libs" / name
        repo = lib / "src"
        venv_python = _venv_python(lib)
        missing = [p for p in (repo, venv_python if need_python else None) if p and not p.exists()]
        if missing:
            raise TargetError(
                f"library {name} is not fetched ({missing[0]} is missing): run `{FETCH_COMMAND}`"
            )
        if need_python:
            python = shlex.quote(str(venv_python))
    ref = str(outputs.get("filter_mutants", ""))
    path, _, selected = ref.partition("#")
    return ResolvedTarget(
        target_id=target_id,
        repo=repo,
        module=str(inputs["module"]),
        existing_tests=[str(t) for t in inputs.get("existing_tests", [])],
        mutants=resolve(Path(course_root), path) if path else None,
        mutant_set=selected or None,
        python=python,
        metadata=metadata,
    )
