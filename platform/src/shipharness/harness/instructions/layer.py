"""Instructions layer (S1): what the agent knows.

- prepare_workspace: copies `platform/teamtrack/harness/instructions/` into the workspace. The tree
  mirrors the workspace layout: AGENTS.md and ARCHITECTURE.md at the root, docs/ as the system of
  record (A1, F-a-29, F-a-30), skills in `.agents/skills/` (B3). docs/HANDBOOK.md is never
  touched: both arms read it.
- context_prefix: one stable block from `router.build_prefix` (the map + skills tier 1).
- after_tool: records which harness docs and skills the agent opened with read_file, into
  `ctx.state["instructions.files_read"]`, and returns one `note` decision per first read (skills
  carry their tier). Reads through `run` (for example `cat`) are not seen.
"""

from __future__ import annotations

import posixpath
from pathlib import Path
from typing import Any

from shipharness.config.prices import REPO_ROOT
from shipharness.harness.base import BaseLayer, LayerContext, register_layer
from shipharness.harness.decisions import HarnessDecision
from shipharness.harness.instructions.router import SKILLS_DIR, build_prefix, strip_markers
from shipharness.layout import APP_DIR
from shipharness.runner.models import ToolCall, ToolResult
from shipharness.runner.paths import PathOutsideWorkspace, resolve_in_workspace
from shipharness.runner.skills_loader import SkillsLoader

DEFAULT_SOURCE = REPO_ROOT / APP_DIR / "harness" / "instructions"
FILES_READ_KEY = "instructions.files_read"
_SKIP_PARTS = {"__pycache__", ".DS_Store"}


def source_files(source: Path) -> list[str]:
    """Workspace-relative paths of every file in the instructions tree, sorted."""
    files = [
        path.relative_to(source).as_posix()
        for path in source.rglob("*")
        if path.is_file() and not _SKIP_PARTS & set(path.parts)
    ]
    return sorted(files)


def _normalise(raw: Any) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    rel = posixpath.normpath(raw.strip().replace("\\", "/"))
    while rel.startswith("./"):
        rel = rel[2:]
    return None if rel in (".", "") or rel.startswith("../") else rel


def _crosses_link(workspace: Path, rel: str) -> bool:
    """True if the destination or any existing parent inside the workspace is a link."""
    current = Path(workspace)
    for part in rel.split("/"):
        current = current / part
        if current.is_symlink():
            return True
        if not current.exists():
            return False
    return False


@register_layer
class InstructionsLayer(BaseLayer):
    name = "instructions"

    def __init__(self, *, source: Path | None = None, **_kwargs: Any) -> None:
        self.source = Path(source) if source is not None else DEFAULT_SOURCE
        self._prefix: str | None = None
        self._tracked: frozenset[str] | None = None
        self._skills = SkillsLoader(self.source / SKILLS_DIR, workspace_prefix=SKILLS_DIR)

    @property
    def tracked(self) -> frozenset[str]:
        if self._tracked is None:
            self._tracked = frozenset(source_files(self.source))
        return self._tracked

    # -- hooks -------------------------------------------------------------------------------------

    def prepare_workspace(self, ctx: LayerContext) -> list[HarnessDecision]:
        placed: list[str] = []
        skipped: list[str] = []
        for rel in source_files(self.source):
            try:
                if _crosses_link(ctx.workspace, rel):
                    raise PathOutsideWorkspace(rel)
                target = resolve_in_workspace(ctx.workspace, rel)
            except PathOutsideWorkspace:
                skipped.append(rel)
                continue
            text = (self.source / rel).read_text(encoding="utf-8")
            if rel.endswith(".md"):
                text = strip_markers(text)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode("utf-8"))
            placed.append(rel)
        ctx.state.setdefault(FILES_READ_KEY, [])
        message = f"placed {len(placed)} instruction files (AGENTS.md map, docs, skills)"
        if skipped:
            message += f"; skipped {len(skipped)} whose workspace path crosses a link"
        return [
            HarnessDecision(
                kind="note",
                layer=self.name,
                message=message,
                paths=placed,
                data={"skipped": skipped} if skipped else {},
            )
        ]

    def context_prefix(self, ctx: LayerContext) -> list[str]:
        if self._prefix is None:
            self._prefix = build_prefix(self.source)
        return [self._prefix]

    def after_tool(
        self, ctx: LayerContext, call: ToolCall, result: ToolResult
    ) -> list[HarnessDecision]:
        if call.name != "read_file" or not result.ok:
            return []
        rel = _normalise(call.arguments.get("path"))
        if rel is None or rel not in self.tracked:
            return []
        files_read: list[str] = ctx.state.setdefault(FILES_READ_KEY, [])
        if rel in files_read:
            return []
        files_read.append(rel)
        data: dict[str, Any] = {"file": rel, "kind": "doc"}
        message = f"agent read {rel}"
        hit = self._skills.skill_for_path(rel)
        if hit is not None:
            skill, tier = hit
            data = {"file": rel, "kind": "skill", "skill": skill, "tier": tier}
            message = f"agent read skill {skill} (tier {tier}): {rel}"
        return [
            HarnessDecision(kind="note", layer=self.name, message=message, paths=[rel], data=data)
        ]
