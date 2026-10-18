"""Secrets hygiene: .env is never tracked; no tracked file contains an API key."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from shipharness.layout import find_repo_root

REPO_ROOT = find_repo_root(Path(__file__))

# OpenAI keys start with "sk-"; LangSmith keys start with "lsv2_pt_" or "lsv2_sk_".
KEY_PATTERNS = [
    re.compile(r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"\blsv2_(?:pt|sk)_[A-Za-z0-9_]{20,}"),
]


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )


def _tracked_files() -> list[str]:
    result = _git("ls-files", "-z")
    if result.returncode != 0:
        pytest.skip("not a git checkout")
    return [name for name in result.stdout.split("\0") if name]


def test_env_file_is_not_tracked() -> None:
    tracked = _tracked_files()
    env_files = [
        name
        for name in tracked
        if Path(name).name.startswith(".env") and Path(name).name != ".env.example"
    ]
    assert env_files == [], f"secret env files are tracked by git: {env_files}"


def test_env_file_is_gitignored() -> None:
    _tracked_files()  # skips outside a git checkout
    result = _git("check-ignore", "--quiet", ".env")
    assert result.returncode == 0, ".env must be listed in .gitignore"


def test_env_example_has_empty_keys() -> None:
    text = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    for key in ("OPENAI_API_KEY", "LANGSMITH_API_KEY"):
        match = re.search(rf"^{key}=(.*)$", text, flags=re.MULTILINE)
        assert match is not None, f"{key} missing from .env.example"
        assert match.group(1).strip() == "", f"{key} must be empty in .env.example"


def test_no_api_keys_in_tracked_files() -> None:
    offenders: list[str] = []
    for name in _tracked_files():
        path = REPO_ROOT / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable file
        for pattern in KEY_PATTERNS:
            if pattern.search(text):
                offenders.append(name)
                break
    assert offenders == [], f"possible API keys found in tracked files: {offenders}"
