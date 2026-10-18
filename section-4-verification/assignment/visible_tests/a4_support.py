"""Shared support for the A4 visible tests and the hidden grader tests.

- `impl_dir()`: the implementation under test (env `A4_IMPL`, default: the starter). Its folder is
  put first on `sys.path`, so `import a4_verification` loads that implementation.
- `make_build()`: a copy of TeamTrack's `app/` package with seeded violations applied as exact text
  patches. A patch whose old text is missing fails loudly, so a TeamTrack change cannot silently
  turn a seeded violation into a clean build.
- `run_r8()`: run the registered `r8_soft_delete` check on a build, in process (no Docker).
- `filter_context()`: a FilterContext for static filters (no sandbox, no coverage, no mutants).

Each test carries `@pytest.mark.criterion("<id>")`; the grader maps criteria to points.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent


def _course_root(assignment: Path) -> Path:
    """The course repository root: the nearest folder above `assignment` with a pyproject.toml
    (found by that marker, not a fixed depth), else the folder that holds the section folder."""
    for folder in assignment.parents:
        if (folder / "pyproject.toml").is_file():
            return folder
    return assignment.parents[1]


REPO = _course_root(ASSIGNMENT)
TEAMTRACK_APP = REPO / "platform" / "teamtrack" / "app"
STARTER = ASSIGNMENT / "starter"
CHECK_NAME = "r8_soft_delete"


def impl_dir() -> Path:
    raw = os.environ.get("A4_IMPL", "")
    path = Path(raw) if raw else STARTER
    if not path.is_absolute():
        path = (REPO / path).resolve()
    return path


def load_impl() -> Any:
    """Import `a4_verification` from the implementation folder (registers the R8 check)."""
    root = str(impl_dir())
    if root not in sys.path:
        sys.path.insert(0, root)
    return importlib.import_module("a4_verification")


# --- seeded builds -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Patch:
    """Replace `old` with `new` in `file` (relative to the build's `app/`), exactly once."""

    file: str
    old: str
    new: str


@dataclass(frozen=True)
class NewFile:
    """Add `file` (relative to the build's `app/`)."""

    file: str
    text: str


_INCLUDE_ANCHOR = "    app.include_router(board.router)\n"


def include_router(module: str) -> Patch:
    """Patch `app/main.py` so `create_app` also mounts `app.api.<module>.router`."""
    return Patch(
        "main.py",
        _INCLUDE_ANCHOR,
        f"    from app.api import {module}\n\n    app.include_router({module}.router)\n"
        + _INCLUDE_ANCHOR,
    )


def make_build(root: Path, changes: Sequence[Patch | NewFile] = ()) -> Path:
    """Copy TeamTrack's `app/` into `root/build/app` and apply `changes`; return the build dir."""
    build = root / "build"
    shutil.copytree(TEAMTRACK_APP, build / "app", ignore=shutil.ignore_patterns("__pycache__"))
    for change in changes:
        target = build / "app" / change.file
        if isinstance(change, NewFile):
            target.write_text(change.text, encoding="utf-8")
            continue
        text = target.read_text(encoding="utf-8")
        count = text.count(change.old)
        if count != 1:
            raise AssertionError(
                f"seeded patch for app/{change.file} matches {count} times (expected 1); "
                "TeamTrack changed: update the seed"
            )
        target.write_text(text.replace(change.old, change.new), encoding="utf-8")
    return build


# Visible seeded violations ------------------------------------------------------------------------

# Single-issue lookup ignores deleted_at: every /issues/{issue_id} operation resolves it.
V_GET = Patch(
    "repositories/issues.py",
    "        select(Issue).where(\n"
    "            Issue.org_id == org_id, Issue.id == issue_id, Issue.deleted_at.is_(None)\n"
    "        )\n",
    "        select(Issue).where(Issue.org_id == org_id, Issue.id == issue_id)\n",
)
V_GET_ENDPOINTS = {
    "GET /issues/{issue_id}",
    "PATCH /issues/{issue_id}",
    "DELETE /issues/{issue_id}",
    "POST /issues/{issue_id}/assign",
    "POST /issues/{issue_id}/transition",
}

# The project issue list ignores deleted_at.
V_LIST = Patch(
    "repositories/issues.py",
    "        Issue.org_id == org_id, Issue.project_id == project_id, Issue.deleted_at.is_(None)\n",
    "        Issue.org_id == org_id, Issue.project_id == project_id\n",
)

# The legacy /v1/issues list ignores deleted_at at the checkpoint itself: a baseline finding.
LEGACY = ("GET /v1/issues", "deleted_list")


# --- running the check ---------------------------------------------------------------------------


def run_r8(
    build: Path,
    *,
    exemptions: dict[str, list[str]] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    """Run the registered R8 check once on `build` and return its CheckResult."""
    load_impl()
    from shipharness.checks import CheckContext, get_check

    ctx = CheckContext(
        checkpoint="m1-base",
        feature_id="A4",
        seed=0,
        exemptions=dict(exemptions or {}),
        params=dict(params or {}),
    )
    return get_check(CHECK_NAME).run(build, ctx)


def counted_keys(result: Any) -> set[tuple[str | None, str]]:
    """(endpoint, detail_key) of every counted finding."""
    return {(f.endpoint, f.detail_key) for f in result.findings if f.counted}


def new_keys(result: Any) -> set[tuple[str | None, str]]:
    """(endpoint, detail_key) of every counted finding not marked as baseline."""
    return {(f.endpoint, f.detail_key) for f in result.findings if f.counted and not f.baseline}


# --- filters -------------------------------------------------------------------------------------


def filter_context(workspace: Path) -> Any:
    from shipharness.filters import CoverageMap, FilterContext

    return FilterContext(
        workspace=workspace,
        sandbox=None,
        baseline_coverage=CoverageMap(),
        filter_mutants=[],
        source_shas_at_phase_start={},
    )


def candidates(workspace: Path, files: dict[str, str]) -> list[Any]:
    """Write `files` (relative path -> source) under `workspace`; one candidate per test."""
    from shipharness.filters import collect_candidates

    for rel, source in files.items():
        path = workspace / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    return collect_candidates(workspace, list(files))


def dedup_filter(existing: list[Any] | None = None) -> Any:
    return load_impl().NoDuplicateTest(existing or [])


# --- portfolio and skill structure ---------------------------------------------------------------

PENDING = "[[PENDING:"
SMITH_LINK = re.compile(r"https://(?:eu\.)?smith\.langchain\.com/\S+")
TEMPLATE_PLACEHOLDER = re.compile(r"^\s*(?:#+|-|\d+\.)?\s*<[A-Z][^>]*>")


@dataclass(frozen=True)
class DocSpec:
    file: str
    headings: tuple[str, ...]
    must_contain: tuple[str, ...] = ()
    table_in: str | None = None  # a section that must hold a Markdown table
    link_in: str | None = None  # a section that must hold a LangSmith link
    words: tuple[int, int] | None = None  # inclusive word-count range (one page)


EVIDENCE = DocSpec(
    "portfolio/evidence-report.md",
    (
        "Target",
        "Commands",
        "Results",
        "Filter 6 on the kept tests",
        "House rule 8 on TeamTrack",
        "Limits",
    ),
    must_contain=("shipharness testgen", "run_r8"),
    table_in="Results",
)
LANGSMITH = DocSpec(
    "portfolio/langsmith.md",
    ("Trace links", "Command", "What the comparison shows"),
    must_contain=("shipharness ab",),
    link_in="Trace links",
)
CASE_STUDY = DocSpec(
    "portfolio/case-study.md",
    ("Problem", "What I built", "Evidence", "What I learned", "Next steps"),
    words=(250, 700),
)


def sections(text: str) -> dict[str, list[str]]:
    """Level-2 headings (lowercased) -> their content lines (HTML comments dropped)."""
    out: dict[str, list[str]] = {}
    current: str | None = None
    in_comment = False
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip().lower()
            out[current] = []
            continue
        stripped = line.strip()
        if in_comment or stripped.startswith("<!--"):
            in_comment = "-->" not in stripped
            continue
        if current is not None and stripped:
            out[current].append(stripped)
    return out


def doc_problems(root: Path, spec: DocSpec) -> list[str]:
    """Structure problems of one portfolio page; a [[PENDING]] marker is one, in every folder."""
    path = root / spec.file
    if not path.is_file():
        return [f"{spec.file}: missing"]
    text = path.read_text(encoding="utf-8")
    problems: list[str] = []
    found = sections(text)
    for heading in spec.headings:
        lines = found.get(heading.lower())
        if lines is None:
            problems.append(f"{spec.file}: missing section '## {heading}'")
        elif not lines:
            problems.append(f"{spec.file}: section '## {heading}' is empty")
    if re.search(r"\bTODO\b", text):
        problems.append(f"{spec.file}: still contains TODO")
    if PENDING in text:
        problems.append(f"{spec.file}: replace the [[PENDING ...]] markers with your run's output")
    for needle in spec.must_contain:
        if needle not in text:
            problems.append(f"{spec.file}: does not mention `{needle}`")

    def section_has(name: str, test: re.Pattern[str]) -> bool:
        return any(test.search(line) for line in found.get(name.lower(), []))

    if spec.table_in and not section_has(spec.table_in, re.compile(r"^\|.*\|$")):
        problems.append(f"{spec.file}: section '## {spec.table_in}' has no Markdown table")
    if spec.link_in and not section_has(spec.link_in, SMITH_LINK):
        problems.append(f"{spec.file}: section '## {spec.link_in}' has no smith.langchain.com link")
    if spec.words:
        low, high = spec.words
        count = len(re.findall(r"[A-Za-z0-9][\w'’.-]*", text))
        if not low <= count <= high:
            problems.append(f"{spec.file}: {count} words; one page means {low} to {high}")
    return problems


def skill_problems(root: Path) -> list[str]:
    """The learner's own skill: one folder under `skill/`, valid, and not the template."""
    from shipharness.skills_cli.validate import validate_path

    base = root / "skill"
    folders = sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []
    folders = [p for p in folders if (p / "SKILL.md").is_file()]
    if len(folders) != 1:
        names = [p.name for p in folders]
        return [f"skill/: expected exactly one folder with a SKILL.md, found {names}"]
    folder = folders[0]
    problems: list[str] = []
    for report in validate_path(folder):
        problems.extend(f"skill/{folder.name}: {message}" for message in report.errors)
    if folder.name == "skill-template":
        problems.append("skill/: rename the folder and the `name` field (still skill-template)")
    text = (folder / "SKILL.md").read_text(encoding="utf-8")
    template = (REPO / "use-in-your-repo" / "skills" / "skill-template" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    template_description = template.split("description:", 1)[1].split("license:", 1)[0]
    if template_description.strip() in text:
        problems.append(f"skill/{folder.name}: the description is still the template's")
    placeholders = [line.strip() for line in text.splitlines() if TEMPLATE_PLACEHOLDER.match(line)]
    if placeholders:
        problems.append(f"skill/{folder.name}: template placeholders left: {placeholders[:3]}")
    found = sections(text)
    for heading in ("When to use", "Steps"):
        if not found.get(heading.lower()):
            problems.append(f"skill/{folder.name}: missing or empty section '## {heading}'")
    return problems


# --- pytest wiring -------------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "criterion(id): grading criterion this test counts toward")


# Outcomes for check.py and grade.py: env A4_RESULTS names a JSON file written at session end.
# Both conftests import these hooks, so each event may arrive twice; dicts keep that idempotent.
_CRITERIA: dict[str, str] = {}
_OUTCOMES: dict[str, dict[str, Any]] = {}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        marker = item.get_closest_marker("criterion")
        _CRITERIA[item.nodeid] = str(marker.args[0]) if marker and marker.args else ""


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    entry = _OUTCOMES.setdefault(report.nodeid, {"passed": False, "message": ""})
    if report.when == "call" and report.passed:
        entry["passed"] = True
    if report.failed or report.skipped:
        entry["passed"] = False
        if not entry["message"]:
            entry["message"] = _short(report)


def _short(report: pytest.TestReport) -> str:
    crash = getattr(report.longrepr, "reprcrash", None)
    if crash is not None:
        return str(crash.message)
    if report.skipped and isinstance(report.longrepr, tuple):
        return f"skipped: {report.longrepr[2]}"
    return str(report.longrepr).strip().splitlines()[-1] if report.longrepr else report.outcome


def pytest_sessionfinish(session: pytest.Session) -> None:
    target = os.environ.get("A4_RESULTS")
    if not target:
        return
    rows = [
        {"nodeid": nodeid, "criterion": criterion, **_OUTCOMES.get(nodeid, {"passed": False})}
        for nodeid, criterion in _CRITERIA.items()
    ]
    Path(target).write_text(json.dumps(rows, indent=1), encoding="utf-8")


@pytest.fixture
def impl() -> Any:
    return load_impl()


@pytest.fixture
def impl_path() -> Path:
    return impl_dir()
