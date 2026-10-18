"""diff_scope (S3 measures): out-of-scope files in the shipped diff, source edits in the test phase.

Inputs:
- the shipped diff: `params.changed_files` (paths) or `params.diff_path` (a unified diff file);
- allowed paths per phase: `ctx.phase_allowed_paths` ({"build": [...], "test": [...]}); a file is
  in scope if any phase allows it;
- `params.phase_files`: files changed during each phase ({"test": [...]}) for the test-phase rule;
- `params.test_globs`: what counts as a test file (default DEFAULT_TEST_GLOBS);
- `params.harness_artifacts`: files the harness layers create (default DEFAULT_HARNESS_ARTIFACTS).
  They are never product changes, so they count toward neither measure.

Patterns: `**` crosses directories, `*` and `?` stay within one; a pattern ending in `/` or
naming a directory also matches everything below it.
"""

from __future__ import annotations

import re
import time
from functools import lru_cache
from pathlib import Path

from shipharness.checks.base import CheckContext, CheckResult, Finding, make_result, register_check

DEFAULT_TEST_GLOBS = ("tests/**", "**/test_*.py", "**/*_test.py", "**/conftest.py")
DEFAULT_HARNESS_ARTIFACTS = (
    "AGENTS.md",
    "ARCHITECTURE.md",
    "docs/SECURITY.md",
    "docs/RELIABILITY.md",
    "docs/QUALITY_SCORE.md",
    "docs/PLANS.md",
    "docs/design-docs/**",
    "docs/product-specs/**",
    "docs/references/**",
    ".agents/skills/**",
    "init.sh",
    "progress.md",
    "session-handoff.md",
    "docs/exec-plans/**",
    "feature_list.json",
    "feature_list.schema.json",
)


@lru_cache(maxsize=512)
def _regex(pattern: str) -> re.Pattern[str]:
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"(?:/.*)?" if not pattern.endswith("/") else out + ".*")


def matches(path: str, pattern: str) -> bool:
    pattern = pattern[2:] if pattern.startswith("./") else pattern
    return _regex(pattern).fullmatch(path) is not None


def matches_any(path: str, patterns: list[str] | tuple[str, ...]) -> bool:
    return any(matches(path, p) for p in patterns)


def changed_paths(diff: str) -> list[str]:
    """Paths touched by a unified git diff (new name for renames, old name for deletions)."""
    paths: list[str] = []
    old: str | None = None
    for line in diff.splitlines():
        if line.startswith("--- "):
            old = line[4:].strip()
        elif line.startswith("+++ "):
            new = line[4:].strip()
            name = old if new == "/dev/null" else new
            if name and name != "/dev/null":
                name = name[2:] if name[:2] in ("a/", "b/") else name
                if name not in paths:
                    paths.append(name)
    return paths


def _finding(key: str, path: str, detail: str) -> Finding:
    return Finding(rule="scope", severity="violation", detail_key=f"{key}:{path}", detail=detail)


@register_check
class DiffScopeCheck:
    name = "diff_scope"
    rule = "scope"

    def run(self, build_dir: Path, ctx: CheckContext) -> CheckResult:
        started = time.monotonic()
        p = ctx.params
        files = list(p.get("changed_files") or [])
        if not files and p.get("diff_path"):
            files = changed_paths(Path(p["diff_path"]).read_text(encoding="utf-8"))
        harness = tuple(p.get("harness_artifacts") or DEFAULT_HARNESS_ARTIFACTS)
        tests = tuple(p.get("test_globs") or DEFAULT_TEST_GLOBS)
        allowed = [pattern for paths in ctx.phase_allowed_paths.values() for pattern in paths]
        product = [f for f in files if not matches_any(f, harness)]
        findings: list[Finding] = []
        if not allowed:
            findings.append(
                Finding(
                    rule="scope",
                    severity="error",
                    detail_key="no_allowed_paths",
                    detail="no allowed paths given (ctx.phase_allowed_paths); scope not judged",
                )
            )
        else:
            for f in product:
                if not matches_any(f, allowed):
                    findings.append(
                        _finding("out_of_scope", f, f"{f} is outside the allowed paths")
                    )
        for f in (p.get("phase_files") or {}).get("test", []):
            if not matches_any(f, harness) and not matches_any(f, tests):
                detail = f"{f} (source) changed during the test phase"
                findings.append(_finding("test_phase_source_edit", f, detail))
        ctx.progress(1, 1, "diff scope")
        return make_result(self.name, findings, total_probes=len(product), started=started)
