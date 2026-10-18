"""Hand-written mutants and the targeted mutant runner.

A mutant replaces one line of one source file. The line is found by its exact text (`original` must
match exactly one line of the file); the recorded line number is a hint for messages, so a mutant
keeps applying when lines are added above it. It is applied to a temporary copy of the workspace,
never to the workspace itself, and the given tests run against that copy in the sandbox. Each
module's mutants are split into a filter set (used by filter 3) and a referee set (held out for the
referee); the two sets never overlap.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from shipharness.events import Arm, EventBus
from shipharness.filters.pytest_cmd import (
    UnsafeTestId,
    check_test_id,
    counts,
    first_failure,
    pytest_command,
)
from shipharness.filters.scratch import ScratchError, copy_workspace, scratch_dir
from shipharness.sandbox.base import Sandbox

MutantSet = Literal["filter", "referee"]
Outcome = Literal["killed", "survived", "timeout", "error"]


class MutantError(ValueError):
    """A mutant record is invalid or does not match its source line."""


class Mutant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str  # "<target>-m<n>"
    target: str  # module path, dotted (for example "app.services.issues")
    set: MutantSet
    file: str  # POSIX path relative to the repository root
    line: int  # 1-based; a hint for messages (the line is found by `original`)
    original: str  # exact text of the one line it changes, without the line ending
    replacement: str
    rationale: str  # the risky behaviour it simulates

    @field_validator("file")
    @classmethod
    def _relative_posix(cls, value: str) -> str:
        if (
            not value
            or "\\" in value
            or value.startswith("/")
            or PureWindowsPath(value).drive
            or ".." in PurePosixPath(value).parts
        ):
            raise ValueError(f"file must be a relative POSIX path, got {value!r}")
        return value

    @field_validator("line")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("line is 1-based")
        return value

    @field_validator("original", "replacement")
    @classmethod
    def _one_line(cls, value: str) -> str:
        if "\n" in value or "\r" in value:
            raise ValueError("original and replacement are single lines")
        return value

    @model_validator(mode="after")
    def _id_names_target(self) -> Mutant:
        if not re.fullmatch(re.escape(self.target) + r"-m\d+", self.id):
            raise ValueError(f"id must be '<target>-m<n>', got {self.id!r}")
        return self


def _split_ending(line: str) -> tuple[str, str]:
    for ending in ("\r\n", "\n", "\r"):
        if line.endswith(ending):
            return line[: -len(ending)], ending
    return line, ""


def source_line(text: str, line: int) -> str | None:
    lines = text.splitlines(keepends=True)
    if line > len(lines):
        return None
    return _split_ending(lines[line - 1])[0]


def _matches(lines: list[str], original: str) -> list[int]:
    return [n for n, line in enumerate(lines, start=1) if _split_ending(line)[0] == original]


def locate(text: str, m: Mutant) -> int:
    """The 1-based line of `text` whose full content (without its line ending) is `m.original`.
    The mutant is found by its text, so lines added or removed above it do not matter; the
    recorded `line` is only a hint for messages. No match, or more than one, is a MutantError."""
    found = _matches(text.splitlines(keepends=True), m.original)
    if not found:
        raise MutantError(f"{m.id}: original not found in {m.file} (recorded at line {m.line})")
    if len(found) > 1:
        where = ", ".join(str(n) for n in found)
        raise MutantError(
            f"{m.id}: original matches {len(found)} lines of {m.file} ({where}); "
            "it must match exactly one"
        )
    return found[0]


def apply_mutant(text: str, m: Mutant) -> str:
    """Return `text` with the one line equal to `m.original` replaced by `m.replacement`."""
    lines = text.splitlines(keepends=True)
    number = locate(text, m)
    ending = _split_ending(lines[number - 1])[1]
    lines[number - 1] = m.replacement + ending
    return "".join(lines)


def check_against_source(m: Mutant, source_root: Path) -> None:
    """Raise MutantError unless `m.original` matches exactly one line of its file."""
    path = Path(source_root) / m.file
    if not path.is_file():
        raise MutantError(f"{m.id}: {m.file} not found under {source_root}")
    locate(path.read_bytes().decode("utf-8"), m)


def load_mutants(path: Path, source_root: Path | None) -> list[Mutant]:
    """Load one JSONL mutant file. With `source_root`, every `original` must match exactly one
    line of its file; pass None only to check the records themselves."""
    path = Path(path)
    mutants: list[Mutant] = []
    seen: set[str] = set()
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        where = f"{path.name}:{number}"
        try:
            m = Mutant.model_validate(json.loads(raw))
        except (ValidationError, ValueError) as exc:
            raise MutantError(f"{where}: {exc}") from None
        if m.id in seen:
            raise MutantError(f"{where}: duplicate id {m.id}")
        seen.add(m.id)
        if source_root is not None:
            try:
                check_against_source(m, source_root)
            except MutantError as exc:
                raise MutantError(f"{where}: {exc}") from None
        mutants.append(m)
    return mutants


def load_mutant_ref(ref: str, source_root: Path | None) -> list[Mutant]:
    """`path/to/module.jsonl#filter` (one set) or `path/to/module.jsonl` (all)."""
    path, _, wanted = ref.partition("#")
    mutants = load_mutants(Path(path), source_root)
    if wanted:
        if wanted not in ("filter", "referee"):
            raise MutantError(f"unknown mutant set {wanted!r} in {ref}")
        mutants = [m for m in mutants if m.set == wanted]
    return mutants


@dataclass(frozen=True)
class MutantRun:
    outcome: Outcome
    killed_by: str | None = None
    detail: str = ""
    duration_ms: int = 0


def _classify(exit_code: int, output: str) -> tuple[Outcome, str | None, str]:
    totals = counts(output)
    node, message = first_failure(output)
    if exit_code == 0:
        if totals["passed"] >= 1:
            return "survived", None, f"{totals['passed']} passed"
        return "error", None, "no tests ran"
    if exit_code in (1, 2) and (node or totals["failed"] or totals["errors"]):
        reason = message or ("collection error" if exit_code == 2 else "test failed")
        return "killed", node or ("collection error" if exit_code == 2 else None), reason
    return "error", None, f"pytest exit code {exit_code}"


def run_mutant_detailed(
    m: Mutant,
    tests: list[str],
    workdir: Path,
    sandbox: Sandbox,
    timeout_s: int,
    *,
    python: str = "python",
    doctest_modules: bool = False,
) -> MutantRun:
    """Apply `m` to a temporary copy of `workdir` and run `tests` there (stop at first failure).
    `doctest_modules` adds `--doctest-modules` (existing suite whose baseline has doctests)."""
    try:
        for test in tests:
            check_test_id(test)
    except UnsafeTestId as exc:
        return MutantRun("error", detail=str(exc))
    try:
        with scratch_dir(workdir, "mutant") as copy:
            copy_workspace(workdir, copy)
            target = copy / m.file
            if not target.is_file():
                return MutantRun("error", detail=f"{m.file} not found in the workspace")
            target.write_bytes(apply_mutant(target.read_bytes().decode("utf-8"), m).encode("utf-8"))
            command = f'cd "{copy.name}" && ' + pytest_command(
                python, tests, extra="-x", doctest_modules=doctest_modules
            )
            result = sandbox.exec(command, timeout_s)
    except (MutantError, ScratchError, UnicodeDecodeError, OSError) as exc:
        return MutantRun("error", detail=str(exc)[:300])
    if result.timed_out:
        return MutantRun("timeout", detail="tests exceeded the time limit", duration_ms=0)
    if result.denied is not None:
        return MutantRun("error", detail=f"sandbox denied: {result.denied.reason_code}")
    outcome, killed_by, detail = _classify(result.exit_code, result.output)
    return MutantRun(outcome, killed_by, detail, result.duration_ms)


def run_mutant(
    m: Mutant,
    tests: list[str],
    workdir: Path,
    sandbox: Sandbox,
    timeout_s: int,
    *,
    python: str = "python",
    doctest_modules: bool = False,
) -> Outcome:
    return run_mutant_detailed(
        m, tests, workdir, sandbox, timeout_s, python=python, doctest_modules=doctest_modules
    ).outcome


def run_mutant_set(
    mutants: list[Mutant],
    tests: list[str],
    workdir: Path,
    sandbox: Sandbox,
    timeout_s: int,
    *,
    bus: EventBus | None = None,
    run_id: str | None = None,
    arm: Arm | None = None,
    python: str = "python",
    doctest_modules: bool = False,
) -> dict[str, MutantRun]:
    """Run mutants one at a time and emit one `mutant_result` event each."""
    runs: dict[str, MutantRun] = {}
    for m in mutants:
        run = run_mutant_detailed(
            m, tests, workdir, sandbox, timeout_s, python=python, doctest_modules=doctest_modules
        )
        runs[m.id] = run
        if bus is not None:
            bus.publish(
                "mutant_result",
                {
                    "mutant_id": m.id,
                    "set": m.set,
                    "outcome": run.outcome,
                    "killed_by": run.killed_by,
                },
                run_id=run_id,
                arm=arm,
            )
    return runs
