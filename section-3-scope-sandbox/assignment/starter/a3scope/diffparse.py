"""Part A1: parse a diff into file changes.

Input is what an agent can hand to `apply_patch` or what `git diff` prints: git diffs (with
`diff --git` headers, renames, copies, mode changes, binary files, quoted names) and plain
unified diffs (only `---`/`+++` headers, with or without the a/ and b/ prefixes, possibly with a
tab and a timestamp after the name). README "Detailed requirements, Part A" lists every rule.

Reference reading (do not import it): src/shipharness/ab/artifacts.py (`_sections`,
`_header_paths`, `_body_paths`) and src/shipharness/harness/scope/guard.py (`patch_targets`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Status = Literal["added", "deleted", "modified", "renamed", "copied"]


class DiffParseError(ValueError):
    """The diff has content but no file whose paths can be determined."""


@dataclass(frozen=True)
class FileChange:
    old_path: str | None  # None for an added file
    new_path: str | None  # None for a deleted file
    status: Status
    binary: bool = False


def parse_diff(diff: str | bytes) -> list[FileChange]:
    """One FileChange per file section, in diff order. An empty diff gives [].

    Paths have the a/ or b/ prefix removed (when the diff uses prefixes), C-style quoting undone
    (git writes "a/caf\\303\\251.md" for a non-ASCII name), a trailing tab and timestamp removed,
    and leading "./" removed. `/dev/null` means the file does not exist on that side.
    Raise DiffParseError for text that has content but no parseable file section.
    """
    # TODO(A3 Part A1): split the diff into file sections and read each section's paths,
    # status, and binary flag. Lines inside a hunk that start with "--- " or "+++ " are content,
    # not headers: count hunk lines with the @@ -a,b +c,d @@ numbers.
    raise NotImplementedError("TODO(A3 Part A1): parse_diff")


def changed_paths(changes: list[FileChange]) -> list[str]:
    """Paths whose content or existence the diff changes, in diff order, without duplicates.

    Added: new path. Deleted: old path. Modified: the path. Renamed: old and new path.
    Copied: the new path only (the copy source is read, not changed).
    """
    # TODO(A3 Part A1): implement from the docstring.
    raise NotImplementedError("TODO(A3 Part A1): changed_paths")
