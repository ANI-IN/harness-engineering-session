from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from shipharness.layout import find_repo_root

REPO = find_repo_root(Path(__file__))
SCRIPT = REPO / "platform" / "scripts" / "lint_prose.py"


def lint(*paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, paths)],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )


def test_flags_banned_words(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("A seamless and powerful way to leverage agents.\n", encoding="utf-8")
    result = lint(doc)
    assert result.returncode == 1
    for word in ("seamless", "powerful", "leverage"):
        assert word in result.stdout.lower()


def test_flags_banned_phrases_case_insensitively(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("It's important to note that this is a Deep Dive.\n", encoding="utf-8")
    assert lint(doc).returncode == 1


def test_flags_tonight(tmp_path: Path) -> None:
    # Pages are read on other days too: "tonight" goes stale; say "today", "in class",
    # "this session" or "this run".
    doc = tmp_path / "doc.md"
    doc.write_text("Tonight's run is one dot.\nWe watch it tonight.\n", encoding="utf-8")
    result = lint(doc)
    assert result.returncode == 1
    assert "2 problems" in result.stdout
    assert "'tonight'" in result.stdout.lower()


def test_plain_time_words_pass(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("Today's run is one dot. In class we watch this run.\n", encoding="utf-8")
    assert lint(doc).returncode == 0


def test_flags_emoji(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("Done \U0001f680\n", encoding="utf-8")
    result = lint(doc)
    assert result.returncode == 1
    assert "emoji" in result.stdout


def test_allows_cited_source_title(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(
        "OpenAI, Harness engineering: leveraging Codex in an agent-first world.\n", encoding="utf-8"
    )
    assert lint(doc).returncode == 0


def test_allows_marked_line(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("Banned list: seamless, robust <!-- lint-prose: allow -->\n", encoding="utf-8")
    assert lint(doc).returncode == 0


def test_status_symbols_are_not_emoji(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("Gate pills: ⏳ then ✓ or ✗; warning ⚠\n", encoding="utf-8")
    assert lint(doc).returncode == 0


def test_repository_docs_pass() -> None:
    result = lint()
    assert result.returncode == 0, result.stdout


def test_verbatim_owner_notes_are_not_linted(tmp_path: Path) -> None:
    # The private notes folder quotes the owner's instructions verbatim; the linter must not
    # force edits to them (CI failed on a banned word in a quoted message, 2026-10-17).
    notes = tmp_path / "instructor" / "engineering-notes"
    notes.mkdir(parents=True)
    (notes / "owner.md").write_text("a seamless journey\n", encoding="utf-8")
    (tmp_path / "instructor" / "guide.md").write_text("plain text\n", encoding="utf-8")
    result = lint(tmp_path / "instructor")
    assert result.returncode == 0, result.stdout
    assert "1 files checked" in result.stdout
