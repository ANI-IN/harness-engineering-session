"""Negative proof for the prose checker: banned dashes found, exemptions honored."""

from pathlib import Path

from tools.lint import check_prose


def _md(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_em_dash_detected_with_location(tmp_path):
    _md(tmp_path, "a.md", "First line fine.\nBad line — right here.\n")
    errors = check_prose.check_tree(tmp_path)
    assert len(errors) == 1
    assert errors[0].startswith("a.md:2:")
    assert "em-dash (U+2014)" in errors[0]


def test_en_dash_detected(tmp_path):
    _md(tmp_path, "a.md", "Sessions 1–2 exist.\n")
    errors = check_prose.check_tree(tmp_path)
    assert len(errors) == 1
    assert "en-dash (U+2013)" in errors[0]


def test_code_fence_exempt(tmp_path):
    _md(tmp_path, "a.md", "```text\ncode — with dash\n```\n")
    assert check_prose.check_tree(tmp_path) == []


def test_inline_code_exempt(tmp_path):
    _md(tmp_path, "a.md", "Use `a — b` as-is.\n")
    assert check_prose.check_tree(tmp_path) == []


def test_link_target_exempt_but_label_checked(tmp_path):
    _md(tmp_path, "ok.md", "[label](https://example.com/a–b)\n")
    assert check_prose.check_tree(tmp_path) == []
    _md(tmp_path, "bad.md", "[label — dashed](https://example.com/x)\n")
    errors = check_prose.check_tree(tmp_path)
    assert len(errors) == 1
    assert errors[0].startswith("bad.md:1")


def test_mermaid_labels_are_checked(tmp_path):
    _md(tmp_path, "a.md", "```mermaid\nflowchart LR\n  A[bad — label] --> B\n```\n")
    errors = check_prose.check_tree(tmp_path)
    assert len(errors) == 1
    assert "em-dash" in errors[0]


def test_fixtures_and_expected_dirs_exempt(tmp_path):
    _md(tmp_path, "unit/fixtures/f.md", "dash — allowed in fixtures\n")
    _md(tmp_path, "unit/expected/e.md", "dash – allowed in expected\n")
    assert check_prose.check_tree(tmp_path) == []
