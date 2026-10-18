"""scripts/fetch_testgen_libs.py: pins, paths, and the source-path hook (no network)."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

from .testgen_support import LIBRARIES, SOURCES, load_script


@pytest.fixture(scope="module")
def fetch() -> Any:
    return load_script("fetch_testgen_libs")


def test_pins_match_the_contract_and_the_dataset_sources(fetch: Any) -> None:
    assert fetch.LIBS["boltons"].commit == "4332b35a278d694f30c99881faa61cde695c7a96"
    assert fetch.LIBS["boltons"].tag == "26.2.0"
    assert fetch.LIBS["wtforms"].commit == "ea57c11591556333b4f0ac494d1e5d3f250ab305"
    assert fetch.LIBS["wtforms"].tag == "3.2.2"
    sources = tomllib.loads(SOURCES.read_text(encoding="utf-8"))["repos"]
    for name in LIBRARIES:
        lib = fetch.LIBS[name]
        assert sources[name]["commit"] == lib.commit
        assert sources[name]["pin"] == lib.tag
        assert sources[name]["license"] == lib.license


def test_libraries_live_under_the_ignored_state_directory(fetch: Any, tmp_path: Path) -> None:
    assert fetch.LIBS_DIR.parts[-2:] == (".shipharness", "libs")
    assert fetch.source_dir("boltons", tmp_path) == tmp_path / "boltons" / "src"
    python = fetch.venv_python("wtforms", tmp_path)
    assert python.parent.parent == tmp_path / "wtforms" / ".venv"


def test_check_reports_a_missing_clone(fetch: Any, tmp_path: Path) -> None:
    problems = fetch.check(fetch.LIBS["boltons"], tmp_path)
    assert problems and "not cloned" in problems[0]
    assert fetch.main(["--check", "--libs-dir", str(tmp_path)]) == 1


@pytest.mark.parametrize("name", LIBRARIES)
def test_pth_hook_puts_the_current_source_copy_first(fetch: Any, name: str, tmp_path: Path) -> None:
    lib = fetch.LIBS[name]
    copy = tmp_path / "copy"
    package = copy / lib.pythonpath / lib.package
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    code = fetch.pth_line(lib) + "\nimport sys; print(sys.path[0])"
    out = subprocess.run(
        [sys.executable, "-I", "-c", code], cwd=copy, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert os.path.normcase(out) == os.path.normcase(str((copy / lib.pythonpath).resolve()))
    elsewhere = subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert os.path.normcase(elsewhere) != os.path.normcase(
        str((tmp_path / lib.pythonpath).resolve())
    )
