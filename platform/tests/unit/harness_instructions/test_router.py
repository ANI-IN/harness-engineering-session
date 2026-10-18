"""router.build_prefix: the AGENTS.md map plus the tier-1 skill catalogue, byte-stable."""

from __future__ import annotations

from pathlib import Path

from shipharness.harness.instructions.router import build_prefix, strip_markers

from .conftest import MAP_TEXT, SKILL_BODY


def test_prefix_holds_the_map_and_the_catalogue(source: Path) -> None:
    prefix = build_prefix(source)
    assert MAP_TEXT.strip() in prefix
    assert "add-endpoint: Add an endpoint the house way." in prefix
    assert ".agents/skills/add-endpoint/SKILL.md" in prefix


def test_prefix_excludes_skill_bodies_and_references(source: Path) -> None:
    prefix = build_prefix(source)
    assert SKILL_BODY not in prefix
    assert "test notes" not in prefix


def test_prefix_is_byte_stable(source: Path) -> None:
    assert build_prefix(source).encode() == build_prefix(source).encode()


def test_prefix_has_no_walkthrough_markers(source: Path) -> None:
    assert "walkthrough" not in build_prefix(source)


def test_prefix_without_skills_is_the_map_only(source: Path) -> None:
    for path in sorted((source / ".agents").rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    (source / ".agents").rmdir()
    prefix = build_prefix(source)
    assert MAP_TEXT.strip() in prefix
    assert "skills" not in prefix.lower()


def test_strip_markers_removes_only_marker_lines() -> None:
    marker = "<!-- [walkthrough:S1:agents_md] {} -->\n"
    text = marker.format("start") + "# Title\nbody\n" + marker.format("end")
    assert strip_markers(text) == "# Title\nbody\n"
    assert strip_markers("no markers\n") == "no markers\n"
