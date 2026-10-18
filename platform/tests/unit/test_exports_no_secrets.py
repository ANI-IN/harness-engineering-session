"""Export inspection (2): files written for reports never carry API keys or host paths.

The A/B, the experiment runner, and the report writer run against a miniature course repository
with a Settings carrying fake keys and arm workspaces under a recognisable host directory. Every
file they write (`exports/scores`, `exports/experiments`, the report, and the run's `ab.json`) is
scanned for key-shaped strings (the redaction patterns), the fake key values, the home and temp
directories, and absolute Windows or POSIX paths. The repository's committed `exports/` directory,
when there is one, is scanned the same way.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

from shipharness.ab.demo import AB_RECORD, ABTask, run_ab
from shipharness.ab.experiments import ExperimentPlan, run_experiments
from shipharness.ab.report import write_report
from shipharness.config import Settings
from shipharness.config.prices import REPO_ROOT
from shipharness.log_setup import KEY_PATTERNS
from shipharness.runner.model import tool_step
from tests.unit.ab.conftest import git, write
from tests.unit.ab.test_demo import LINE, Clients, make_deps
from tests.unit.ab.test_experiments import FakeEvaluate, FakeLangSmith, example

FAKE_OPENAI = "sk-test-" + "Ab3dEf6hIj9kLm2nOp5qRs8t"
FAKE_LANGSMITH = "lsv2_pt_" + "0123456789abcdef0123456789abcdef_1a2b3c4d5e"
HOST_MARK = "HOSTMARK-7c1d"

WINDOWS_ABS = re.compile(r"(?<![A-Za-z])[A-Za-z]:(?:\\\\|\\|/)[^\s\"']")
POSIX_ABS = re.compile(r"(?<![\w.:/-])/(?:home|Users|tmp|var|private|root|mnt|opt|etc|srv)/")


def _forms(path: str) -> set[str]:
    """A host path as raw text, JSON-escaped, and with forward slashes."""
    return {path, path.replace("\\", "\\\\"), path.replace("\\", "/")} - {""}


def leaks(text: str, extra_paths: list[str] | None = None) -> list[str]:
    found = [f"key pattern {p.pattern}" for p in KEY_PATTERNS if p.search(text)]
    found += [f"fake key {k[:8]}..." for k in (FAKE_OPENAI, FAKE_LANGSMITH) if k in text]
    paths = [str(Path.home()), tempfile.gettempdir(), *(extra_paths or [])]
    found += [f"host path {form}" for p in paths for form in _forms(p) if form in text]
    if HOST_MARK in text:
        found.append(f"host marker {HOST_MARK}")
    found += [f"windows path {m.group(0)}" for m in WINDOWS_ABS.finditer(text)]
    found += [f"posix path {m.group(0)}" for m in POSIX_ABS.finditer(text)]
    return found


def scan(files: list[Path], extra_paths: list[str] | None = None) -> dict[str, list[str]]:
    report: dict[str, list[str]] = {}
    for path in files:
        problems = leaks(path.read_text(encoding="utf-8", errors="replace"), extra_paths)
        if problems:
            report[str(path.name)] = problems
    return report


def test_scanner_finds_what_it_looks_for(tmp_path: Path) -> None:
    for text in (
        FAKE_OPENAI,
        "sk-" + "proj-abcdefghijklmnopqrstuvwxyz",
        json.dumps({"p": str(tmp_path)}),
        "C:/Users/someone/ws",
        "see /home/someone/ws",
        f"{HOST_MARK}/ws",
    ):
        assert leaks(text, [str(tmp_path)]), text
    assert not leaks("https://smith.example/compare/x 2026-10-16T12:30:00Z tests/visible/a.py")


@pytest.fixture
def course(tmp_path: Path) -> Path:
    repo = tmp_path / "course"
    tt = repo / "teamtrack"
    write(tt / "app" / "main.py", "def create_app():\n    return 'app'\n")
    write(tt / "app" / "api" / "issues.py", "def list_issues():\n    return []\n")
    write(tt / "tests" / "visible" / "test_app.py", "def test_app():\n    assert True\n")
    write(tt / "tests" / "hidden" / "f1" / "test_secret.py", "def test_secret():\n    assert 1\n")
    git(repo, "init", "-q")
    git(repo, "add", "-A", "-f")
    git(repo, "commit", "-qm", "course")
    git(repo, "tag", "m1-s1-start")
    return repo


def test_export_writers_never_write_keys_or_host_paths(
    course: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_OPENAI)
    monkeypatch.setenv("LANGSMITH_API_KEY", FAKE_LANGSMITH)
    host = tmp_path / HOST_MARK
    settings = Settings(
        _env_file=None,
        openai_api_key=FAKE_OPENAI,
        langsmith_api_key=FAKE_LANGSMITH,
        runs_dir=tmp_path / "runs",
        exports_dir=tmp_path / "exports",
    )
    leaky_steps = [
        tool_step("list_dir", path=".", depth=None),
        tool_step("finish", claim="done", summary=f"built with {FAKE_OPENAI}"),
        tool_step("finish", claim="done", summary=f"tests, key {FAKE_LANGSMITH}"),
    ]
    clients = Clients(bare=leaky_steps, harness=leaky_steps)
    deps = make_deps(course, tmp_path, clients, settings=settings, workspace_base=host / "ws")
    line: dict[str, Any] = json.loads(json.dumps(LINE))
    line["inputs"]["ticket_text"] += f" (do not paste {FAKE_OPENAI})"
    result = run_ab(ABTask.from_dataset_line(line), frozenset({"instructions"}), deps)
    assert str(host) in str(result.arms["bare"].spec.workspace)  # the workspace is a host path

    deps.client_factory = lambda arm: Clients(bare=leaky_steps, harness=leaky_steps)(arm)
    plan = ExperimentPlan(
        dataset="teamtrack-features-v1",
        k=1,
        harness_layers=frozenset({"instructions"}),
        metadata={"key": FAKE_LANGSMITH},
    )
    run_experiments(
        plan, deps, FakeLangSmith([example()]), evaluate_fn=FakeEvaluate(tmp_path / "exports")
    )
    write_report(tmp_path / "exports", tmp_path / "exports" / "report")

    exports = sorted(p for p in (tmp_path / "exports").rglob("*") if p.is_file())
    kinds = {p.parent.name for p in exports}
    assert {"scores", "experiments", "report"} <= kinds
    records = [result.run_dir / AB_RECORD]
    assert scan([*exports, *records], [str(tmp_path), str(host), os.getcwd()]) == {}


def _committed_exports() -> list[Path]:
    folder = REPO_ROOT / "exports"
    if not folder.is_dir():
        return []
    done = subprocess.run(
        ["git", "ls-files", "-z", "--", "exports"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    if done.returncode != 0:  # not a git checkout: scan what is there
        return sorted(p for p in folder.rglob("*") if p.is_file())
    names = [n for n in done.stdout.decode("utf-8").split("\0") if n]
    return [REPO_ROOT / n for n in names if (REPO_ROOT / n).is_file()]


def test_committed_exports_carry_no_keys_or_host_paths() -> None:
    assert scan(_committed_exports()) == {}
