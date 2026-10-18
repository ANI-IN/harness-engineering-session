"""Checkpoints: the base product plus an ordered list of reference tasks.

`platform/teamtrack/reference/checkpoints.toml` names each checkpoint and its tasks. Main's
TeamTrack stays the base product; reference code lives only in its `reference/<task>/` as
`git apply` patches (paths relative to TeamTrack's directory):

- `<task>.patch` applies to the task's start checkpoint;
- `<task>.<checkpoint>.patch` replaces it where the default does not apply. When the task is in
  the checkpoint's list, that is the state the checkpoint has just before the task (used to build
  the checkpoint); otherwise it is the whole checkpoint (the task run from that checkpoint).

`materialize` builds a checkpoint in a directory from the working tree (tests, verification).
`build_commits` makes one commit per checkpoint whose parent is the current HEAD, in a temporary
index (no checkout, no branch moves), and tags it; only the integrator runs it without
`dry_run`. Task manifests (`reference/<task>/task.toml`) are read by `load_task`. A checkout or a
HEAD in the layout before the course-first one (TeamTrack at `teamtrack/`) still works:
TeamTrack's directory is resolved per checkout and per commit (`app_dir_at`).
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from shipharness.ab.workspace import APP_DIR, export_checkpoint
from shipharness.config.prices import REPO_ROOT
from shipharness.layout import app_dir_at

REFERENCE = Path(APP_DIR) / "reference"
CHECKPOINTS_FILE = REFERENCE / "checkpoints.toml"


def reference_dir(repo: Path) -> Path:
    """`<repo>/<TeamTrack>/reference` for the checkout `repo` (either layout)."""
    return Path(repo) / app_dir_at(Path(repo)) / "reference"


class CheckpointError(ValueError):
    pass


class ReferenceApplyError(CheckpointError):
    pass


@dataclass(frozen=True)
class Checkpoint:
    name: str
    tasks: list[str]
    description: str = ""


@dataclass(frozen=True)
class TaskManifest:
    """`<TeamTrack>/reference/<task>/task.toml` (builder contract §3)."""

    task: str  # directory name, e.g. "f1"
    id: str  # "F1"
    title: str
    section: str
    start_checkpoint: str
    primary_measure: str
    mutant_set: str
    session_budget: list[int]
    canonical_ticket: str
    allowed_paths: dict[str, list[str]]
    hidden: dict[str, list[str]] = field(default_factory=dict)


def load_checkpoints(repo: Path = REPO_ROOT) -> dict[str, Checkpoint]:
    data = tomllib.loads((reference_dir(repo) / "checkpoints.toml").read_text(encoding="utf-8"))
    return {
        name: Checkpoint(name, list(spec.get("tasks", [])), str(spec.get("description", "")))
        for name, spec in data.get("checkpoints", {}).items()
    }


def checkpoint(name: str, repo: Path = REPO_ROOT) -> Checkpoint:
    found = load_checkpoints(repo)
    if name not in found:
        raise CheckpointError(f"unknown checkpoint {name!r}; known: {sorted(found)}")
    return found[name]


def state_before(task: str, name: str, repo: Path = REPO_ROOT) -> list[str]:
    """Tasks already applied when `task` is applied at checkpoint `name`."""
    tasks = checkpoint(name, repo).tasks
    return tasks[: tasks.index(task)] if task in tasks else list(tasks)


def patch_for(task: str, name: str, repo: Path = REPO_ROOT) -> Path:
    folder = reference_dir(repo) / task
    variant = folder / f"{task}.{name}.patch"
    if variant.is_file():
        return variant
    default = folder / f"{task}.patch"
    if not default.is_file():
        raise CheckpointError(f"no reference patch for task {task!r} ({default.as_posix()})")
    return default


def _git_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(extra or {})
    return env


def apply_reference(task: str, name: str, build: Path, repo: Path = REPO_ROOT) -> Path:
    """Apply the task's reference patch for checkpoint `name` to the TeamTrack tree `build`."""
    patch = patch_for(task, name, repo)
    build = Path(build).resolve()
    # Never let git find a repository above the build: paths stay relative to the build.
    env = _git_env({"GIT_CEILING_DIRECTORIES": str(build.parent)})
    done = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "apply", "--whitespace=nowarn", str(patch)],
        cwd=build,
        capture_output=True,
        env=env,
        check=False,
    )
    if done.returncode != 0:
        detail = done.stderr.decode("utf-8", errors="replace").strip()[:800]
        raise ReferenceApplyError(f"{patch.name} does not apply at {name}: {detail}")
    return patch


def materialize(repo: Path, name: str, dest: Path) -> Path:
    """The checkpoint `name` as a TeamTrack tree in `dest`: the filtered working tree (what an
    arm workspace gets) plus the checkpoint's reference patches, in order."""
    spec = checkpoint(name, repo)
    export_checkpoint(Path(repo), None, Path(dest))
    for task in spec.tasks:
        apply_reference(task, name, Path(dest), repo)
    return Path(dest)


def load_task(task: str, repo: Path = REPO_ROOT) -> TaskManifest:
    path = reference_dir(repo) / task / "task.toml"
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return TaskManifest(
        task=task,
        id=data["id"],
        title=data["title"],
        section=data["section"],
        start_checkpoint=data["start_checkpoint"],
        primary_measure=data.get("primary_measure", ""),
        mutant_set=data["mutant_set"],
        session_budget=list(data["session_budget"]),
        canonical_ticket=data["canonical_ticket"],
        allowed_paths={k: list(v) for k, v in data["allowed_paths"].items()},
        hidden={k: list(v) for k, v in data.get("hidden", {}).items()},
    )


def task_names(repo: Path = REPO_ROOT, prefix: str = "") -> list[str]:
    root = reference_dir(repo)
    return sorted(
        p.name for p in root.iterdir() if (p / "task.toml").is_file() and p.name.startswith(prefix)
    )


# -- checkpoint commits (integrator) ------------------------------------------------------------


@dataclass(frozen=True)
class BuildResult:
    name: str
    tasks: list[str]
    tree: str
    commit: str | None  # None on a dry run


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    done = subprocess.run(
        ["git", "-c", "core.autocrlf=false", *args],
        cwd=repo,
        capture_output=True,
        env=env or _git_env(),
        check=False,
    )
    if done.returncode != 0:
        detail = done.stderr.decode("utf-8", errors="replace").strip()[:800]
        raise CheckpointError(f"git {' '.join(args[:2])} failed: {detail}")
    return done.stdout.decode("utf-8").strip()


def _tag_exists(repo: Path, name: str) -> bool:
    done = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{name}"],
        cwd=repo,
        capture_output=True,
        env=_git_env(),
        check=False,
    )
    return done.returncode == 0


def tag_commits(repo: Path, names: list[str]) -> dict[str, str]:
    """The commit each existing tag among `names` points at now (missing tags are left out)."""
    return {
        name: _git(Path(repo), "rev-parse", f"refs/tags/{name}^{{commit}}")
        for name in names
        if _tag_exists(Path(repo), name)
    }


def recorded_results(runs_dir: Path, exports_dir: Path) -> list[Path]:
    """Recorded results that name checkpoints by tag: every `<runs>/*/ab.json` and every JSON
    export under `<exports>` (scores, experiments). Tags must not move under them without an
    explicit approval."""
    found = sorted(Path(runs_dir).glob("*/ab.json")) if Path(runs_dir).is_dir() else []
    if Path(exports_dir).is_dir():
        found += sorted(p for p in Path(exports_dir).rglob("*.json") if p.is_file())
    return found


def build_commits(
    repo: Path = REPO_ROOT,
    names: list[str] | None = None,
    *,
    dry_run: bool = True,
    force: bool = False,
) -> list[BuildResult]:
    """One commit per checkpoint (parent: HEAD) with its reference patches applied to HEAD's
    tree, then a tag of the same name. A dry run applies everything in a temporary index and
    stops before committing. Existing tags are an error unless `force`."""
    repo = Path(repo)
    specs = load_checkpoints(repo)
    wanted = names or list(specs)
    unknown = [n for n in wanted if n not in specs]
    if unknown:
        raise CheckpointError(f"unknown checkpoint(s): {unknown}")
    if not dry_run and not force:
        taken = [n for n in wanted if _tag_exists(repo, n)]
        if taken:
            raise CheckpointError(f"tag(s) already exist: {taken} (use --force to move them)")
    head = _git(repo, "rev-parse", "HEAD^{commit}")
    app_dir = app_dir_at(repo, head)
    results: list[BuildResult] = []
    with tempfile.TemporaryDirectory(prefix="shipharness-checkpoint-") as tmp:
        for name in wanted:
            spec = specs[name]
            env = _git_env({"GIT_INDEX_FILE": str(Path(tmp) / f"{name}.index")})
            _git(repo, "read-tree", head, env=env)
            for task in spec.tasks:
                patch = patch_for(task, name, repo)
                try:
                    _git(repo, "apply", "--cached", f"--directory={app_dir}", str(patch), env=env)
                except CheckpointError as exc:
                    raise ReferenceApplyError(f"{patch.name} at {name}: {exc}") from None
            tree = _git(repo, "write-tree", env=env)
            commit = None
            if not dry_run:
                label = ", ".join(t.upper() for t in spec.tasks) or "no tasks"
                message = f"checkpoint {name}: base + {label}"
                commit = _git(repo, "commit-tree", tree, "-p", head, "-m", message)
                _git(repo, "tag", *(["-f"] if force else []), name, commit)
            results.append(BuildResult(name, list(spec.tasks), tree, commit))
    return results
