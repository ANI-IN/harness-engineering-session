"""Referee-set mutants for a task's `mutant_set` (the filter and referee sets are disjoint)."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

import structlog

from shipharness.layout import APP_DIR, app_dir_at, logical_path

MUTANT_DIR = Path(APP_DIR) / "mutants"
_LOGICAL_MUTANT_DIR = "teamtrack/mutants"  # how task manifests name it (any layout)


def _blob(course_repo: Path, ref: str, rel: Path) -> bytes | None:
    """The file `rel` at commit `ref` of the course repository (None when it does not exist)."""
    done = subprocess.run(
        ["git", "-C", str(course_repo), "show", f"{ref}:{rel.as_posix()}"],
        capture_output=True,
        check=False,
    )
    return done.stdout if done.returncode == 0 else None


def load_referee_mutants(mutant_set: str, course_repo: Path, ref: str | None = None) -> list[Any]:
    """`mutant_set` is a comma-separated list of module names (`app.services.issues`, resolved to
    TeamTrack's `mutants/<name>.jsonl`) or repo-relative `.jsonl` paths (`teamtrack/...` names
    TeamTrack's directory in either layout). Only the referee set is
    returned; filter-set mutants are never used to judge an arm. Records are validated, but not
    matched against source lines here: the arm may have changed a line, which the mutant runner
    reports as an error for that mutant. With `ref` (the A/B's pinned checkpoint commit), the
    files are read from that commit, so swap and replay judge with the mutants the A/B used."""
    from shipharness.filters import load_mutants

    mutants: list[Any] = []
    for token in (t.strip() for t in mutant_set.split(",")):
        if not token:
            continue
        logical = token if token.endswith(".jsonl") else f"{_LOGICAL_MUTANT_DIR}/{token}.jsonl"
        rel = Path(logical_path(logical, app_dir_at(Path(course_repo), ref)))
        if ref is None:
            path = Path(course_repo) / rel
            if not path.is_file():
                raise ValueError(f"unknown mutant set {token!r}: {rel.as_posix()} does not exist")
            mutants.extend(m for m in load_mutants(path, None) if m.set == "referee")
            continue
        data = _blob(Path(course_repo), ref, rel)
        if data is None:
            raise ValueError(f"unknown mutant set {token!r}: {rel.as_posix()} not at {ref[:12]}")
        with tempfile.TemporaryDirectory(prefix="shipharness-mutants-") as tmp:
            path = Path(tmp) / rel.name
            path.write_bytes(data)
            mutants.extend(m for m in load_mutants(path, None) if m.set == "referee")
    return mutants


def referee_mutants(
    mutant_set: str,
    course_repo: Path,
    given: list[Any] | None = None,
    *,
    ref: str | None = None,
) -> list[Any]:
    """Mutants that judge one task, for every path that runs the referee (A/B, swap test, replay,
    experiments). `given` wins when set. A missing set is logged and scored 0/0 instead of
    aborting a live run; dataset validation checks that every mutant set exists."""
    if given:
        return list(given)
    try:
        return load_referee_mutants(mutant_set, course_repo, ref)
    except ValueError as exc:
        structlog.get_logger(__name__).warning("referee mutants unavailable", reason=str(exc))
        return []
