"""Negative proof for the README-command gate: extraction and failure
detection must both work, and the real tree must carry a healthy floor."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import check_readme_commands as crc  # noqa: E402


def _readme(tmp_path: Path, rel: str, text: str) -> Path:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_fences_extracted_only_from_named_sections(tmp_path):
    _readme(
        tmp_path, "lectures/lecture-01-x/README.md",
        "# T\n\n## Demo\n\n### Python\n\n```sh\necho demo\n```\n\n"
        "## Hints\n\n```sh\necho never-run\n```\n\n"
        "## Usage\n\n```sh\necho usage\n```\n",
    )
    fences = crc.discover_fences(tmp_path)
    assert [(f.section, f.script.strip()) for f in fences] == [
        ("Demo", "echo demo"), ("Usage", "echo usage"),
    ]


def test_fence_exit_annotation_is_honored(tmp_path):
    _readme(
        tmp_path, "lectures/lecture-01-x/README.md",
        "# T\n\n## Demo\n\n<!-- fence-exit: 1 -->\n```sh\nexit 1\n```\n",
    )
    fences = crc.discover_fences(tmp_path)
    assert fences[0].expected_exit == 1
    assert crc.run_readme_fences(fences[0].readme, fences) == []


def test_failing_documented_command_is_detected(tmp_path):
    _readme(
        tmp_path, "projects/project-01-x/README.md",
        "# T\n\n## Usage\n\n```sh\nbash -c 'exit 7'\n```\n",
    )
    fences = crc.discover_fences(tmp_path)
    failures = crc.run_readme_fences(fences[0].readme, fences)
    assert len(failures) == 1
    assert "exit 7 != expected 0" in failures[0]


def test_mid_fence_failure_is_not_masked_by_a_later_success(tmp_path):
    _readme(
        tmp_path, "projects/project-01-x/README.md",
        "# T\n\n## Usage\n\n```sh\nfalse\necho recovered\n```\n",
    )
    fences = crc.discover_fences(tmp_path)
    failures = crc.run_readme_fences(fences[0].readme, fences)
    assert len(failures) == 1


def test_real_tree_meets_the_floor():
    fences = crc.discover_fences()
    assert len(fences) >= 26
    sections = {fence.section for fence in fences}
    assert {"Setup", "Usage", "Demo", "Demo flow"} <= sections
