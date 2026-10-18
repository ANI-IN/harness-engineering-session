"""assured-tests/scripts/run_testgen.py: builds and runs `shipharness testgen`."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest

from shipharness.layout import find_repo_root
from tests.unit.skills.helpers import load_script

REPO = find_repo_root(Path(__file__))
SCRIPT = REPO / "use-in-your-repo" / "skills" / "assured-tests" / "scripts" / "run_testgen.py"


@pytest.fixture(scope="module")
def run_testgen() -> ModuleType:
    return load_script(SCRIPT, "assured_run_testgen")


@pytest.fixture
def target(tmp_path: Path) -> Path:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    return tmp_path


def test_builds_the_contract_command(run_testgen: ModuleType, target: Path) -> None:
    calls: list[list[str]] = []
    code = run_testgen.main(
        ["--repo", str(target), "--module", "pkg/mod.py", "--max-tests", "4"],
        runner=lambda cmd: calls.append(cmd) or 0,
        launcher=["shipharness"],
    )
    assert code == 0
    assert calls == [
        [
            "shipharness",
            "testgen",
            "--repo",
            str(target),
            "--module",
            "pkg/mod.py",
            "--layers",
            "verify",
            "--max-tests",
            "4",
        ]
    ]


def test_passes_sandbox_options_and_exit_code(run_testgen: ModuleType, target: Path) -> None:
    calls: list[list[str]] = []
    code = run_testgen.main(
        [
            "--repo",
            str(target),
            "--module",
            "pkg/mod.py",
            "--layers",
            "none",
            "--sandbox",
            "docker",
            "--image",
            "img:1",
        ],
        runner=lambda cmd: calls.append(cmd) or 2,
        launcher=["uv", "run", "shipharness"],
    )
    assert code == 2
    assert calls[0][:4] == ["uv", "run", "shipharness", "testgen"]
    assert calls[0][-6:] == ["--layers", "none", "--sandbox", "docker", "--image", "img:1"]


def test_dry_run_prints_and_does_not_run(
    run_testgen: ModuleType, target: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run_testgen.main(
        ["--repo", str(target), "--module", "pkg/mod.py", "--dry-run"],
        runner=lambda cmd: pytest.fail("must not run"),
        launcher=["shipharness"],
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "shipharness testgen --repo" in out
    assert "UNSANDBOXED" in out  # no --sandbox docker: generated tests run on this machine


def test_missing_module_is_an_error(run_testgen: ModuleType, target: Path) -> None:
    code = run_testgen.main(
        ["--repo", str(target), "--module", "pkg/missing.py"],
        runner=lambda cmd: pytest.fail("must not run"),
        launcher=["shipharness"],
    )
    assert code == 2


def test_image_requires_docker_sandbox(run_testgen: ModuleType, target: Path) -> None:
    with pytest.raises(SystemExit):
        run_testgen.main(
            ["--repo", str(target), "--module", "pkg/mod.py", "--image", "img:1"],
            runner=lambda cmd: 0,
            launcher=["shipharness"],
        )


def test_default_launcher(run_testgen: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_testgen.shutil, "which", lambda name: None)
    assert run_testgen.default_launcher() == ["uv", "run", "shipharness"]
    monkeypatch.setattr(run_testgen.shutil, "which", lambda name: f"/bin/{name}")
    assert run_testgen.default_launcher() == ["/bin/shipharness"]
