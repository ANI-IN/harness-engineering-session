"""Part A2: the per-phase diff-scope policy.

The interface follows src/shipharness/harness/scope/guard.py (PathRules, check_paths), applied to
a whole diff instead of one path list. README "Detailed requirements, Part A" lists the rules
and their order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

RefusalCode = Literal[
    "path_escape",  # absolute path or a ".." segment: the path leaves the workspace
    "harness_only",  # feature_list.json or feature_list.schema.json
    "test_phase_source_edit",  # test phase: a path outside the test phase's allowed paths
    "outside_allowed_paths",  # any other phase: a path outside the phase's allowed paths
    "unparseable",  # the diff could not be parsed (path is "")
]

HARNESS_ONLY: tuple[str, ...] = ("feature_list.json", "feature_list.schema.json")
# Files the state layer asks the agent to keep current (progress log, handoff, exec plans):
# allowed in every phase when the state layer is on.
STATE_FILES: tuple[str, ...] = ("progress.md", "session-handoff.md", "docs/exec-plans/**")


@dataclass(frozen=True)
class PhasePolicy:
    """allowed_paths: phase -> globs, as in a dataset example's outputs.allowed_paths."""

    allowed_paths: dict[str, list[str]]
    state_layer: bool = True


@dataclass(frozen=True)
class Refusal:
    path: str
    code: RefusalCode
    message: str  # shown to the agent; names the path


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
    """Remove leading "./" segments."""
    while path.startswith("./"):
        path = path[2:]
    return path


def glob_matches(path: str, pattern: str) -> bool:
    """`*` and `?` stay inside one path segment; `**` spans any number of segments, and `**/`
    also matches zero directories (`docs/**/*.md` matches `docs/x.md`). The whole path must match.
    """
    # TODO(A3 Part A2): implement the glob semantics above (guard.py `_compile` is the model).
    raise NotImplementedError("TODO(A3 Part A2): glob_matches")


def check_diff(policy: PhasePolicy, phase: str, diff: str | bytes) -> ScopeVerdict:
    """Refuse every path the diff may not touch in `phase`; accept the diff if none.

    One Refusal per path, in diff order. A diff that cannot be parsed is refused with one
    Refusal(path="", code="unparseable").
    """
    # TODO(A3 Part A2): parse with a3scope.diffparse, then apply the rules in README order:
    # path_escape (every path named, copy sources too), harness_only, state files, a phase
    # without an allow list, the phase's globs, then test_phase_source_edit or
    # outside_allowed_paths.
    raise NotImplementedError("TODO(A3 Part A2): check_diff")
