"""Allowed paths per phase: which files the agent may change in this phase.

Patterns are globs relative to the workspace root: `*` and `?` stay inside one path segment, `**`
spans any number of segments (`tests/visible/**`, `docs/**/x.md`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from shipharness.runner.patch_format import header_path
from shipharness.runner.tools import patch_paths

FEATURE_LIST_REASON = "feature_list.json is written only by the harness"
HARNESS_ONLY: dict[str, str] = {
    "feature_list.json": FEATURE_LIST_REASON,
    "feature_list.schema.json": "feature_list.schema.json is written only by the harness",
}
# Files the state layer asks the agent to keep current at wrap-up.
STATE_FILES: tuple[str, ...] = ("progress.md", "session-handoff.md", "docs/exec-plans/**")


@lru_cache(maxsize=256)
def _compile(pattern: str) -> re.Pattern[str]:
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def normalise(path: str) -> str:
    text = path.strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def glob_matches(path: str, pattern: str) -> bool:
    return _compile(normalise(pattern)).match(normalise(path)) is not None


# [walkthrough:S3:allowed_paths] start
@dataclass(frozen=True)
class PathRules:
    """What the agent may change in one phase. `allowed=None`: the task gave no list."""

    phase: str
    allowed: list[str] | None
    state_files: bool  # the state layer is on, so progress.md and friends are the agent's

    def reason(self, path: str) -> str | None:
        """None if the agent may change `path`; otherwise the reason it sees."""
        rel = normalise(path)
        if rel in HARNESS_ONLY:
            return HARNESS_ONLY[rel]
        if self.state_files and any(glob_matches(rel, p) for p in STATE_FILES):
            return None
        if self.allowed is None or any(glob_matches(rel, p) for p in self.allowed):
            return None
        listed = ", ".join(self.allowed) or "(none)"
        return f"{rel} is outside the allowed paths for the {self.phase} phase ({listed})"


def check_paths(rules: PathRules, paths: list[str]) -> dict[str, list[str]]:
    """Group the refused paths by reason (one blocked decision per reason)."""
    refused: dict[str, list[str]] = {}
    for path in paths:
        reason = rules.reason(path)
        if reason is not None:
            key = reason if normalise(path) in HARNESS_ONLY else _phase_reason(rules)
            refused.setdefault(key, []).append(normalise(path))
    return refused


def _phase_reason(rules: PathRules) -> str:
    listed = ", ".join(rules.allowed or []) or "(none)"
    return f"outside the allowed paths for the {rules.phase} phase ({listed})"


# [walkthrough:S3:allowed_paths] end


def patch_targets(patch: str) -> list[str]:
    """Every path a patch can touch: ---/+++ headers, `diff --git`, renames, copies, and the
    anchored format's `*** Update File:` / `*** Add File:` / `*** Delete File:` / `*** Move to:`."""
    found: list[str] = []

    def add(name: str) -> None:
        name = normalise(name.strip().strip('"'))
        if name and name != "/dev/null" and name not in found:
            found.append(name)

    header_paths, prefixed = patch_paths(patch)
    header_set = set(header_paths)
    for line in patch.splitlines():
        anchored = header_path(line)
        if anchored is not None:
            add(anchored)
        elif line.startswith("diff --git "):
            match = re.match(r'^diff --git "?a/(.+?)"? "?b/(.+?)"?$', line)
            if match:
                add(match.group(1))
                add(match.group(2))
        elif line.startswith(("rename from ", "rename to ", "copy from ", "copy to ")):
            add(line.split(" ", 2)[2])
        elif line.startswith(("--- ", "+++ ")):
            name = line[4:].split("\t", 1)[0].strip()
            if prefixed and name.startswith(("a/", "b/")):
                name = name[2:]
            if name in header_set:
                add(name)
    return found
