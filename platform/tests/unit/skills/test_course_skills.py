"""The course skills in skills/: valid for both validators, sourced, complete per the contract."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from shipharness.layout import find_repo_root
from shipharness.skills_cli.validate import parse_skill_frontmatter, validate_skill

REPO = find_repo_root(Path(__file__))
SKILLS = REPO / "use-in-your-repo" / "skills"
NAMES = ["assured-tests", "harness-setup", "house-rules", "skill-template"]
SOURCE_ID = re.compile(r"\b(?:A[1-7]|B(?:1[0-4]|[1-9]))\b")
TEMPLATES = SKILLS / "harness-setup" / "assets" / "templates"


def headings(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("#")]


def test_exactly_the_four_course_skills() -> None:
    assert sorted(p.name for p in SKILLS.iterdir() if p.is_dir()) == NAMES


@pytest.mark.parametrize("name", NAMES)
def test_passes_shipharness_validate_without_warnings(name: str) -> None:
    report = validate_skill(SKILLS / name)
    assert report.errors == [] and report.warnings == [], (report.errors, report.warnings)
    assert report.lines < 500


@pytest.mark.parametrize("name", NAMES)
def test_passes_skills_ref_validate(name: str) -> None:
    validator = pytest.importorskip("skills_ref.validator")
    assert validator.validate(SKILLS / name) == []


@pytest.mark.parametrize("name", NAMES)
def test_scripts_are_python_only(name: str) -> None:
    scripts = SKILLS / name / "scripts"
    assert scripts.is_dir()
    for path in scripts.iterdir():
        if path.name == "__pycache__":  # bytecode from other test runs; gitignored
            continue
        assert path.suffix == ".py" or path.name == ".gitkeep", path


@pytest.mark.parametrize("name", ["assured-tests", "harness-setup", "house-rules"])
def test_skill_and_references_cite_sources_by_name(name: str) -> None:
    # The skills are copied into learners' repositories: sources by linked title or "Source N",
    # listed in full under "## Sources" as "- Source N: title, <link>, ..."; never the course's
    # source ids.
    folder = SKILLS / name
    for page in [folder / "SKILL.md", *sorted((folder / "references").glob("*.md"))]:
        text = page.read_text(encoding="utf-8")
        assert re.search(r"^## Sources\n\n- Source 1: [^\n]+\n?[^\n]*<https://", text, re.M), page
        assert not SOURCE_ID.search(text), page


def test_descriptions_say_what_and_when() -> None:
    for name in NAMES:
        fields, _ = parse_skill_frontmatter((SKILLS / name / "SKILL.md").read_text("utf-8"))
        description = str(fields["description"])
        assert "Use when" in description or "Use it when" in description, name


def test_prose_lint_is_clean() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO / "platform" / "scripts" / "lint_prose.py"), str(SKILLS)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout


# --- harness-setup ------------------------------------------------------------------------


def test_harness_setup_has_a_checklist_per_area_and_the_layout_and_failure_references() -> None:
    refs = SKILLS / "harness-setup" / "references"
    for stem in (
        "instructions",
        "state",
        "scope",
        "verification",
        "session-lifecycle",
        "docs-layout",
        "failure-modes",
    ):
        assert (refs / f"{stem}.md").is_file(), stem


def test_harness_setup_templates_exist() -> None:
    for name in (
        "AGENTS.md",
        "ARCHITECTURE.md",
        "SECURITY.md",
        "feature_list.json",
        "feature_list.schema.json",
        "progress.md",
        "session-handoff.md",
        "exec-plan.md",
        "clean-state-checklist.md",
        "init.sh",
    ):
        assert (TEMPLATES / name).is_file(), name


def test_agents_md_template_is_a_short_map() -> None:
    lines = (TEMPLATES / "AGENTS.md").read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 100  # A1: "roughly 100 lines"
    text = "\n".join(lines)
    for target in ("ARCHITECTURE.md", "docs/SECURITY.md", "progress.md", "feature_list.json"):
        assert target in text


def test_feature_list_template_matches_its_schema_and_contract() -> None:
    data = json.loads((TEMPLATES / "feature_list.json").read_text(encoding="utf-8"))
    schema = json.loads((TEMPLATES / "feature_list.schema.json").read_text(encoding="utf-8"))
    assert data["$schema"] == "./feature_list.schema.json"
    item_schema = schema["properties"]["features"]["items"]
    keys = ["id", "category", "description", "steps", "passes", "evidence", "testedAt"]
    assert sorted(item_schema["required"]) == sorted(keys)
    assert item_schema["additionalProperties"] is False
    for feature in data["features"]:
        assert sorted(feature) == sorted(keys)
        assert feature["passes"] is False
        assert feature["evidence"] is None and feature["testedAt"] is None
    evidence = item_schema["properties"]["evidence"]
    evidence_object = next(s for s in evidence["oneOf"] if s.get("type") == "object")
    assert sorted(evidence_object["required"]) == [
        "checks",
        "commit",
        "existing",
        "gate_id",
        "visible",
    ]


def test_progress_template_sections_in_contract_order() -> None:
    assert headings(TEMPLATES / "progress.md") == [
        "# Progress",
        "## Current feature",
        "## Done",
        "## In progress",
        "## Next",
        "## Session log",
    ]


def test_handoff_template_sections() -> None:
    found = headings(TEMPLATES / "session-handoff.md")
    assert found[1:] == ["## Machine summary", "## Notes from the agent"]


def test_exec_plan_template_sections() -> None:
    found = [h for h in headings(TEMPLATES / "exec-plan.md") if h.startswith("## ")]
    assert found == [
        "## Purpose",
        "## Progress",
        "## Surprises & Discoveries",
        "## Decision Log",
        "## Outcomes & Retrospective",
        "## Validation",
    ]


def test_init_sh_template_is_a_strict_bash_script() -> None:
    text = (TEMPLATES / "init.sh").read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash\n")
    assert "set -euo pipefail" in text
    assert "\r\n" not in text


# --- skill-template ------------------------------------------------------------------------


def test_skill_template_has_placeholders_and_install_guide() -> None:
    folder = SKILLS / "skill-template"
    for sub in ("scripts", "references", "assets"):
        assert (folder / sub / ".gitkeep").is_file(), sub
    readme = (folder / "README.md").read_text(encoding="utf-8")
    for needle in (
        ".claude/skills/",
        "~/.claude/skills/",
        ".agents/skills/",
        "$HOME/.agents/skills",
        "Cursor",
        "shipharness skills validate",
        "agentskills validate",
    ):
        assert needle in readme, needle


def test_skill_template_anchor_extracts() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(REPO / "platform" / "scripts" / "anchors.py"),
            "extract",
            "Final:skill_template",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "description:" in result.stdout
