"""Negative proof for the link checker: broken links and anchors must be found."""

from pathlib import Path

from tools.lint import check_links


def _md(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_broken_relative_link_detected(tmp_path):
    md = _md(tmp_path, "a.md", "See [missing](./does-not-exist.md).\n")
    errors = check_links.check_relative([md], tmp_path)
    assert len(errors) == 1
    assert "broken link ./does-not-exist.md" in errors[0]
    assert errors[0].startswith("a.md")


def test_broken_anchor_detected(tmp_path):
    _md(tmp_path, "target.md", "# Title\n\n## Real section\n")
    md = _md(tmp_path, "a.md", "See [anchor](./target.md#no-such-heading).\n")
    errors = check_links.check_relative([md], tmp_path)
    assert len(errors) == 1
    assert "missing anchor" in errors[0]


def test_broken_same_file_anchor_detected(tmp_path):
    md = _md(tmp_path, "a.md", "Jump to [here](#nowhere).\n\n## Somewhere\n")
    errors = check_links.check_relative([md], tmp_path)
    assert len(errors) == 1
    assert "missing anchor #nowhere" in errors[0]


def test_valid_links_pass(tmp_path):
    _md(tmp_path, "target.md", "## Real section\n")
    md = _md(
        tmp_path,
        "a.md",
        "Good: [file](./target.md), [anchor](./target.md#real-section), "
        "[self](#local), [ext](https://example.com/x).\n\n## Local\n",
    )
    assert check_links.check_relative([md], tmp_path) == []


def test_links_inside_code_fences_ignored(tmp_path):
    md = _md(tmp_path, "a.md", "```text\n[not a link](./missing.md)\n```\n")
    assert check_links.check_relative([md], tmp_path) == []
