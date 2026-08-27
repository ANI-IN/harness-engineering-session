"""The fresh-checkout gate must see exactly what a clone sees."""

import subprocess
from pathlib import Path

from tools import check_fresh_checkout


def _repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, timeout=60)
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"], cwd=root, check=True, timeout=60
    )
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True, timeout=60)


def test_export_omits_ignored_and_untracked_files(tmp_path):
    """The failure this gate exists for: a fixture present on disk, absent from git."""
    source = tmp_path / "source"
    source.mkdir()
    _repo(source)
    (source / ".gitignore").write_text("*.log\n", encoding="utf-8")
    fixtures = source / "lectures/lecture-01-x/code/fixtures"
    fixtures.mkdir(parents=True)
    (fixtures / "committed.json").write_text("{}\n", encoding="utf-8")
    (fixtures / "swallowed.log").write_text("recorded run\n", encoding="utf-8")
    (fixtures / "never-added.json").write_text("{}\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore", str(fixtures / "committed.json")],
                   cwd=source, check=True, timeout=60)
    subprocess.run(["git", "commit", "-qm", "first"], cwd=source, check=True, timeout=60)

    out = tmp_path / "export"
    out.mkdir()
    count = check_fresh_checkout.export_tracked(source, out)

    rel = "lectures/lecture-01-x/code/fixtures"
    assert (out / rel / "committed.json").is_file()
    assert not (out / rel / "swallowed.log").exists(), "an ignored fixture must not appear"
    assert not (out / rel / "never-added.json").exists(), "an untracked fixture must not appear"
    assert count == 2


def test_export_reports_the_file_count(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    _repo(source)
    (source / "a.txt").write_text("a\n", encoding="utf-8")
    (source / "b.txt").write_text("b\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=source, check=True, timeout=60)
    subprocess.run(["git", "commit", "-qm", "first"], cwd=source, check=True, timeout=60)
    out = tmp_path / "export"
    out.mkdir()
    assert check_fresh_checkout.export_tracked(source, out) == 2
