"""Part A2 (reference solution): the per-phase diff-scope policy.

Rules per path, first match wins (README "Detailed requirements, Part A"):
1. path_escape: absolute, a drive letter, or a ".." segment (every path named, copy sources too)
2. harness_only: feature_list.json, feature_list.schema.json (changed paths only)
3. state files are allowed in every phase when the state layer is on
4. a phase with no allow list allows the path (as PathRules with allowed=None in guard.py)
5. a path matching one of the phase's globs is allowed
6. otherwise test_phase_source_edit in the test phase, outside_allowed_paths in any other
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

from a3scope.diffparse import DiffParseError, changed_paths, parse_diff

RefusalCode = Literal[
    "path_escape",
    "harness_only",
    "test_phase_source_edit",
    "outside_allowed_paths",
    "unparseable",
]

HARNESS_ONLY: tuple[str, ...] = ("feature_list.json", "feature_list.schema.json")
STATE_FILES: tuple[str, ...] = ("progress.md", "session-handoff.md", "docs/exec-plans/**")


@dataclass(frozen=True)
class PhasePolicy:
    allowed_paths: dict[str, list[str]]
    state_layer: bool = True


@dataclass(frozen=True)
class Refusal:
    path: str
    code: RefusalCode
    message: str


@dataclass(frozen=True)
class ScopeVerdict:
    phase: str
    refusals: tuple[Refusal, ...] = field(default=())

    @property
    def accepted(self) -> bool:
        return not self.refusals

    @property
    def refused_paths(self) -> list[str]:
        return [r.path for r in self.refusals]


def normalise(path: str) -> str:
    while path.startswith("./"):
        path = path[2:]
    return path


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
    return re.compile("".join(out) + r"\Z", re.DOTALL)


def glob_matches(path: str, pattern: str) -> bool:
    return _compile(normalise(pattern)).match(normalise(path)) is not None


def _escapes(path: str) -> bool:
    text = path.replace("\\", "/")
    return (
        not text
        or text.startswith("/")
        or re.match(r"^[A-Za-z]:", text) is not None
        or ".." in text.split("/")
    )


def _refusal(policy: PhasePolicy, phase: str, path: str) -> Refusal | None:
    rel = normalise(path)
    if rel in HARNESS_ONLY:
        return Refusal(rel, "harness_only", f"{rel} is written only by the harness")
    if policy.state_layer and any(glob_matches(rel, p) for p in STATE_FILES):
        return None
    allowed = policy.allowed_paths.get(phase)
    if allowed is None or any(glob_matches(rel, p) for p in allowed):
        return None
    listed = ", ".join(allowed) or "(none)"
    if phase == "test":
        return Refusal(
            rel,
            "test_phase_source_edit",
            f"{rel} is outside the allowed paths for the test phase ({listed}); "
            "the test phase changes tests only",
        )
    return Refusal(
        rel,
        "outside_allowed_paths",
        f"{rel} is outside the allowed paths for the {phase} phase ({listed})",
    )


def check_diff(policy: PhasePolicy, phase: str, diff: str | bytes) -> ScopeVerdict:
    try:
        changes = parse_diff(diff)
    except DiffParseError as exc:
        message = f"the patch could not be parsed ({exc}); nothing was applied"
        return ScopeVerdict(phase, (Refusal("", "unparseable", message),))
    changed = set(changed_paths(changes))
    refusals: list[Refusal] = []
    seen: set[str] = set()
    for change in changes:
        for path in (change.old_path, change.new_path):
            if path is None or path in seen:
                continue
            seen.add(path)
            if _escapes(path):
                message = f"{path} leaves the workspace (absolute path or '..' segment)"
                refusals.append(Refusal(path, "path_escape", message))
            elif path in changed:
                refusal = _refusal(policy, phase, path)
                if refusal is not None:
                    refusals.append(refusal)
    return ScopeVerdict(phase, tuple(refusals))
