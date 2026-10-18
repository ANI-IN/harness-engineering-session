#!/usr/bin/env python3
"""Assess a repository's harness for coding agents and write an HTML report.

Usage:
    python assess.py <repo> [--out harness-assessment.html] [--json]

Five areas: instructions, state, scope, verification, session lifecycle. Every check names the
source it comes from (a short name such as "OpenAI, Harness engineering"; the skill's README lists
each source in full) and the template that fixes it.

The assessment is deterministic and read-only: it reads files, never runs code from the repository,
never calls a network or a model, never follows a link that leaves the repository, and writes no
timestamps, so the same repository gives a byte-identical report. Keyword checks are heuristics
and say so in their evidence. Standard library only (Python 3.10+).
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

AREAS = ("Instructions", "State", "Scope", "Verification", "Session lifecycle")
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache", ".ruff_cache"}
MAX_FILES = 20_000
MAX_READ = 1_000_000  # bytes read from any one file
# Course thresholds around the "roughly 100 lines" in OpenAI, Harness engineering; the source
# gives no hard limit.
MAP_PASS_LINES = 150
MAP_PARTIAL_LINES = 300
A1_DOCS = (
    "docs/SECURITY.md",
    "docs/RELIABILITY.md",
    "docs/QUALITY_SCORE.md",
    "docs/PLANS.md",
    "docs/design-docs",
    "docs/product-specs",
    "docs/references",
    "docs/exec-plans",
)
TEST_FILE = re.compile(r"(^test_.*\.py$|_test\.py$|\.(test|spec)\.[jt]sx?$|_test\.go$)")
POINTER_LINK = re.compile(r"\[[^\]]*\]\(\s*([^)\s]+)\s*\)")
POINTER_CODE = re.compile(r"`([^`\s<>*]+)`")
FILE_LIKE = re.compile(r"(/|\.(md|json|sh|py|txt|toml|ya?ml|ini|cfg)$)")


@dataclass(frozen=True)
class Check:
    id: str
    area: str
    title: str
    status: str  # "pass" | "partial" | "fail"
    evidence: str
    fix: str
    source: str


class Repo:
    """Read-only view of a repository that never leaves its root."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._files: list[str] | None = None

    def path(self, rel: str) -> Path | None:
        """The path if it exists inside the root after resolving links, else None."""
        candidate = self.root / rel
        try:
            resolved = candidate.resolve()
        except OSError:
            return None
        if resolved != self.root and not resolved.is_relative_to(self.root):
            return None
        return resolved if resolved.exists() else None

    def is_file(self, rel: str) -> bool:
        found = self.path(rel)
        return found is not None and found.is_file()

    def is_dir(self, rel: str) -> bool:
        found = self.path(rel)
        return found is not None and found.is_dir()

    def read(self, rel: str) -> str | None:
        found = self.path(rel)
        if found is None or not found.is_file():
            return None
        with found.open("rb") as handle:
            return handle.read(MAX_READ).decode("utf-8", errors="replace")

    def files(self) -> list[str]:
        """Repository-relative POSIX paths of regular files, sorted, links not followed."""
        if self._files is None:
            found: list[str] = []
            for current, dirs, names in os.walk(self.root, followlinks=False):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                base = Path(current)
                for name in sorted(names):
                    full = base / name
                    if full.is_symlink():
                        continue
                    found.append(full.relative_to(self.root).as_posix())
                    if len(found) >= MAX_FILES:
                        break
                if len(found) >= MAX_FILES:
                    break
            self._files = sorted(found)
        return self._files

    def listing(self, rel: str, suffixes: tuple[str, ...] = ()) -> list[str]:
        prefix = rel.rstrip("/") + "/"
        return [
            f
            for f in self.files()
            if f.startswith(prefix) and (not suffixes or f.endswith(suffixes))
        ]


def _status(ok: bool, partial: bool = False) -> str:
    return "pass" if ok else ("partial" if partial else "fail")


def _agent_docs(repo: Repo) -> str:
    """Text of the agent instruction files, lower-cased, for keyword checks."""
    parts = [repo.read(name) or "" for name in ("AGENTS.md", "CLAUDE.md")]
    return "\n".join(parts).lower()


def _pointers(text: str) -> list[str]:
    found: list[str] = []
    for match in POINTER_LINK.finditer(text):
        found.append(match.group(1))
    for match in POINTER_CODE.finditer(text):
        found.append(match.group(1))
    result: list[str] = []
    for target in found:
        target = target.split("#", 1)[0]
        if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE):
            continue
        if target.startswith("./"):
            target = target[2:]
        if FILE_LIKE.search(target) and target not in result:
            result.append(target)
    return result


# --- areas ---------------------------------------------------------------------------------


def instructions(repo: Repo) -> list[Check]:
    area = "Instructions"
    agents = repo.read("AGENTS.md")
    checks = []
    if agents is not None:
        status, evidence = "pass", "AGENTS.md found at the repository root"
    elif repo.is_file("CLAUDE.md"):
        status, evidence = (
            "partial",
            ("only CLAUDE.md found; the map in OpenAI, Harness engineering is a root AGENTS.md"),
        )
    else:
        status, evidence = "fail", "no AGENTS.md at the repository root"
    checks.append(
        Check(
            "I1",
            area,
            "AGENTS.md map at the repository root",
            status,
            evidence,
            "assets/templates/AGENTS.md",
            "OpenAI, Harness engineering",
        )
    )

    if agents is None:
        status, evidence = "fail", "no AGENTS.md to measure"
    else:
        lines = len(agents.splitlines())
        status = _status(lines <= MAP_PASS_LINES, lines <= MAP_PARTIAL_LINES)
        evidence = (
            f"{lines} lines (pass at {MAP_PASS_LINES} or fewer, partial up to {MAP_PARTIAL_LINES}:"
            " course thresholds around the roughly 100 lines in OpenAI, Harness engineering)"
        )
    checks.append(
        Check(
            "I2",
            area,
            "AGENTS.md is short and points elsewhere",
            status,
            evidence,
            "move rules into docs/ and keep pointers in AGENTS.md",
            "OpenAI, Harness engineering",
        )
    )

    if agents is None:
        status, evidence = "fail", "no AGENTS.md to check"
    else:
        pointers = _pointers(agents)
        missing = [p for p in pointers if repo.path(p.rstrip("/")) is None]
        if not pointers:
            status, evidence = "fail", "AGENTS.md has no file pointers; a map points to docs"
        elif missing:
            shown = ", ".join(missing[:5]) + (" ..." if len(missing) > 5 else "")
            status = "partial"
            evidence = f"{len(missing)} of {len(pointers)} pointers do not resolve: {shown}"
        else:
            status, evidence = "pass", f"all {len(pointers)} pointers resolve"
    checks.append(
        Check(
            "I3",
            area,
            "Every pointer in AGENTS.md resolves",
            status,
            evidence,
            "create the missing files or fix the paths",
            "OpenAI, Harness engineering",
        )
    )

    if repo.is_file("ARCHITECTURE.md"):
        status, evidence = "pass", "ARCHITECTURE.md found at the root"
    elif repo.is_file("docs/ARCHITECTURE.md"):
        status, evidence = (
            "partial",
            ("docs/ARCHITECTURE.md found; OpenAI, Harness engineering keeps it at the root"),
        )
    else:
        status, evidence = "fail", "no ARCHITECTURE.md"
    checks.append(
        Check(
            "I4",
            area,
            "ARCHITECTURE.md maps domains and layers",
            status,
            evidence,
            "assets/templates/ARCHITECTURE.md",
            "OpenAI, Harness engineering",
        )
    )

    present = [d for d in A1_DOCS if repo.path(d) is not None]
    docs_md = repo.listing("docs", (".md",))
    status = "pass" if len(present) >= 4 else _status(False, bool(present or docs_md))
    evidence = (
        f"{len(present)} of {len(A1_DOCS)} entries from the docs/ layout in "
        "OpenAI, Harness engineering"
        + (f": {', '.join(present)}" if present else "")
        + f"; Markdown files under docs/: {len(docs_md)}"
    )
    checks.append(
        Check(
            "I5",
            area,
            "docs/ is the system of record",
            status,
            evidence,
            "assets/templates/SECURITY.md and the docs layout reference",
            "OpenAI, Harness engineering",
        )
    )

    skill_dirs = []
    for root in (".agents/skills", ".claude/skills"):
        valid = [
            f
            for f in repo.listing(root, ("/SKILL.md",))
            if f.count("/") == root.count("/") + 2 and _has_skill_frontmatter(repo.read(f) or "")
        ]
        if valid:
            skill_dirs.append(f"{root}/ ({len(valid)})")
    status = _status(len(skill_dirs) == 2, len(skill_dirs) == 1)
    evidence = (
        ("skills found in " + ", ".join(skill_dirs)) if skill_dirs else "no skills found"
    ) + "; Claude Code reads .claude/skills/, Codex reads .agents/skills/, Cursor reads both"
    checks.append(
        Check(
            "I6",
            area,
            "Skills where every agent can load them",
            status,
            evidence,
            "skills/skill-template, installed in both folders",
            "Agent Skills, Specification; Claude Code, Skills; Codex, Skills; Cursor, Skills "
            "(install paths)",
        )
    )
    return checks


def _has_skill_frontmatter(text: str) -> bool:
    if not text.startswith("---"):
        return False
    head = text.split("---", 2)[1] if text.count("---") >= 2 else ""
    return bool(re.search(r"^name:\s*\S", head, re.M) and re.search(r"^description:", head, re.M))


def state(repo: Repo) -> list[Check]:
    area = "State"
    progress = next(
        (n for n in ("progress.md", "PROGRESS.md", "claude-progress.txt") if repo.is_file(n)), None
    )
    checks = [
        Check(
            "S1",
            area,
            "A progress file records what agents have done",
            "pass" if progress else "fail",
            f"{progress} found" if progress else "no progress.md or claude-progress.txt",
            "assets/templates/progress.md",
            "Anthropic, Effective harnesses",
        )
    ]
    if repo.is_file("init.sh"):
        text = repo.read("init.sh") or ""
        status = _status(text.startswith("#!"), True)
        evidence = "init.sh found" + ("" if text.startswith("#!") else " (no #! line)")
    elif any(f.endswith("/init.sh") for f in repo.files()):
        status = "partial"
        evidence = "init.sh found below the root: " + next(
            f for f in repo.files() if f.endswith("/init.sh")
        )
    else:
        status, evidence = "fail", "no init.sh"
    checks.append(
        Check(
            "S2",
            area,
            "init.sh starts the app and runs a smoke test",
            status,
            evidence,
            "assets/templates/init.sh",
            "Anthropic, Effective harnesses",
        )
    )
    plans = repo.listing("docs/exec-plans", (".md",))
    if plans:
        status, evidence = "pass", f"{len(plans)} exec plan files under docs/exec-plans/"
    elif repo.is_file("docs/PLANS.md") or repo.is_file("PLANS.md"):
        status, evidence = "partial", "PLANS.md found but no plans under docs/exec-plans/"
    else:
        status, evidence = "fail", "no exec plans and no PLANS.md"
    checks.append(
        Check(
            "S3",
            area,
            "Exec plans are checked into the repository",
            status,
            evidence,
            "assets/templates/exec-plan.md in docs/exec-plans/active/",
            "OpenAI, Harness engineering; OpenAI, Exec plans",
        )
    )
    has_git = (repo.root / ".git").exists()
    checks.append(
        Check(
            "S4",
            area,
            "Git history is available to the agent",
            "pass" if has_git else "fail",
            ".git found (not read)" if has_git else "no .git in this folder",
            "git init and commit the harness files",
            "Anthropic, Effective harnesses",
        )
    )
    return checks


def scope(repo: Repo) -> list[Check]:
    area = "Scope"
    checks = []
    features: list | None = None
    raw = repo.read("feature_list.json")
    if raw is None:
        status, evidence = "fail", "no feature_list.json"
    else:
        try:
            data = json.loads(raw)
            features = data.get("features") if isinstance(data, dict) else data
            if not isinstance(features, list) or not features:
                status, evidence = "fail", "feature_list.json has no list of features"
                features = None
            else:
                status, evidence = "pass", f"{len(features)} features listed"
        except json.JSONDecodeError as exc:
            status, evidence = "fail", f"feature_list.json is not valid JSON: {exc.msg}"
    checks.append(
        Check(
            "C1",
            area,
            "feature_list.json lists the work",
            status,
            evidence,
            "assets/templates/feature_list.json",
            "Anthropic, Effective harnesses; Anthropic, Autonomous coding demo",
        )
    )

    if features is None:
        status, evidence = "fail", "no features to check"
    else:
        entries = [f for f in features if isinstance(f, dict)]
        with_passes = [f for f in entries if isinstance(f.get("passes"), bool)]
        with_evidence = [f for f in with_passes if "evidence" in f and "testedAt" in f]
        passing = sum(1 for f in with_passes if f["passes"])
        if len(with_passes) < len(features):
            status = "fail"
            evidence = f"{len(features) - len(with_passes)} features lack a boolean passes field"
        elif len(with_evidence) < len(features):
            status = "partial"
            evidence = (
                f"passes on every feature ({passing} true); evidence and testedAt missing"
                " (shipharness additions, course design)"
            )
        else:
            status = "pass"
            evidence = f"passes, evidence, testedAt on every feature ({passing} passing)"
    checks.append(
        Check(
            "C2",
            area,
            "Each feature has a boolean passes field",
            status,
            evidence,
            "assets/templates/feature_list.json",
            "Anthropic, Effective harnesses",
        )
    )

    schema_text = repo.read("feature_list.schema.json")
    if schema_text is None:
        status, evidence = "partial", "no feature_list.schema.json (a course addition)"
    else:
        try:
            json.loads(schema_text)
            status, evidence = "pass", "feature_list.schema.json found and parses"
        except json.JSONDecodeError as exc:
            status, evidence = "fail", f"feature_list.schema.json is not valid JSON: {exc.msg}"
    checks.append(
        Check(
            "C3",
            area,
            "The feature list has a schema",
            status,
            evidence,
            "assets/templates/feature_list.schema.json",
            "Anthropic, Prompting best practices (structured formats for state)",
        )
    )

    pyproject = repo.read("pyproject.toml") or ""
    setup_cfg = repo.read("setup.cfg") or ""
    layering = [
        name
        for name, found in (
            (".importlinter", repo.is_file(".importlinter")),
            ("pyproject [tool.importlinter]", "[tool.importlinter" in pyproject),
            ("setup.cfg [importlinter]", "[importlinter" in setup_cfg),
            (".dependency-cruiser.js", repo.is_file(".dependency-cruiser.js")),
            (".dependency-cruiser.cjs", repo.is_file(".dependency-cruiser.cjs")),
        )
        if found
    ]
    checks.append(
        Check(
            "C4",
            area,
            "Layering is enforced by code",
            "pass" if layering else "fail",
            ("found " + ", ".join(layering)) if layering else "no import-linter or layering config",
            "add an import-linter contract (house-rules skill)",
            "OpenAI, Harness engineering",
        )
    )

    containers = [
        name
        for name in (".devcontainer/devcontainer.json", "Dockerfile", "compose.yaml")
        + ("docker-compose.yml", "sandbox/Dockerfile")
        if repo.is_file(name)
    ]
    checks.append(
        Check(
            "C5",
            area,
            "A container is defined for the agent to run in",
            "pass" if containers else "fail",
            (
                "found " + ", ".join(containers) + " (cannot tell from files whether agents use it)"
                if containers
                else "no Dockerfile or devcontainer"
            ),
            "run agents in a container with no network",
            "Anthropic, C compiler; Anthropic, Autonomous coding demo",
        )
    )
    return checks


def verification(repo: Repo) -> list[Check]:
    area = "Verification"
    tests = [f for f in repo.files() if TEST_FILE.search(f.rsplit("/", 1)[-1])]
    checks = [
        Check(
            "V1",
            area,
            "Tests exist",
            "pass" if tests else "fail",
            f"{len(tests)} test files" if tests else "no test files found",
            "write tests; generate more with the assured-tests skill",
            "Anthropic, C compiler",
        )
    ]
    ci = [
        f
        for f in repo.files()
        if (f.startswith(".github/workflows/") and f.endswith((".yml", ".yaml")))
        or f in (".gitlab-ci.yml", ".circleci/config.yml", "azure-pipelines.yml", "Jenkinsfile")
    ]
    checks.append(
        Check(
            "V2",
            area,
            "CI runs the checks on every change",
            "pass" if ci else "fail",
            ("found " + ", ".join(ci[:3])) if ci else "no CI configuration",
            "add a CI job that runs tests and lint",
            "Anthropic, C compiler",
        )
    )
    pyproject = repo.read("pyproject.toml") or ""
    root_files = [f for f in repo.files() if "/" not in f]
    linters = [
        name
        for name, found in (
            ("ruff (pyproject)", "[tool.ruff" in pyproject),
            ("ruff.toml", repo.is_file("ruff.toml") or repo.is_file(".ruff.toml")),
            (".flake8", repo.is_file(".flake8")),
            ("eslint", any(f.startswith((".eslintrc", "eslint.config")) for f in root_files)),
            (".golangci.yml", repo.is_file(".golangci.yml")),
        )
        if found
    ]
    checks.append(
        Check(
            "V3",
            area,
            "A linter is configured",
            "pass" if linters else "fail",
            ("found " + ", ".join(linters)) if linters else "no linter configuration",
            "configure a linter; write custom rules with the house-rules skill",
            "OpenAI, Harness engineering",
        )
    )
    clean_doc = next(
        (
            n
            for n in ("docs/clean-state-checklist.md", "clean-state-checklist.md")
            if repo.is_file(n)
        ),
        None,
    )
    mentions = "clean state" in _agent_docs(repo)
    checks.append(
        Check(
            "V4",
            area,
            "Clean state is defined",
            _status(bool(clean_doc), mentions),
            f"{clean_doc} found"
            if clean_doc
            else (
                "AGENTS.md mentions clean state but no checklist (keyword check)"
                if mentions
                else "no clean-state checklist"
            ),
            "assets/templates/clean-state-checklist.md",
            "Anthropic, Effective harnesses",
        )
    )
    coverage = [
        name
        for name, found in (
            ("pyproject [tool.coverage]", "[tool.coverage" in pyproject),
            (".coveragerc", repo.is_file(".coveragerc")),
            ("pytest-cov", "pytest-cov" in pyproject or "--cov" in pyproject),
        )
        if found
    ]
    checks.append(
        Check(
            "V5",
            area,
            "Line coverage can be measured",
            _status(bool(coverage), True),
            ("found " + ", ".join(coverage))
            if coverage
            else "no coverage configuration (needed to judge generated tests)",
            "configure coverage.py; see the assured-tests skill",
            "Meta, TestGen-LLM",
        )
    )
    return checks


def session_lifecycle(repo: Repo) -> list[Check]:
    area = "Session lifecycle"
    docs = _agent_docs(repo)
    routine = [k for k in ("progress", "git log") if k in docs]
    checks = [
        Check(
            "L1",
            area,
            "Getting up to speed: read progress and git log first",
            _status(len(routine) == 2, len(routine) == 1),
            (f"AGENTS.md mentions {', '.join(routine)}" if routine else "not described")
            + " (keyword check)",
            "the Getting up to speed section of assets/templates/AGENTS.md",
            "Anthropic, Effective harnesses",
        )
    ]
    has_handoff = repo.is_file("session-handoff.md")
    checks.append(
        Check(
            "L2",
            area,
            "A structured handoff file for the next session",
            "pass" if has_handoff else "fail",
            "session-handoff.md found" if has_handoff else "no session-handoff.md",
            "assets/templates/session-handoff.md",
            "Anthropic, Harness design",
        )
    )
    one_feature = bool(re.search(r"one feature", docs))
    checks.append(
        Check(
            "L3",
            area,
            "One feature per session",
            "pass" if one_feature else "fail",
            ("AGENTS.md says one feature" if one_feature else "not stated") + " (keyword check)",
            "state it in AGENTS.md",
            "Anthropic, Effective harnesses; Anthropic, Harness design",
        )
    )
    runs_init = "init.sh" in docs
    checks.append(
        Check(
            "L4",
            area,
            "Sessions start by running init.sh",
            "pass" if runs_init else "fail",
            ("AGENTS.md mentions init.sh" if runs_init else "not stated") + " (keyword check)",
            "the Getting up to speed section of assets/templates/AGENTS.md",
            "Anthropic, Effective harnesses",
        )
    )
    end_routine = bool(re.search(r"end of (the )?session|end the session|session end", docs))
    commits = "commit" in docs
    checks.append(
        Check(
            "L5",
            area,
            "Sessions end with a commit and a progress update",
            _status(end_routine and commits, commits),
            (
                "end-of-session routine found"
                if end_routine and commits
                else (
                    "commits mentioned, no end-of-session routine" if commits else "not described"
                )
            )
            + " (keyword check)",
            "the End of session section of assets/templates/AGENTS.md",
            "Anthropic, Effective harnesses",
        )
    )
    return checks


def assess(root: Path) -> list[Check]:
    repo = Repo(Path(root))
    return (
        instructions(repo)
        + state(repo)
        + scope(repo)
        + verification(repo)
        + session_lifecycle(repo)
    )


# --- output --------------------------------------------------------------------------------

CSS = """
:root { --bg: #ffffff; --fg: #1f2328; --muted: #59636e; --line: #d1d9e0;
  --pass: #1a7f37; --partial: #9a6700; --fail: #cf222e; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #0d1117; --fg: #e6edf3; --muted: #9198a1; --line: #3d444d;
    --pass: #3fb950; --partial: #d29922; --fail: #f85149; } }
body { background: var(--bg); color: var(--fg); margin: 0 auto; max-width: 1100px;
  padding: 24px 16px; font: 15px/1.5 system-ui, sans-serif; }
h1 { font-size: 24px; margin: 0 0 4px; } h2 { font-size: 19px; margin: 32px 0 8px; }
p.meta { color: var(--muted); margin: 0 0 16px; }
table { border-collapse: collapse; width: 100%; }
th, td { border-bottom: 1px solid var(--line); padding: 6px 8px; text-align: left;
  vertical-align: top; }
th { color: var(--muted); font-weight: 600; }
.status { font-weight: 700; white-space: nowrap; }
.pass { color: var(--pass); } .partial { color: var(--partial); } .fail { color: var(--fail); }
code { font-size: 13px; }
.wrap { overflow-x: auto; }
"""
SYMBOL = {"pass": "+ pass", "partial": "~ partial", "fail": "x fail"}


def summary(checks: list[Check]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for area in AREAS:
        rows = [c for c in checks if c.area == area]
        counts[area] = {s: sum(1 for c in rows if c.status == s) for s in SYMBOL}
    return counts


def render_html(root: Path, checks: list[Check]) -> str:
    esc = html.escape
    counts = summary(checks)
    out = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Harness assessment</title>",
        f"<style>{CSS}</style></head><body>",
        "<h1>Harness assessment</h1>",
        f'<p class="meta">Repository: <code>{esc(Path(root).resolve().name)}</code>. '
        "Read-only, deterministic file checks; keyword checks are heuristics. Sources are short "
        "names; the harness-setup skill's README lists each one in full.</p>",
        '<div class="wrap"><table><tr><th>Area</th><th>Pass</th><th>Partial</th><th>Fail</th></tr>',
    ]
    for area in AREAS:
        c = counts[area]
        out.append(
            f"<tr><td>{esc(area)}</td><td>{c['pass']}</td><td>{c['partial']}</td>"
            f"<td>{c['fail']}</td></tr>"
        )
    out.append("</table></div>")
    for area in AREAS:
        out.append(f"<h2>{esc(area)}</h2>")
        out.append(
            '<div class="wrap"><table><tr><th>Check</th><th>Status</th>'
            "<th>Evidence</th><th>Fix</th><th>Source</th></tr>"
        )
        for check in (c for c in checks if c.area == area):
            out.append(
                f"<tr><td>{esc(check.title)}</td>"
                f'<td class="status {esc(check.status)}">{esc(SYMBOL[check.status])}</td>'
                f"<td>{esc(check.evidence)}</td><td>{esc(check.fix)}</td>"
                f"<td>{esc(check.source)}</td></tr>"
            )
        out.append("</table></div>")
    out.append("</body></html>")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo", type=Path, help="repository to assess")
    parser.add_argument("--out", type=Path, default=Path("harness-assessment.html"))
    parser.add_argument("--json", action="store_true", help="also print the checks as JSON")
    args = parser.parse_args(argv)
    if not args.repo.is_dir():
        print(f"ERROR not a directory: {args.repo}", file=sys.stderr)
        return 2
    checks = assess(args.repo)
    args.out.write_text(render_html(args.repo, checks), encoding="utf-8", newline="\n")
    if args.json:
        print(json.dumps([asdict(c) for c in checks], indent=2))
        return 0
    for area, c in summary(checks).items():
        print(f"{area:<18} pass {c['pass']}  partial {c['partial']}  fail {c['fail']}")
    for check in checks:
        if check.status != "pass":
            print(f"{check.status.upper():<8} {check.area}: {check.title}: {check.evidence}")
    print(f"report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
