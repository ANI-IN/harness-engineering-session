"""The TeamTrack instructions tree: A1 layout, a map of roughly 100 lines, one valid skill."""

from __future__ import annotations

import configparser
import re
from pathlib import Path

import pytest
from skills_ref.validator import validate

from shipharness.harness.instructions.layer import DEFAULT_SOURCE, source_files
from shipharness.harness.instructions.router import build_prefix, strip_markers
from shipharness.runner.skills_loader import parse_frontmatter

TEAMTRACK = DEFAULT_SOURCE.parents[1]
SKILLS = DEFAULT_SOURCE / ".agents" / "skills"
SPEC_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
# A1's layout (F-a-30) as assigned to the instructions layer by the M4 contract (I-6).
REQUIRED = [
    "AGENTS.md",
    "ARCHITECTURE.md",
    "docs/SECURITY.md",
    "docs/RELIABILITY.md",
    "docs/QUALITY_SCORE.md",
    "docs/PLANS.md",
    "docs/design-docs/index.md",
    "docs/product-specs/index.md",
]
# Both arms have the handbook on disk; the map may name it.
SHARED = {"docs/HANDBOOK.md"}
# Paths owned by the state and scope layers: the map must not point to them.
OTHER_LAYERS = ("exec-plans", "progress.md", "session-handoff.md", "init.sh", "feature_list")
_PATH = re.compile(r"(?<![\w/.-])((?:\.agents|docs)/[\w./-]+|[A-Z_]+\.md)")


def agents_md() -> str:
    return strip_markers((DEFAULT_SOURCE / "AGENTS.md").read_text(encoding="utf-8"))


@pytest.mark.parametrize("rel", REQUIRED)
def test_layout_file_exists(rel: str) -> None:
    assert (DEFAULT_SOURCE / rel).is_file()


def test_product_specs_has_the_base_product_description() -> None:
    specs = [p for p in source_files(DEFAULT_SOURCE) if p.startswith("docs/product-specs/")]
    assert len(specs) >= 2


def test_references_are_llms_txt_files() -> None:
    refs = [p for p in source_files(DEFAULT_SOURCE) if p.startswith("docs/references/")]
    assert refs and all(p.endswith("-llms.txt") for p in refs)


def test_handbook_is_not_part_of_the_harness_tree() -> None:
    assert "docs/HANDBOOK.md" not in source_files(DEFAULT_SOURCE)


def test_agents_md_is_a_map_of_roughly_100_lines() -> None:
    assert 80 <= len(agents_md().splitlines()) <= 120


def test_agents_md_points_only_to_files_in_the_instructions_tree() -> None:
    files = set(source_files(DEFAULT_SOURCE))
    targets = {m.rstrip(".") for m in _PATH.findall(agents_md())}
    assert targets, "the map points nowhere"
    missing = sorted(
        t
        for t in targets
        if t not in files | SHARED and not any(f.startswith(t.rstrip("/") + "/") for f in files)
    )
    assert missing == []
    assert not [word for word in OTHER_LAYERS if word in agents_md()]


def test_agents_md_warns_about_the_legacy_handler() -> None:
    text = agents_md()
    assert "/v1/issues" in text and "copy" in text.lower()


def test_agents_md_anchor_is_present() -> None:
    raw = (DEFAULT_SOURCE / "AGENTS.md").read_text(encoding="utf-8")
    assert "[walkthrough:S1:agents_md] start" in raw
    assert "[walkthrough:S1:agents_md] end" in raw


def test_real_prefix_has_map_and_catalogue_but_no_skill_body() -> None:
    prefix = build_prefix(DEFAULT_SOURCE)
    assert agents_md().strip() in prefix
    assert "add-endpoint:" in prefix
    body = (SKILLS / "add-endpoint" / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[2]
    assert body.strip().splitlines()[0] not in prefix


# -- skills --------------------------------------------------------------------------------------


def skill_dirs() -> list[Path]:
    return sorted(p for p in SKILLS.iterdir() if p.is_dir()) if SKILLS.is_dir() else []


def test_exactly_one_teamtrack_skill() -> None:
    assert [p.name for p in skill_dirs()] == ["add-endpoint"]


@pytest.mark.parametrize("skill", skill_dirs(), ids=lambda p: p.name)
def test_skill_passes_skills_ref(skill: Path) -> None:
    assert validate(skill) == []


@pytest.mark.parametrize("skill", skill_dirs(), ids=lambda p: p.name)
def test_skill_uses_spec_fields_and_size_limits(skill: Path) -> None:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    fields = parse_frontmatter(text)
    assert fields is not None
    assert set(fields) <= SPEC_FIELDS
    assert fields["name"] == skill.name
    assert 1 <= len(fields["description"]) <= 1024
    assert len(text.splitlines()) < 500


@pytest.mark.parametrize("skill", skill_dirs(), ids=lambda p: p.name)
def test_skill_references_are_one_level_deep_and_exist(skill: Path) -> None:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    refs = re.findall(r"\]\(([^)#]+)\)", text)
    local = [r for r in refs if not r.startswith(("http://", "https://", "../"))]
    for ref in local:
        assert len(Path(ref).parts) <= 2, ref
        assert (skill / ref).is_file(), ref
    for nested in skill.rglob("*"):
        if nested.is_file():
            assert len(nested.relative_to(skill).parts) <= 2, nested


# -- import-linter contract (M3 review minor M11) ------------------------------------------------


def test_layers_contract_name_matches_its_layer_order() -> None:
    config = configparser.ConfigParser()
    config.read(TEAMTRACK / ".importlinter", encoding="utf-8")
    section = config["importlinter:contract:layers"]
    layers = [line.strip() for line in section["layers"].splitlines() if line.strip()]
    named = section["name"].split(":", 1)[1].split("->")
    assert [f"app.{part.strip()}" for part in named] == layers
