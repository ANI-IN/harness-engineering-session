"""Semantic checks for testgen-targets-v1 lines (beyond the line model in schema.py).

`check_testgen_line` checks one line against the repository: both mutant references resolve to
non-empty sets for the line's module, and the existing tests are listed (and exist, where the
source tree is available). `check_testgen_file` checks the whole file: 40 lines, 20 TeamTrack +
10 boltons + 10 WTForms, unique ids. Both return a list of problems (empty = valid).
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel, ValidationError

from shipharness.datasets.schema import TestgenTarget
from shipharness.filters.mutants import MutantError, load_mutant_ref
from shipharness.layout import app_dir_at, resolve

EXPECTED_COUNTS = {"teamtrack": 20, "boltons": 10, "wtforms": 10}
EXPECTED_TOTAL = sum(EXPECTED_COUNTS.values())
SPLIT = "testgen"
TEAMTRACK_PIN = "m1-base"
REQUIRED_METADATA = ("license", "commit")
LIBRARY_METADATA: dict[str, dict[str, Any]] = {
    "boltons": {"baseline_includes_doctests": True},  # G-19
    "wtforms": {"pytest_config": "upstream", "warnings_are_errors": True},  # G-20
}


def dotted_module(module: str) -> str:
    parts = list(PurePosixPath(module).with_suffix("").parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    return ".".join(parts)


def source_root(repo: Path, name: str) -> Path | None:
    """Where the line's source tree lives: TeamTrack in this repository, or the fetched library
    clone (None when it has not been fetched)."""
    if name == "teamtrack":
        return Path(repo) / app_dir_at(Path(repo))
    clone = Path(repo) / ".shipharness" / "libs" / name / "src"
    return clone if clone.is_dir() else None


def _as_target(line: Any) -> tuple[TestgenTarget | None, list[str]]:
    if isinstance(line, TestgenTarget):
        return line, []
    data = line.model_dump(mode="json") if isinstance(line, BaseModel) else line
    try:
        return TestgenTarget.model_validate(data), []
    except ValidationError as exc:
        return None, [
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        ]


def _check_ref(
    field: str, ref: str, wanted: str, module: str, repo: Path, root: Path | None
) -> list[str]:
    path, _, selected = ref.partition("#")
    if selected != wanted:
        return [f"{field}: {ref!r} must select the #{wanted} set"]
    file = resolve(Path(repo), path)  # dataset paths name datasets/ and teamtrack/ logically
    if not file.is_file():
        return [f"{field}: {path} not found"]
    try:
        mutants = load_mutant_ref(f"{file}#{selected}", root)
    except MutantError as exc:
        return [f"{field}: {exc}"]
    if not mutants:
        return [f"{field}: {ref} has no {wanted} mutants"]
    problems = []
    dotted = dotted_module(module)
    for m in mutants:
        if m.file != module or m.target != dotted:
            problems.append(f"{field}: {m.id} targets {m.file}, not the line's module {module}")
    return problems


def check_testgen_line(line: Any, repo: Path) -> list[str]:
    """Problems with one line (a dict or a TestgenTarget); `repo` is the repository root."""
    target, problems = _as_target(line)
    if target is None:
        return problems
    inputs, outputs, meta = target.inputs, target.outputs, target.metadata
    where = inputs.target_id
    root = source_root(repo, inputs.repo)

    if target.split != [SPLIT]:
        problems.append(f"split must be [{SPLIT!r}], got {target.split}")
    if inputs.repo not in EXPECTED_COUNTS:
        problems.append(f"unknown repo {inputs.repo!r}")
    if inputs.repo == "teamtrack" and inputs.pin != TEAMTRACK_PIN:
        problems.append(f"TeamTrack targets are pinned at {TEAMTRACK_PIN}, got {inputs.pin!r}")
    if root is not None and not (root / inputs.module).is_file():
        problems.append(f"module {inputs.module} not found in {inputs.repo}")

    problems += _check_ref(
        "filter_mutants", outputs.filter_mutants, "filter", inputs.module, repo, root
    )
    problems += _check_ref(
        "referee_mutants", outputs.referee_mutants, "referee", inputs.module, repo, root
    )
    if outputs.filter_mutants.partition("#")[0] != outputs.referee_mutants.partition("#")[0]:
        problems.append("filter_mutants and referee_mutants must name the same mutant file")

    if not inputs.existing_tests:
        problems.append("existing_tests is empty")
    for test in inputs.existing_tests:
        if root is not None and not (root / test.split("::", 1)[0]).exists():
            problems.append(f"existing test {test} not found in {inputs.repo}")
    for test in outputs.known_failures:
        if "::" not in test:
            problems.append(f"known failure {test!r} is not a test id")

    for key in REQUIRED_METADATA:
        if not meta.get(key):
            problems.append(f"metadata.{key} is missing")
    if meta.get("example_id") != inputs.target_id:
        problems.append("metadata.example_id must equal inputs.target_id")
    for key, value in LIBRARY_METADATA.get(inputs.repo, {}).items():
        if meta.get(key) != value:
            problems.append(f"metadata.{key} must be {value!r} for {inputs.repo}")
    return [f"{where}: {p}" for p in problems]


def check_testgen_file(lines: list[Any]) -> list[str]:
    """Problems with the whole file: line count, per-repo counts, unique ids and modules."""
    problems: list[str] = []
    targets = []
    for number, line in enumerate(lines, start=1):
        target, errors = _as_target(line)
        if target is None:
            problems.extend(f"line {number}: {e}" for e in errors)
        else:
            targets.append(target)
    if len(lines) != EXPECTED_TOTAL:
        problems.append(f"expected {EXPECTED_TOTAL} lines, got {len(lines)}")
    counts = Counter(t.inputs.repo for t in targets)
    for repo, expected in EXPECTED_COUNTS.items():
        if counts.get(repo, 0) != expected:
            problems.append(f"expected {expected} {repo} targets, got {counts.get(repo, 0)}")
    for repo in sorted(set(counts) - set(EXPECTED_COUNTS)):
        problems.append(f"unexpected repo {repo!r}")
    for target_id, n in sorted(Counter(t.inputs.target_id for t in targets).items()):
        if n > 1:
            problems.append(f"duplicate target_id {target_id} ({n} lines)")
    modules = Counter((t.inputs.repo, t.inputs.module) for t in targets)
    for (repo, module), n in sorted(modules.items()):
        if n > 1:
            problems.append(f"duplicate module {repo}:{module} ({n} lines)")
    return problems
