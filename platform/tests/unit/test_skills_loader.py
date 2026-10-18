from __future__ import annotations

from pathlib import Path

import pytest

from shipharness.runner.skills_loader import SkillsLoader


def write_skill(root: Path, name: str, description: str, body: str = "Body text.") -> None:
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n", encoding="utf-8"
    )


@pytest.fixture
def skills_root(tmp_path: Path) -> Path:
    root = tmp_path / ".agents" / "skills"
    write_skill(root, "house-rules", "Write a house rule and its check.", "Long body " * 200)
    write_skill(root, "assured-tests", "Generate tests that pass the filters.")
    return root


def test_catalogue_has_name_and_description_only_sorted(skills_root: Path) -> None:
    catalogue = SkillsLoader(skills_root).catalogue()
    assert [s.name for s in catalogue] == ["assured-tests", "house-rules"]
    assert catalogue[1].description == "Write a house rule and its check."


def test_catalogue_block_excludes_bodies(skills_root: Path) -> None:
    block = SkillsLoader(skills_root).catalogue_block()
    assert "house-rules: Write a house rule and its check." in block
    assert "Long body" not in block


def test_catalogue_block_is_stable(skills_root: Path) -> None:
    assert (
        SkillsLoader(skills_root).catalogue_block() == SkillsLoader(skills_root).catalogue_block()
    )


def test_skill_for_path_reports_tier(skills_root: Path) -> None:
    loader = SkillsLoader(skills_root, workspace_prefix=".agents/skills")
    assert loader.skill_for_path(".agents/skills/house-rules/SKILL.md") == ("house-rules", 2)
    assert loader.skill_for_path(".agents/skills/house-rules/references/a.md") == ("house-rules", 3)
    assert loader.skill_for_path("app/main.py") is None


def test_missing_root_gives_empty_catalogue(tmp_path: Path) -> None:
    assert SkillsLoader(tmp_path / "none").catalogue() == []


def test_skill_without_frontmatter_is_skipped(tmp_path: Path) -> None:
    folder = tmp_path / "broken"
    folder.mkdir()
    (folder / "SKILL.md").write_text("no frontmatter here\n", encoding="utf-8")
    assert SkillsLoader(tmp_path).catalogue() == []
