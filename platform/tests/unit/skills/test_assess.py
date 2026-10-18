"""harness-setup/scripts/assess.py: deterministic, read-only assessment of a repository -> HTML."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from shipharness.layout import find_repo_root
from tests.unit.skills.helpers import load_script

REPO = find_repo_root(Path(__file__))
SKILL = REPO / "use-in-your-repo" / "skills" / "harness-setup"
SCRIPT = SKILL / "scripts" / "assess.py"
TEMPLATES = SKILL / "assets" / "templates"
AREAS = ["Instructions", "State", "Scope", "Verification", "Session lifecycle"]


@pytest.fixture(scope="module")
def assess() -> ModuleType:
    return load_script(SCRIPT, "harness_assess")


def statuses(checks: list) -> dict[str, str]:
    return {c.id: c.status for c in checks}


def write(root: Path, rel: str, text: str = "x\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def full_harness_repo(root: Path) -> Path:
    """A repository set up with every harness-setup template in its documented place."""
    placement = {
        "AGENTS.md": "AGENTS.md",
        "ARCHITECTURE.md": "ARCHITECTURE.md",
        "SECURITY.md": "docs/SECURITY.md",
        "clean-state-checklist.md": "docs/clean-state-checklist.md",
        "exec-plan.md": "docs/exec-plans/active/F1.md",
        "progress.md": "progress.md",
        "session-handoff.md": "session-handoff.md",
        "feature_list.json": "feature_list.json",
        "feature_list.schema.json": "feature_list.schema.json",
        "init.sh": "init.sh",
    }
    for source, target in placement.items():
        (root / target).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TEMPLATES / source, root / target)
    for rel in (
        "docs/RELIABILITY.md",
        "docs/QUALITY_SCORE.md",
        "docs/PLANS.md",
        "docs/design-docs/index.md",
        "docs/product-specs/index.md",
        "docs/references/uv-llms.txt",
        "docs/exec-plans/completed/.gitkeep",
        "tests/test_app.py",
        ".github/workflows/ci.yml",
        ".importlinter",
        "Dockerfile",
        ".git/HEAD",
    ):
        write(root, rel)
    skill = "---\nname: demo\ndescription: Demo. Use when testing.\n---\n"
    write(root, ".agents/skills/demo/SKILL.md", skill)
    write(root, ".claude/skills/demo/SKILL.md", skill)
    write(root, "pyproject.toml", "[tool.ruff]\nline-length = 100\n\n[tool.coverage.run]\n")
    return root


def test_empty_repo_fails_the_core_checks(assess: ModuleType, tmp_path: Path) -> None:
    checks = assess.assess(tmp_path)
    found = statuses(checks)
    assert {c.area for c in checks} == set(AREAS)
    for check_id in ("I1", "I2", "I4", "S1", "S2", "S4", "C1", "V1", "V2", "L2"):
        assert found[check_id] == "fail", check_id
    assert all(c.source for c in checks)


def test_repo_built_from_the_templates_passes_every_check(
    assess: ModuleType, tmp_path: Path
) -> None:
    checks = assess.assess(full_harness_repo(tmp_path))
    failing = {c.id: (c.status, c.evidence) for c in checks if c.status != "pass"}
    assert failing == {}


def test_agents_md_pointers_that_do_not_resolve_are_listed(
    assess: ModuleType, tmp_path: Path
) -> None:
    write(tmp_path, "AGENTS.md", "# Map\n\n- [Arch](ARCHITECTURE.md)\n- `docs/SECURITY.md`\n")
    write(tmp_path, "ARCHITECTURE.md")
    check = next(c for c in assess.assess(tmp_path) if c.id == "I3")
    assert check.status == "partial"
    assert "docs/SECURITY.md" in check.evidence


def test_long_agents_md_is_not_a_map(assess: ModuleType, tmp_path: Path) -> None:
    write(tmp_path, "AGENTS.md", "rule\n" * 400)
    assert statuses(assess.assess(tmp_path))["I2"] == "fail"


def test_invalid_feature_list_is_reported(assess: ModuleType, tmp_path: Path) -> None:
    write(tmp_path, "feature_list.json", "{not json")
    check = next(c for c in assess.assess(tmp_path) if c.id == "C1")
    assert check.status == "fail" and "JSON" in check.evidence


def test_feature_list_without_passes_fails_c2(assess: ModuleType, tmp_path: Path) -> None:
    write(tmp_path, "feature_list.json", json.dumps({"features": [{"id": "F1", "status": "x"}]}))
    assert statuses(assess.assess(tmp_path))["C2"] == "fail"


def test_html_escapes_repository_content(assess: ModuleType, tmp_path: Path) -> None:
    check = assess.Check("I1", "Instructions", "t", "fail", "<script>alert(1)</script>", "f", "A1")
    html = assess.render_html(tmp_path, [check])
    assert "<script>alert" not in html and "&lt;script&gt;" in html


def test_does_not_follow_links_out_of_the_repo(assess: ModuleType, tmp_path: Path) -> None:
    outside = write(tmp_path / "outside", "AGENTS.md", "# secret map\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    try:
        os.symlink(outside, repo / "AGENTS.md")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available on this machine")
    assert statuses(assess.assess(repo))["I1"] == "fail"


def test_cli_writes_identical_html_on_every_run(tmp_path: Path) -> None:
    repo = full_harness_repo(tmp_path / "repo")
    outputs = []
    for run in ("a", "b"):
        out = tmp_path / f"{run}.html"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(repo), "--out", str(out)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "Instructions" in result.stdout
        outputs.append(out.read_bytes())
    assert outputs[0] == outputs[1]
    html = outputs[0].decode("utf-8")
    assert html.startswith("<!doctype html>")
    for area in AREAS:
        assert area in html
    assert "http://" not in html.replace("http://www.w3.org", "") and "<script" not in html


def test_cli_json_and_missing_repo(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path), "--json", "--out", str(tmp_path / "r.html")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    rows = json.loads(result.stdout)
    assert {row["area"] for row in rows} == set(AREAS)
    missing = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "nope")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert missing.returncode == 2


def test_assess_teamtrack(assess: ModuleType, tmp_path: Path) -> None:
    """The bundled demo target: the bare repo has visible tests and a handbook, but no map."""
    checks = assess.assess(REPO / "platform" / "teamtrack")
    found = statuses(checks)
    assert found["V1"] == "pass"
    assert found["I1"] == "fail"  # rules live in docs/HANDBOOK.md, not an AGENTS.md map
    assert found["C1"] == "fail"
    html = assess.render_html(REPO / "platform" / "teamtrack", checks)
    assert all(area in html for area in AREAS)


def test_text_and_html_name_checks_in_plain_words(tmp_path: Path) -> None:
    """Check ids (I1, S1, ...) stay in the JSON; the printed summary and the HTML use words."""
    out = tmp_path / "r.html"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path), "--out", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    fails = [line for line in result.stdout.splitlines() if line.startswith("FAIL")]
    assert fails and all(not re.search(r"\b[ISCVL][1-9]\b", line) for line in fails), fails
    assert "FAIL     Instructions: AGENTS.md map at the repository root" in result.stdout
    assert not re.search(r"<td>[ISCVL][1-9]</td>", out.read_text(encoding="utf-8"))
