"""Our errors agree with skills-ref 0.1.1 (dev dependency) on valid vs invalid, case by case."""

from __future__ import annotations

from pathlib import Path

import pytest

from shipharness.skills_cli.validate import validate_skill

skills_ref_validator = pytest.importorskip("skills_ref.validator")

CASES = {
    "valid-minimal": "---\nname: valid-minimal\ndescription: Does x. Use when y.\n---\nbody\n",
    "valid-all": (
        "---\nname: valid-all\ndescription: >\n  Folded\n  text.\nlicense: MIT\n"
        "compatibility: Python 3.12\nallowed-tools: Read Bash\nmetadata:\n  owner: course\n---\n"
    ),
    "valid-quoted": "---\nname: valid-quoted\ndescription: 'Use when: quoted'\n---\n",
    "valid-comment": "---\n# note\nname: valid-comment\ndescription: d\n---\n",
    "extra-field": "---\nname: extra-field\ndescription: d\ncontext: fork\n---\n",
    "no-name": "---\ndescription: d\n---\n",
    "no-description": "---\nname: no-description\n---\n",
    "mismatch": "---\nname: something-else\ndescription: d\n---\n",
    "Upper-Case": "---\nname: Upper-Case\ndescription: d\n---\n",
    "dou--ble": "---\nname: dou--ble\ndescription: d\n---\n",
    "under_score": "---\nname: under_score\ndescription: d\n---\n",
    "long-description": f"---\nname: long-description\ndescription: {'x' * 1025}\n---\n",
    "long-compat": f"---\nname: long-compat\ndescription: d\ncompatibility: {'x' * 501}\n---\n",
    "no-frontmatter": "# Title only\n",
    "unclosed": "---\nname: unclosed\ndescription: d\n",
    "colon-value": "---\nname: colon-value\ndescription: Use when: x\n---\n",
    "flow-style": "---\nname: flow-style\ndescription: d\nmetadata: {a: b}\n---\n",
    "duplicate": "---\nname: duplicate\nname: duplicate\ndescription: d\n---\n",
}


@pytest.mark.parametrize("folder", sorted(CASES))
def test_same_verdict_as_skills_ref(tmp_path: Path, folder: str) -> None:
    skill = tmp_path / folder
    skill.mkdir()
    (skill / "SKILL.md").write_text(CASES[folder], encoding="utf-8")
    ours = validate_skill(skill).errors
    theirs = skills_ref_validator.validate(skill)
    assert (ours == []) == (theirs == []), {"ours": ours, "skills-ref": theirs}


def test_ascii_reading_is_stricter_than_skills_ref(tmp_path: Path) -> None:
    """skills-ref accepts any Unicode lowercase letter; we read the spec's `a-z` literally."""
    skill = tmp_path / "café"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\nname: café\ndescription: d\n---\n", "utf-8")
    assert skills_ref_validator.validate(skill) == []
    assert any("invalid characters" in e for e in validate_skill(skill).errors)
