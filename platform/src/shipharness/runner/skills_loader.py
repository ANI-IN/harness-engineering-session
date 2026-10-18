"""Agent Skills loader with progressive disclosure (Agent Skills spec)."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)


class SkillMeta(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    path: str  # folder, relative to the workspace when a prefix is known


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Top-level scalar fields of a SKILL.md frontmatter block (enough for name/description)."""
    match = _FRONTMATTER.match(text)
    if not match:
        return None
    fields: dict[str, str] = {}
    lines = match.group(1).splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        key_match = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        index += 1
        if not key_match:
            continue
        key, value = key_match.group(1), key_match.group(2).strip()
        if value in (">", "|", ">-", "|-"):
            block: list[str] = []
            while index < len(lines) and (lines[index].startswith((" ", "\t")) or not lines[index]):
                block.append(lines[index].strip())
                index += 1
            joiner = " " if value.startswith(">") else "\n"
            value = joiner.join(part for part in block if part)
        elif len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        fields[key] = value
    return fields


# [walkthrough:S1:progressive] start
class SkillsLoader:
    """Tier 1 (name + description) goes into the context prefix for every skill.

    Tier 2 (the full SKILL.md) and tier 3 (referenced files) are never pre-loaded: the agent reads
    them with read_file when a task matches, and `skill_for_path` tells the harness which tier a
    read touched, so the console can show which skills the agent actually opened.
    """

    def __init__(self, root: Path, workspace_prefix: str = ".agents/skills") -> None:
        self.root = Path(root)
        self.prefix = workspace_prefix.strip("/")

    def catalogue(self) -> list[SkillMeta]:
        if not self.root.is_dir():
            return []
        skills: list[SkillMeta] = []
        for skill_md in sorted(self.root.glob("*/SKILL.md")):
            fields = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
            if not fields or not fields.get("name") or not fields.get("description"):
                continue
            folder = skill_md.parent.name
            skills.append(
                SkillMeta(
                    name=fields["name"],
                    description=fields["description"],
                    path=f"{self.prefix}/{folder}",
                )
            )
        return sorted(skills, key=lambda s: s.name)

    def catalogue_block(self) -> str:
        skills = self.catalogue()
        if not skills:
            return ""
        rows = [f"- {s.name}: {s.description} (read {s.path}/SKILL.md to use it)" for s in skills]
        return (
            "Available skills (load a skill's SKILL.md only when the task needs it):\n"
            + "\n".join(rows)
        )

    # [walkthrough:S1:progressive] end

    def skill_for_path(self, rel: str) -> tuple[str, int] | None:
        parts = PurePosixPath(rel.replace("\\", "/")).parts
        prefix = PurePosixPath(self.prefix).parts
        if len(parts) <= len(prefix) + 1 or parts[: len(prefix)] != prefix:
            return None
        skill, rest = parts[len(prefix)], parts[len(prefix) + 1 :]
        return (skill, 2) if rest == ("SKILL.md",) else (skill, 3)
