"""Line coverage via coverage.py JSON reports, measured inside the sandbox."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath

from shipharness.filters.models import CoverageMap
from shipharness.filters.pytest_cmd import UnsafeTestId, error_excerpt, pytest_command
from shipharness.filters.scratch import ScratchError, read_scratch_file, scratch_dir
from shipharness.filters.source import is_source_path
from shipharness.sandbox.base import Sandbox


@dataclass(frozen=True)
class CoverageRun:
    ok: bool
    coverage: CoverageMap = field(default_factory=CoverageMap)
    exit_code: int | None = None
    output: str = ""
    detail: str = ""


def _normalise(key: str, workspace: Path) -> str | None:
    text = key.replace("\\", "/")
    if text.startswith("/") or PureWindowsPath(key).drive:
        try:
            text = Path(key).resolve().relative_to(Path(workspace).resolve()).as_posix()
        except (ValueError, OSError):
            return None
    if ".." in PurePosixPath(text).parts:
        return None
    return text.removeprefix("./")


def parse_coverage_json(text: str, workspace: Path) -> CoverageMap:
    """Executed lines of source files from a `coverage json` report. The report was written by
    code running in the sandbox, so anything malformed is dropped rather than trusted."""
    try:
        data = json.loads(text)
    except ValueError:
        return CoverageMap()
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, dict):
        return CoverageMap()
    result: dict[str, frozenset[int]] = {}
    for key, info in files.items():
        if not isinstance(key, str) or not isinstance(info, dict):
            continue
        rel = _normalise(key, workspace)
        if rel is None or not is_source_path(rel):
            continue
        lines = info.get("executed_lines")
        if not isinstance(lines, list):
            continue
        result[rel] = frozenset(n for n in lines if isinstance(n, int) and not isinstance(n, bool))
    return CoverageMap(files=result)


def measure_coverage(
    workspace: Path,
    sandbox: Sandbox,
    tests: list[str],
    *,
    python: str = "python",
    timeout_s: int = 300,
    doctest_modules: bool = False,
) -> CoverageRun:
    """Run `tests` under coverage in the sandbox (cwd = workspace root) and read the report.

    Test failures still produce a report (exit code 1 is accepted); collection and usage errors
    do not. `doctest_modules` runs pytest with `--doctest-modules` (baseline with doctests).
    """
    try:
        with scratch_dir(workspace, "cov") as scratch:
            data = f"{scratch.name}/.coverage"
            run_cmd = (
                f'{python} -m coverage run --data-file="{data}" --source=. '
                + pytest_command("", tests, doctest_modules=doctest_modules).lstrip()
            )
            run = sandbox.exec(run_cmd, timeout_s)
            if run.timed_out:
                return CoverageRun(
                    False,
                    exit_code=run.exit_code,
                    output=run.output,
                    detail="coverage run timed out",
                )
            if run.exit_code not in (0, 1):
                return CoverageRun(
                    False,
                    exit_code=run.exit_code,
                    output=run.output,
                    detail=f"pytest exit code {run.exit_code}: {error_excerpt(run.output)}",
                )
            report = sandbox.exec(
                f'{python} -m coverage json --data-file="{data}" '
                f'-o "{scratch.name}/coverage.json" -q',
                timeout_s,
            )
            if report.exit_code != 0:
                return CoverageRun(
                    False,
                    exit_code=run.exit_code,
                    output=run.output,
                    detail=f"coverage json failed: {error_excerpt(report.output)}",
                )
            text = read_scratch_file(scratch, "coverage.json")
    except (UnsafeTestId, ScratchError, OSError) as exc:
        return CoverageRun(False, detail=str(exc)[:300])
    return CoverageRun(True, parse_coverage_json(text, workspace), run.exit_code, run.output)
