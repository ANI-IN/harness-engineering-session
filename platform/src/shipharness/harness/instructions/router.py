"""Context prefix for the instructions layer (S1): the AGENTS.md map plus the skills catalogue.

The brief names this module `router.py`; the course calls AGENTS.md a "map" or "table of contents"
(A1 F-a-27, F-a-28). The prefix is built from the course checkout, never from the
workspace, so an agent edit to its own copy of AGENTS.md cannot change the cached prompt prefix.
"""

from __future__ import annotations

import re
from pathlib import Path

from shipharness.runner.skills_loader import SkillsLoader

MAP_FILE = "AGENTS.md"
SKILLS_DIR = ".agents/skills"
_MARKER_LINE = re.compile(
    r"^\s*<!--\s*\[walkthrough:[A-Za-z0-9]+:[A-Za-z0-9_]+\]\s+(start|end)\s*-->\s*$"
)


def strip_markers(text: str) -> str:
    """Drop walkthrough anchor comment lines (they are for the class, not for the agent)."""
    kept = [line for line in text.splitlines(keepends=True) if not _MARKER_LINE.match(line)]
    return "".join(kept)


# [walkthrough:S1:prefix] start
def build_prefix(source: Path) -> str:
    """One stable text block: the map, then tier 1 of every skill (name + description).

    A1: "A short AGENTS.md (roughly 100 lines) is injected into context and serves primarily as a
    map, with pointers to deeper sources of truth elsewhere." The documents the map points to are
    not injected; the agent reads them with read_file when its task needs them. Skills follow the
    same progressive disclosure (B1): only the catalogue line is here, never a SKILL.md body.
    """
    source = Path(source)
    agents_md = strip_markers((source / MAP_FILE).read_text(encoding="utf-8")).strip()
    blocks = [
        "Repository map (AGENTS.md at the workspace root). It points to the documents to read "
        "before you change code; open them with read_file when your task needs them.",
        agents_md,
    ]
    catalogue = SkillsLoader(source / SKILLS_DIR, workspace_prefix=SKILLS_DIR).catalogue_block()
    if catalogue:
        blocks.append(catalogue)
    return "\n\n".join(blocks)


# [walkthrough:S1:prefix] end
