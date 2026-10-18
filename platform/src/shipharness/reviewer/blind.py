"""Blinding the reviewer: the reviewer gets the task and the
code and tests the arm shipped, nothing that tells it which arm wrote them."""

from __future__ import annotations

import re

from shipharness.ab.artifacts import strip_harness_artifacts

_INDEX = re.compile(r"^index [0-9a-f]+\.\.[0-9a-f]+(?: \d+)?$")
_WORKSPACE = re.compile(r"[^\s'\"`]*shipharness-ws[\\/][^\s'\"`]*?[\\/](?:bare|harness)[\\/]ws")
_IDS = re.compile(r"\b(?:ab|r)-\d{8}-\d{6}-[0-9a-f]{6}\b")


# [walkthrough:S4:blind] start
def blind(diff: str | bytes) -> str:
    """Return the diff with every arm-identifying trace removed, so two arms that shipped the
    same code produce the same text.

    1. Harness artifacts (AGENTS.md, progress.md, feature_list.json, .agents/, exec plans,
       handoff, init.sh, ...) are dropped file by file: they exist only in the harness arm.
    2. Commit metadata (mail headers before the first file, blob hashes on `index` lines)
       is removed.
    3. Host workspace paths (which contain the arm name) and run ids are normalised.
    The arm label itself is never an input: ReviewInput has no field for it.
    """
    text = diff.decode("utf-8", errors="replace") if isinstance(diff, bytes) else diff
    text = strip_harness_artifacts(text)
    lines = text.splitlines()
    first = next((i for i, line in enumerate(lines) if line.startswith("diff --git ")), None)
    if first is None:
        return ""
    kept = [line for line in lines[first:] if not _INDEX.match(line)]
    body = "\n".join(kept) + "\n"
    body = _WORKSPACE.sub("<workspace>", body)
    return _IDS.sub("<id>", body)


# [walkthrough:S4:blind] end
