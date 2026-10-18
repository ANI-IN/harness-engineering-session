"""Tracked text files use LF line endings: shell scripts, the Makefile, and Dockerfiles run in Linux
containers and WSL2, where a carriage return breaks them."""

from __future__ import annotations

import subprocess
from pathlib import Path

from shipharness.layout import find_repo_root

REPO = find_repo_root(Path(__file__))


def test_gitattributes_pins_lf() -> None:
    text = (REPO / ".gitattributes").read_text(encoding="utf-8")
    assert "* text=auto eol=lf" in text


def test_no_tracked_file_has_crlf_in_the_index() -> None:
    out = subprocess.run(
        ["git", "ls-files", "--eol"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout
    crlf = [line.split()[-1] for line in out.splitlines() if line.startswith("i/crlf")]
    assert crlf == []
