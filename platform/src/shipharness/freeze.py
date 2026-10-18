"""Harness freeze: what the `harness-frozen` tag pins before the experiments.

When the pilot passes its pre-registered test, a freeze script creates an annotated tag at HEAD.
The experiments' results are valid only for that state. The tag pins four things:

- treatment, measurement, tasks, and environment files (`FROZEN_PATHS`): any change, or new file,
  under them after the tag is drift;
- a content hash per frozen path and the checkpoint tags' trees, so the check also works in the
  public repository, whose history is new (rule 2);
- the run settings that shape a run (`RUN_SETTINGS`), both the code defaults and the effective
  values (with `.env`); secrets are never recorded.

Rule 1: after the tag, a change to a frozen path passes only with an entry in the private
`FREEZE-EXCEPTIONS.toml` (its content hash, and either the experiments re-run or a recorded
check that it cannot change any score). No silent changes.

Console, report, replay tooling, docs, slides, and course content stay editable.

The release tag `class-v1` is separate: it is not a freeze. It records the content hashes of the
same paths, the checkpoint trees, and the run settings of the class release, so a learner can
check a copy with `shipharness verify --tag class-v1`.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from shipharness.config import Settings
from shipharness.layout import APP_DIR, LEGACY_APP_DIR

TAG = "harness-frozen"
CHECKPOINT_TAG_PREFIX = "m1-"
_MARKER = "frozen-record:"

CLASS_TAG = "class-v1"
CLASS_MESSAGE = (
    "Class version 1: the code, datasets, and settings used for the class. No experiment freeze; "
    "the pilot gate did not pass (see the course notes)."
)
_CLASS_MARKER = "class-record:"

FROZEN_PATHS: tuple[str, ...] = (
    # treatment
    "platform/src/shipharness/harness",
    "platform/src/shipharness/runner",  # loop, prompts, tools, patch formats
    "platform/src/shipharness/filters",
    "platform/teamtrack/harness",  # instruction files the harness places in the workspace
    # measurement
    "platform/src/shipharness/checks",  # checks and the check runner
    "platform/src/shipharness/reviewer",  # prompt and grading criteria
    "platform/src/shipharness/ab/artifacts.py",
    "platform/src/shipharness/ab/checkpoints.py",
    "platform/src/shipharness/ab/clients.py",
    "platform/src/shipharness/ab/commands.py",
    "platform/src/shipharness/ab/demo.py",
    "platform/src/shipharness/ab/experiments.py",
    "platform/src/shipharness/ab/mutants.py",
    "platform/src/shipharness/ab/referee.py",
    "platform/src/shipharness/ab/runtime.py",
    "platform/src/shipharness/ab/score.py",
    "platform/src/shipharness/ab/workspace.py",
    # tasks
    "platform/datasets",
    "platform/teamtrack/tests/hidden",
    "platform/teamtrack/mutants",
    "platform/teamtrack/reference",  # task manifests, reference patches, checkpoints.toml
    # environment
    "platform/sandbox/Dockerfile",
    "platform/src/shipharness/sandbox",  # policy and container execution
    "platform/src/shipharness/cost",  # caps and reservations
    "platform/config/prices.toml",
    "uv.lock",
    ".python-version",
)

RUN_SETTINGS: tuple[str, ...] = (
    "openai_model",
    "openai_reasoning_effort",
    "openai_eval_model",
    "openai_eval_reasoning_effort",
    "openai_service_tier",
    "max_run_cost_usd",
    "max_final_run_cost_usd",
    "max_review_cost_usd",
    "max_session_cost_usd",
    "max_batch_cost_usd",
    "max_experiment_total_usd",
    "max_build_total_usd",
    "max_turns_per_session",
    "max_output_tokens",
    "wrapup_turns",
    "tool_timeout_s",
    "run_timeout_s",
    "harness_timeout_s",
    "max_concurrency",
    "sandbox_mode",
    "sandbox_runtime",
    "sandbox_image_agent",
    "sandbox_image_referee",
    "sandbox_cpus",
)


class FreezeError(RuntimeError):
    """The tag cannot be created."""


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)


ABSENT = "absent"
EXCEPTIONS_FILE = "FREEZE-EXCEPTIONS.toml"  # private: accepted changes after the tag (rule 1)
EXCEPTION_KINDS = ("rerun", "no-score-effect")


def run_settings(settings: Settings) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key in RUN_SETTINGS:
        value = getattr(settings, key)
        values[key] = value if isinstance(value, int | float | bool) else str(value)
    return values


def checkpoint_tags(repo: Path) -> dict[str, str]:
    """Checkpoint tag name -> commit (informational: commit ids differ between repositories)."""
    names = _git(repo, "tag", "--list", f"{CHECKPOINT_TAG_PREFIX}*").stdout.split()
    return {name: _git(repo, "rev-parse", f"{name}^{{commit}}").stdout.strip() for name in names}


def checkpoint_trees(repo: Path) -> dict[str, str]:
    """Checkpoint tag name -> the id of its TeamTrack tree (what arms and the referee use; the
    build repository's checkpoint commits also hold private files, the public rebuild does not):
    `platform/teamtrack/`, or `teamtrack/` in a tag made before the course-first layout (the same
    tree id when the content is the same), or the whole tree when the tag has neither (compared,
    rule 2)."""
    names = _git(repo, "tag", "--list", f"{CHECKPOINT_TAG_PREFIX}*").stdout.split()
    trees: dict[str, str] = {}
    for name in names:
        for app in (APP_DIR, LEGACY_APP_DIR):
            sub = _git(repo, "rev-parse", "-q", "--verify", f"{name}:{app}")
            if sub.returncode == 0:
                trees[name] = sub.stdout.strip()
                break
        else:
            trees[name] = _git(repo, "rev-parse", f"{name}^{{tree}}").stdout.strip()
    return trees


def content_hashes(repo: Path, paths: list[str] | tuple[str, ...]) -> dict[str, str]:
    """SHA-256 per path over the working-tree bytes of its files (tracked plus untracked, ignored
    files excluded), independent of commit history. `ABSENT` when a path has no files."""
    hashes: dict[str, str] = {}
    root = Path(repo)
    for path in paths:
        listed = _git(
            repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", path
        ).stdout
        files = sorted({f for f in listed.split("\0") if f})
        digest = hashlib.sha256()
        present = 0
        for rel in files:
            file = root / rel
            if file.is_symlink():
                data = b"link:" + os.readlink(file).encode()
            elif file.is_file():
                data = file.read_bytes()
            else:
                continue  # deleted from the working tree
            present += 1
            digest.update(rel.encode() + b"\0" + hashlib.sha256(data).digest())
        hashes[path] = digest.hexdigest() if present else ABSENT
    return hashes


def make_record(repo: Path, effective: Settings) -> dict[str, Any]:
    return {
        "frozen_paths": list(FROZEN_PATHS),
        "content_hashes": content_hashes(repo, FROZEN_PATHS),
        "checkpoint_trees": checkpoint_trees(repo),
        "checkpoint_tags": checkpoint_tags(repo),
        "defaults": run_settings(Settings(_env_file=None)),
        "effective": run_settings(effective),
    }


def class_record(repo: Path, settings: Settings) -> dict[str, Any]:
    """The `class-v1` record: content hashes of `FROZEN_PATHS`, the checkpoint trees, and the run
    settings (secrets are never recorded)."""
    return {
        "tag": CLASS_TAG,
        "paths": list(FROZEN_PATHS),
        "content_hashes": content_hashes(repo, FROZEN_PATHS),
        "checkpoint_trees": checkpoint_trees(repo),
        "run_settings": run_settings(settings),
    }


def read_tag_record(repo: Path, tag: str) -> dict[str, Any] | None:
    """The JSON record after the marker line in an annotated tag's message; None without the tag."""
    if _git(repo, "rev-parse", "-q", "--verify", f"refs/tags/{tag}").returncode != 0:
        return None
    message = _git(repo, "tag", "--list", tag, "--format=%(contents)").stdout
    for marker in (_MARKER, _CLASS_MARKER):
        _, found, payload = message.partition(marker)
        if found:
            return json.loads(payload)
    raise FreezeError(f"{tag} has no record in its message")


def read_record(repo: Path) -> dict[str, Any] | None:
    return read_tag_record(repo, TAG)


def read_exceptions(repo: Path) -> tuple[dict[str, str], list[str]]:
    """Accepted changes (path -> content hash) and problems with the exceptions file. An entry is
    valid only with a kind, a verification-record reference, and (for re-runs) the experiments
    re-run."""
    file = Path(repo) / EXCEPTIONS_FILE
    if not file.is_file():
        return {}, []
    accepted: dict[str, str] = {}
    issues: list[str] = []
    for entry in tomllib.loads(file.read_text(encoding="utf-8")).get("change", []):
        path = str(entry.get("path", ""))
        complete = (
            path in FROZEN_PATHS
            and len(str(entry.get("content_hash", ""))) == 64
            and entry.get("kind") in EXCEPTION_KINDS
            and len(str(entry.get("verification", "")).strip()) >= 8
            and (entry.get("kind") != "rerun" or bool(entry.get("experiments")))
        )
        if complete:
            accepted[path] = str(entry["content_hash"])
        else:
            issues.append(
                f"exception incomplete: {path or '(no path)'} needs a frozen path, its content "
                "hash, kind rerun (with experiments) or no-score-effect, and a verification-record "
                "entry"
            )
    return accepted, issues


def expected_record(repo: Path) -> dict[str, Any] | None:
    """The tag's record with valid exceptions applied: what M8 results are valid for."""
    record = read_record(repo)
    if record is None:
        return None
    accepted, _ = read_exceptions(repo)
    return {**record, "content_hashes": {**record["content_hashes"], **accepted}}


def _message(record: dict[str, Any]) -> str:
    return (
        "Harness freeze before the experiments (course freeze rules 1 and 2). "
        "Their results are valid only for this content.\n\n"
        f"{_MARKER}\n{json.dumps(record, indent=2, sort_keys=True)}\n"
    )


def _tag(
    repo: Path, message: str, identity: tuple[str, str], tag: str = TAG, target: str = "HEAD"
) -> str:
    name, email = identity
    made = _git(
        repo,
        "-c",
        f"user.name={name}",
        "-c",
        f"user.email={email}",
        "tag",
        "-a",
        tag,
        "-m",
        message,
        target,
    )
    if made.returncode != 0:
        raise FreezeError(made.stderr.strip() or "git tag failed")
    return _git(repo, "rev-parse", f"{tag}^{{commit}}").stdout.strip()


def _dirty(repo: Path, paths: list[str]) -> list[str]:
    changed = _git(repo, "diff", "--name-only", "HEAD", "--", *paths).stdout.split()
    untracked = _git(
        repo, "ls-files", "--others", "--exclude-standard", "--", *paths
    ).stdout.split()
    return sorted(set(changed) | set(untracked))


def create_tag(repo: Path, effective: Settings, *, identity: tuple[str, str]) -> str:
    """Annotated `harness-frozen` tag at HEAD with the record in its message; returns the commit."""
    if _git(repo, "rev-parse", "-q", "--verify", f"refs/tags/{TAG}").returncode == 0:
        raise FreezeError(f"{TAG} exists; a new freeze needs a new decision and a re-run")
    dirty = _dirty(repo, list(FROZEN_PATHS))
    if dirty:
        raise FreezeError("uncommitted changes under frozen paths: " + ", ".join(dirty[:20]))
    return _tag(repo, _message(make_record(repo, effective)), identity)


def write_record_tag(repo: Path, record: dict[str, Any], *, identity: tuple[str, str]) -> str:
    """The same record as an annotated tag in another repository (the public release)."""
    if _git(repo, "rev-parse", "-q", "--verify", f"refs/tags/{TAG}").returncode == 0:
        raise FreezeError(f"{TAG} exists in {repo}")
    return _tag(repo, _message(record), identity)


def write_class_tag(
    repo: Path, record: dict[str, Any], *, identity: tuple[str, str], target: str = "HEAD"
) -> str:
    """Annotated `class-v1` tag at `target`: the owner's sentence, a blank line, then the record.
    Returns the commit it points at."""
    if _git(repo, "rev-parse", "-q", "--verify", f"refs/tags/{CLASS_TAG}").returncode == 0:
        raise FreezeError(f"{CLASS_TAG} exists in {repo}")
    payload = json.dumps(record, indent=2, sort_keys=True)
    message = f"{CLASS_MESSAGE}\n\n{_CLASS_MARKER}\n{payload}\n"
    return _tag(repo, message, identity, tag=CLASS_TAG, target=target)


def verify_copy(repo: Path, tag: str = CLASS_TAG) -> tuple[dict[str, Any] | None, list[str]]:
    """A working copy against a tag's record: (record, one line per difference), or (None, [])
    when the tag is not in the repository."""
    record = read_tag_record(repo, tag)
    if record is None:
        return None, []
    present = checkpoint_trees(repo)
    missing = sorted(name for name in record.get("checkpoint_trees", {}) if name not in present)
    found = [
        line
        for line in compare_content(repo, record)
        if line.removeprefix("checkpoint content differs: ") not in missing
    ]
    return record, found + [f"checkpoint tag missing: {n} (run git fetch --tags)" for n in missing]


def compare_content(repo: Path, record: dict[str, Any]) -> list[str]:
    """Frozen content of `repo` against `record` by content hash and checkpoint tree (rule 2)."""
    found: list[str] = []
    paths = record.get("frozen_paths") or record.get("paths") or list(FROZEN_PATHS)
    now = content_hashes(repo, paths)
    for path in paths:
        if now.get(path) != record.get("content_hashes", {}).get(path):
            found.append(f"content differs: {path}")
    trees = checkpoint_trees(repo)
    for name, tree in sorted(record.get("checkpoint_trees", {}).items()):
        if trees.get(name) != tree:
            found.append(f"checkpoint content differs: {name}")
    return found


def problems(repo: Path, effective: Settings) -> list[str]:
    """Everything that differs from the frozen state (valid exceptions applied); empty without
    the tag. Rule 1: a change passes only with a recorded re-run or a no-score-effect check."""
    expected = expected_record(repo)
    if expected is None:
        return []
    _, issues = read_exceptions(repo)
    found = compare_content(repo, expected) + issues
    for label, now in (
        ("defaults", run_settings(Settings(_env_file=None))),
        ("effective", run_settings(effective)),
    ):
        for key, value in sorted(expected.get(label, {}).items()):
            if now.get(key) != value:
                found.append(f"run setting changed ({label}): {key} {value!r} -> {now.get(key)!r}")
    return found
