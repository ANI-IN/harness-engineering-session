"""`shipharness skills validate`: skills-ref checks as errors, spec recommendations as warnings."""

from __future__ import annotations

from pathlib import Path

import pytest

from shipharness.skills_cli.validate import parse_skill_frontmatter, validate_path, validate_skill

GOOD = (
    "---\nname: {name}\ndescription: Does a thing. Use when the thing is needed.\n---\n\n# Body\n"
)


def make_skill(root: Path, name: str, text: str | None = None) -> Path:
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(
        GOOD.format(name=name) if text is None else text, encoding="utf-8"
    )
    return folder


def errors_of(folder: Path) -> list[str]:
    return validate_skill(folder).errors


# --- frontmatter parsing -------------------------------------------------------------------


def test_parses_scalars_block_scalars_quotes_and_metadata() -> None:
    text = (
        "---\n"
        "# a comment line\n"
        "name: my-skill\n"
        "description: >\n"
        "  Folded text\n"
        "  over two lines.\n"
        "license: 'MIT'\n"
        'compatibility: "Python 3.12, uv"\n'
        "metadata:\n"
        "  owner: course\n"
        '  version: "1.0"\n'
        "---\nbody\n"
    )
    fields, body_start = parse_skill_frontmatter(text)
    assert fields == {
        "name": "my-skill",
        "description": "Folded text over two lines.",
        "license": "MIT",
        "compatibility": "Python 3.12, uv",
        "metadata": {"owner": "course", "version": "1.0"},
    }
    assert body_start == 13


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("name: x\n", "must start with YAML frontmatter"),
        ("---\nname: x\n", "not closed"),
        ("---\nname: x\nname: y\n---\n", "duplicate key"),
        ("---\nname: [a, b]\n---\n", "flow style"),
        ("---\ndescription: Use when: something\n---\n", "quote the value"),
        ("---\n  name: x\n---\n", "unexpected indentation"),
        ("---\njust text\n---\n", "not a key"),
        ("---\n---\n", "must be a YAML mapping"),
    ],
)
def test_rejects_unparseable_frontmatter(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_skill_frontmatter(text)


# --- errors: the skills-ref checks ---------------------------------------------------------


def test_valid_skill_has_no_errors_or_warnings(tmp_path: Path) -> None:
    report = validate_skill(make_skill(tmp_path, "good-skill"))
    assert report.errors == []
    assert report.warnings == []
    assert report.name == "good-skill"
    assert report.lines == 6


def test_missing_skill_md(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    assert errors_of(tmp_path / "empty") == ["Missing required file: SKILL.md"]


def test_unknown_field_is_an_error(tmp_path: Path) -> None:
    text = "---\nname: odd\ndescription: d\ndisable-model-invocation: true\n---\n"
    errors = errors_of(make_skill(tmp_path, "odd", text))
    assert any("Unexpected fields in frontmatter: disable-model-invocation" in e for e in errors)


@pytest.mark.parametrize(
    ("folder", "name", "message"),
    [
        ("Upper", "Upper", "lowercase"),
        ("-lead", "-lead", "start or end with a hyphen"),
        ("trail-", "trail-", "start or end with a hyphen"),
        ("dou--ble", "dou--ble", "consecutive hyphens"),
        ("under_score", "under_score", "invalid characters"),
        ("café", "café", "invalid characters"),  # ASCII reading of the charset
        ("a" * 65, "a" * 65, "64 character limit"),
        ("folder", "other", "must match skill name"),
    ],
)
def test_name_rules(tmp_path: Path, folder: str, name: str, message: str) -> None:
    text = f"---\nname: {name}\ndescription: d\n---\n"
    errors = errors_of(make_skill(tmp_path, folder, text))
    assert any(message in e for e in errors), errors


def test_missing_name_and_description(tmp_path: Path) -> None:
    errors = errors_of(make_skill(tmp_path, "bare", "---\nlicense: MIT\n---\n"))
    assert "Missing required field in frontmatter: name" in errors
    assert "Missing required field in frontmatter: description" in errors


def test_description_and_compatibility_limits(tmp_path: Path) -> None:
    text = f"---\nname: long\ndescription: {'d' * 1025}\ncompatibility: {'c' * 501}\n---\n"
    errors = errors_of(make_skill(tmp_path, "long", text))
    assert any("Description exceeds 1024 character limit" in e for e in errors)
    assert any("Compatibility exceeds 500 character limit" in e for e in errors)


def test_empty_description_is_an_error(tmp_path: Path) -> None:
    errors = errors_of(make_skill(tmp_path, "nodesc", "---\nname: nodesc\ndescription:\n---\n"))
    assert "Field 'description' must be a non-empty string" in errors


def test_metadata_must_map_strings_to_strings(tmp_path: Path) -> None:
    text = "---\nname: meta\ndescription: d\nmetadata: flat\n---\n"
    errors = errors_of(make_skill(tmp_path, "meta", text))
    assert "Field 'metadata' must be a map of string keys to string values" in errors


def test_unparseable_frontmatter_is_reported_as_an_error(tmp_path: Path) -> None:
    errors = errors_of(make_skill(tmp_path, "broken", "no frontmatter\n"))
    assert len(errors) == 1 and "frontmatter" in errors[0]


# --- warnings: spec recommendations --------------------------------------------------------


def test_warns_over_500_lines(tmp_path: Path) -> None:
    text = GOOD.format(name="big") + "line\n" * 500
    report = validate_skill(make_skill(tmp_path, "big", text))
    assert report.errors == []
    assert any("over 500 lines" in w for w in report.warnings)


def test_warns_on_missing_referenced_files(tmp_path: Path) -> None:
    text = GOOD.format(name="refs") + "See [the guide](references/guide.md) and `scripts/run.py`.\n"
    report = validate_skill(make_skill(tmp_path, "refs", text))
    assert any("references/guide.md" in w and "missing" in w for w in report.warnings)
    assert any("scripts/run.py" in w and "missing" in w for w in report.warnings)


def test_existing_references_and_urls_do_not_warn(tmp_path: Path) -> None:
    text = (
        GOOD.format(name="ok-refs")
        + "Read [guide](references/guide.md), [site](https://agentskills.io/specification),"
        + " [top](#body), and run `scripts/run.py`. Templates live in `assets/templates/`.\n"
    )
    folder = make_skill(tmp_path, "ok-refs", text)
    (folder / "references").mkdir()
    (folder / "references" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (folder / "scripts").mkdir()
    (folder / "scripts" / "run.py").write_text("print(1)\n", encoding="utf-8")
    (folder / "assets" / "templates").mkdir(parents=True)
    assert validate_skill(folder).warnings == []


def test_warns_on_reference_chains_deeper_than_one_level(tmp_path: Path) -> None:
    text = GOOD.format(name="chain") + "Read [a](references/a.md).\n"
    folder = make_skill(tmp_path, "chain", text)
    (folder / "references").mkdir()
    (folder / "references" / "a.md").write_text("Then read [b](references/b.md).\n", "utf-8")
    (folder / "references" / "b.md").write_text("# B\n", encoding="utf-8")
    report = validate_skill(folder)
    assert any("one level deep" in w and "references/a.md" in w for w in report.warnings)


def test_warns_on_references_outside_the_skill(tmp_path: Path) -> None:
    text = GOOD.format(name="escape") + "Read [x](../other/SKILL.md).\n"
    report = validate_skill(make_skill(tmp_path, "escape", text))
    assert any("outside the skill" in w for w in report.warnings)


# --- path handling -------------------------------------------------------------------------


def test_validate_path_accepts_one_skill_or_a_folder_of_skills(tmp_path: Path) -> None:
    make_skill(tmp_path, "one")
    make_skill(tmp_path, "two")
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "__pycache__").mkdir()
    assert [r.name for r in validate_path(tmp_path)] == ["one", "two"]
    assert [r.name for r in validate_path(tmp_path / "one")] == ["one"]


def test_validate_path_reports_subfolders_without_skill_md(tmp_path: Path) -> None:
    make_skill(tmp_path, "one")
    (tmp_path / "notes").mkdir()
    reports = validate_path(tmp_path)
    assert [r.errors for r in reports if r.folder.name == "notes"] == [
        ["Missing required file: SKILL.md"]
    ]


def test_validate_path_missing_directory(tmp_path: Path) -> None:
    reports = validate_path(tmp_path / "nope")
    assert len(reports) == 1 and "does not exist" in reports[0].errors[0]
