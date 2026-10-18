"""Checks for `teamtrack-features-v1` beyond the line schema.

`check_features_line(line, repo)` checks one line against the course repository: the checkpoint is
defined in TeamTrack's `reference/checkpoints.toml`, every hidden test id exists in its file, the
mutant set resolves to a non-empty referee set whose every mutant applies at the line's checkpoint
(its `original` matches exactly one line there), the primary measure parses against `ScoreRecord`
(and is the measure registered for the feature, ruling R-5), and the allowed paths are non-empty
relative globs. `check_features_file(lines)` checks the whole file: group counts, split sizes,
unique example ids. Both return a list of messages; an empty list means the check passed.
"""

from __future__ import annotations

import ast
import hashlib
import tempfile
import tomllib
import types
import typing
from collections import Counter
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from pydantic import BaseModel, ValidationError

from shipharness.ab.score import ScoreRecord, evaluate_primary
from shipharness.datasets.schema import FeatureTask
from shipharness.layout import APP_DIR as LAYOUT_APP_DIR
from shipharness.layout import app_dir_at

APP_DIR = LAYOUT_APP_DIR
CHECKPOINTS_FILE = Path(APP_DIR) / "reference" / "checkpoints.toml"
HIDDEN_PREFIX = "tests/hidden/"

# Dataset groups (course design): 7 + 21 + 8 + 9 + 7 + 8 = 60 lines.
GROUP_COUNTS: dict[str, int] = {
    "canonical": 7,
    "reworded": 21,
    "alt_checkpoint": 8,
    "session_stop": 9,
    "trap": 7,
    "control": 8,
}
TOTAL_LINES = 60
SPLIT_SIZES: dict[str, int] = {
    "smoke": 6,
    "section-1": 8,
    "section-2": 8,
    "section-3": 8,
    "section-4": 8,
}
# Ruling R-5: the pre-registered primary measure per feature; F5-F7 and controls have none.
REGISTERED_PRIMARY: dict[str, str] = {
    "F1": "r1_new_violations>=1",
    "F2": "continuity_failure",
    "F3": "out_of_scope_files>=1 or test_phase_source_edits>=1",
    "F4": "hidden_passed,mutants_killed",
    "F5": "",
    "F6": "",
    "F7": "",
}


# -- hidden tests -------------------------------------------------------------------------------


def _is_parametrized(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any("parametrize" in ast.unparse(d) for d in node.decorator_list)


def collect_tests(path: Path) -> dict[str, bool]:
    """Test names pytest would collect from one file, read statically (the file is never
    imported): `test_x` or `TestGroup::test_x` -> True when the test is parametrized. A
    parametrized test gets ids like `test_x[1]`, which a dataset id `file::test_x` never matches."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))
    found: dict[str, bool] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test"
        ):
            found[node.name] = _is_parametrized(node)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef) and (
                    item.name.startswith("test")
                ):
                    found[f"{node.name}::{item.name}"] = _is_parametrized(item)
    return found


def hidden_test_ids(repo: Path, files: list[str]) -> list[str]:
    """Node ids (relative to the TeamTrack root, ruling R-1) for every test in `files`."""
    ids: list[str] = []
    app = app_dir_at(Path(repo))
    for rel in files:
        path = Path(repo) / app / rel
        if not path.is_file():
            raise FileNotFoundError(f"hidden test file {app}/{rel} does not exist")
        ids += [f"{rel}::{name}" for name in collect_tests(path)]
    return ids


def _check_hidden(ids: list[str], repo: Path) -> list[str]:
    if not ids:
        return ["outputs.hidden_test_ids: no hidden test ids"]
    errors: list[str] = []
    cache: dict[str, dict[str, bool] | None] = {}
    app = app_dir_at(Path(repo))
    for node_id in ids:
        rel, sep, name = node_id.partition("::")
        if not sep or not name or not rel.startswith(HIDDEN_PREFIX):
            errors.append(
                f"hidden id {node_id!r}: expected '{HIDDEN_PREFIX}<task>/<file>.py::<test>' "
                "(relative to the TeamTrack root, ruling R-1)"
            )
            continue
        if rel not in cache:
            path = Path(repo) / app / rel
            cache[rel] = collect_tests(path) if path.is_file() else None
        tests = cache[rel]
        if tests is None:
            errors.append(f"hidden id {node_id!r}: file {app}/{rel} does not exist")
        elif name not in tests:
            errors.append(f"hidden id {node_id!r}: no test {name!r} in {app}/{rel}")
        elif tests[name]:
            errors.append(
                f"hidden id {node_id!r}: parametrized tests get ids the referee cannot match"
            )
    return errors


# -- checkpoints --------------------------------------------------------------------------------


def checkpoints_file(repo: Path) -> Path:
    """`<TeamTrack>/reference/checkpoints.toml`, relative to the checkout `repo` (either layout)."""
    return Path(app_dir_at(Path(repo))) / "reference" / "checkpoints.toml"


def checkpoint_names(repo: Path) -> set[str]:
    """Checkpoint names defined in TeamTrack's `reference/checkpoints.toml`."""
    from shipharness.ab.checkpoints import load_checkpoints

    path = Path(repo) / checkpoints_file(repo)
    if not path.is_file():
        raise FileNotFoundError(f"{checkpoints_file(repo).as_posix()} not found")
    return set(load_checkpoints(Path(repo)))


# -- primary measure ----------------------------------------------------------------------------


def _is_bool_field(name: str) -> bool:
    annotation = ScoreRecord.model_fields[name].annotation
    if annotation is bool:
        return True
    if isinstance(annotation, types.UnionType) or typing.get_origin(annotation) is typing.Union:
        args = {a for a in typing.get_args(annotation) if a is not type(None)}
        return args == {bool}
    return False


def _check_primary(measure: str, feature_id: str) -> list[str]:
    text = measure.strip()
    errors: list[str] = []
    dummy: dict[str, Any] = dict.fromkeys(ScoreRecord.model_fields, 0)
    try:
        evaluate_primary(text, dummy)
    except KeyError as exc:
        return [f"outputs.primary_measure {measure!r}: unknown ScoreRecord field {exc.args[0]!r}"]
    except (TypeError, ValueError) as exc:
        return [f"outputs.primary_measure {measure!r}: does not parse ({exc})"]
    if text and "," not in text:
        for term in (t.strip() for t in text.split(" or ")):
            if term in ScoreRecord.model_fields and not _is_bool_field(term):
                errors.append(
                    f"outputs.primary_measure {measure!r}: bare field {term!r} is not boolean"
                )
    expected = REGISTERED_PRIMARY.get(feature_id, "" if feature_id.startswith("C") else None)
    if expected is not None and text != expected:
        errors.append(
            f"outputs.primary_measure {measure!r}: {feature_id} registers {expected!r} (ruling R-5)"
        )
    return errors


# -- mutants and paths --------------------------------------------------------------------------


def _check_mutants(mutant_set: str, repo: Path) -> list[str]:
    from shipharness.ab.mutants import load_referee_mutants
    from shipharness.filters.mutants import MutantError

    try:
        mutants = load_referee_mutants(mutant_set, Path(repo))
    except (ValueError, MutantError) as exc:
        return [f"outputs.mutant_set {mutant_set!r}: {exc}"]
    if not mutants:
        return [f"outputs.mutant_set {mutant_set!r}: no referee mutants"]
    return []


_TREES: dict[tuple[str, str, str], Path] = {}
_TREES_ROOT: list[tempfile.TemporaryDirectory[str]] = []


def _signature(repo: Path, name: str) -> str:
    """Hash of what a checkpoint is built from (its definition and its reference patches), so a
    cached tree is rebuilt when either changes."""
    from shipharness.ab import checkpoints as cp

    digest = hashlib.sha256((Path(repo) / checkpoints_file(repo)).read_bytes())
    for task in cp.checkpoint(name, repo).tasks:
        digest.update(cp.patch_for(task, name, repo).read_bytes())
    return digest.hexdigest()


def checkpoint_tree(repo: Path, name: str) -> Path:
    """The checkpoint `name` built from `repo` (base TeamTrack plus its reference patches). Each
    checkpoint is materialized once per process and cached in a temporary directory."""
    from shipharness.ab import checkpoints as cp

    key = (str(Path(repo).resolve()), name, _signature(repo, name))
    if key not in _TREES:
        if not _TREES_ROOT:
            _TREES_ROOT.append(tempfile.TemporaryDirectory(prefix="shipharness-checkpoints-"))
        dest = Path(_TREES_ROOT[0].name) / f"{len(_TREES)}-{name}"
        cp.materialize(Path(repo), name, dest)
        _TREES[key] = dest
    return _TREES[key]


def check_mutants_apply(mutant_set: str, checkpoint: str, repo: Path) -> list[str]:
    """Every referee mutant of `mutant_set` applies at `checkpoint`: its `original` matches
    exactly one line of its file there (mutants are located by text; the recorded line is a
    hint). An unknown set is reported by `_check_mutants`, not here."""
    from shipharness.ab.checkpoints import CheckpointError
    from shipharness.ab.mutants import load_referee_mutants
    from shipharness.filters.mutants import MutantError, check_against_source

    try:
        mutants = load_referee_mutants(mutant_set, Path(repo))
    except (ValueError, MutantError):
        return []
    try:
        tree = checkpoint_tree(Path(repo), checkpoint)
    except (CheckpointError, OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        return [
            f"outputs.mutant_set {mutant_set!r}: checkpoint {checkpoint!r} cannot be built ({exc})"
        ]
    errors: list[str] = []
    for m in mutants:
        try:
            check_against_source(m, tree)
        except MutantError as exc:
            errors.append(f"outputs.mutant_set {mutant_set!r}: at {checkpoint}: {exc}")
    return errors


def _bad_glob(pattern: str) -> bool:
    return (
        not pattern.strip()
        or "\\" in pattern
        or pattern.startswith("/")
        or bool(PureWindowsPath(pattern).drive)
        or ".." in PurePosixPath(pattern).parts
    )


def _check_paths(allowed: dict[str, list[str]]) -> list[str]:
    errors: list[str] = []
    for phase in ("build", "test"):
        patterns = allowed.get(phase)  # type: ignore[call-overload]
        if not patterns:
            errors.append(f"outputs.allowed_paths.{phase}: missing or empty")
            continue
        errors += [
            f"outputs.allowed_paths.{phase}: {p!r} is not a relative POSIX glob"
            for p in patterns
            if _bad_glob(p)
        ]
    return errors


# -- entry points -------------------------------------------------------------------------------


def _as_task(line: FeatureTask | BaseModel | dict[str, Any]) -> FeatureTask:
    if isinstance(line, FeatureTask):
        return line
    data = line.model_dump(mode="json") if isinstance(line, BaseModel) else line
    return FeatureTask.model_validate(data)


def check_features_line(
    line: FeatureTask | dict[str, Any], repo: Path, *, apply_mutants: bool | None = None
) -> list[str]:
    """Problems with one dataset line, checked against the course repository at `repo`.

    `apply_mutants` re-validates every referee mutant at the line's checkpoint (built from the
    reference patches, once per checkpoint). The default runs it when `repo` has the TeamTrack
    source (`platform/teamtrack/app`); repositories made of fixture manifests only have nothing to
    build."""
    try:
        task = _as_task(line)
    except ValidationError as exc:
        return [f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()]
    errors: list[str] = []
    try:
        if task.inputs.checkpoint not in checkpoint_names(repo):
            errors.append(
                f"inputs.checkpoint {task.inputs.checkpoint!r} is not defined in "
                f"{checkpoints_file(repo).as_posix()}"
            )
    except (FileNotFoundError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"inputs.checkpoint: cannot read {checkpoints_file(repo).as_posix()} ({exc})")
    checkpoint_ok = not errors
    errors += _check_hidden(task.outputs.hidden_test_ids, repo)
    mutant_errors = _check_mutants(task.outputs.mutant_set, repo)
    errors += mutant_errors
    if apply_mutants is None:
        apply_mutants = (Path(repo) / app_dir_at(Path(repo)) / "app").is_dir()
    if apply_mutants and checkpoint_ok and not mutant_errors:
        errors += check_mutants_apply(task.outputs.mutant_set, task.inputs.checkpoint, repo)
    errors += _check_primary(task.outputs.primary_measure, task.inputs.feature_id)
    errors += _check_paths(task.outputs.allowed_paths)
    example = task.metadata.get("example_id", task.inputs.feature_id)
    return [f"{example}: {e}" for e in errors]


def check_features_file(lines: list[FeatureTask] | list[dict[str, Any]]) -> list[str]:
    """Problems with the file as a whole: line total, group counts, split sizes, unique ids."""
    tasks: list[FeatureTask] = []
    errors: list[str] = []
    for number, line in enumerate(lines, start=1):
        try:
            tasks.append(_as_task(line))
        except ValidationError as exc:
            errors.append(f"line {number}: does not match the line schema ({exc.error_count()})")
    if len(lines) != TOTAL_LINES:
        errors.append(f"expected {TOTAL_LINES} lines, found {len(lines)}")
    groups = Counter(str(t.metadata.get("group")) for t in tasks)
    for group in sorted(set(groups) | set(GROUP_COUNTS)):
        want, got = GROUP_COUNTS.get(group, 0), groups.get(group, 0)
        if want != got:
            errors.append(f"group {group!r}: expected {want} lines, found {got}")
    splits = Counter(name for t in tasks for name in t.split)
    for name, size in SPLIT_SIZES.items():
        if splits.get(name, 0) != size:
            errors.append(f"split {name!r}: expected {size} lines, found {splits.get(name, 0)}")
    ids = Counter(str(t.metadata.get("example_id")) for t in tasks)
    errors += [f"duplicate example_id {i!r} ({n} lines)" for i, n in sorted(ids.items()) if n > 1]
    return errors
