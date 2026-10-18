"""Fetch the two testgen-targets-v1 libraries at their pinned commits.

Each library is cloned into `.shipharness/libs/<name>/src` (git-ignored), its commit is verified,
and `.shipharness/libs/<name>/.venv` is created with uv and the library's test dependencies. The
library itself is not installed: a `.pth` file in the venv puts the source tree of the current
directory first on sys.path (`Library.pythonpath`), so a mutant applied to a copy of the source is
the code under test.

Usage:
  uv run python platform/scripts/fetch_testgen_libs.py            # both libraries
  uv run python platform/scripts/fetch_testgen_libs.py boltons    # one library
  uv run python platform/scripts/fetch_testgen_libs.py --check    # verify what is there; no network
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
LIBS_DIR = REPO / ".shipharness" / "libs"


@dataclass(frozen=True)
class Library:
    name: str
    url: str
    tag: str
    commit: str
    license: str
    test_deps: tuple[str, ...]
    package: str  # import name
    pythonpath: str  # directory (relative to the clone) that must be on sys.path for imports
    test_args: tuple[str, ...]  # extra pytest arguments of the upstream command
    build: str = ""  # Python run in the clone after install (upstream build steps tests rely on)


LIBS: dict[str, Library] = {
    "boltons": Library(
        name="boltons",
        url="https://github.com/mahmoud/boltons.git",
        tag="26.2.0",
        commit="4332b35a278d694f30c99881faa61cde695c7a96",
        license="BSD-3-Clause",
        test_deps=("pytest==9.1.1", "pytest-cov==7.1.0"),
        package="boltons",
        pythonpath=".",
        # Upstream tox: `pytest --doctest-modules {site-packages}/boltons {repo}/tests` (G-19).
        test_args=("--doctest-modules", "boltons", "tests"),
    ),
    "wtforms": Library(
        name="wtforms",
        url="https://github.com/pallets-eco/wtforms.git",
        tag="3.2.2",
        commit="ea57c11591556333b4f0ac494d1e5d3f250ab305",
        license="BSD-3-Clause",
        test_deps=(
            "pytest==9.1.1",
            "pytest-cov==7.1.0",
            "babel==2.18.0",
            "email-validator==2.3.0",
            "markupsafe==3.0.4",
        ),
        package="wtforms",
        pythonpath="src",
        # Upstream tox: `pytest --tb=short -l`; pyproject keeps `filterwarnings = ["error"]` (G-20).
        test_args=("tests",),
        # hatch_build.py compiles the message catalogs at build time; the i18n tests need the
        # .mo files, which upstream's .gitignore excludes, so the clone stays clean.
        build=(
            "from babel.messages.frontend import CommandLineInterface as C; "
            "C().run(['pybabel', '-q', 'compile', '-d', 'src/wtforms/locale', '-D', 'wtforms'])"
        ),
    ),
}


def lib_root(name: str, libs_dir: Path = LIBS_DIR) -> Path:
    return Path(libs_dir) / name


def source_dir(name: str, libs_dir: Path = LIBS_DIR) -> Path:
    return lib_root(name, libs_dir) / "src"


def venv_python(name: str, libs_dir: Path = LIBS_DIR) -> Path:
    venv = lib_root(name, libs_dir) / ".venv"
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def _run(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed:\n{result.stdout}{result.stderr}")
    return result.stdout.strip()


def head_commit(src: Path) -> str:
    return _run(["git", "-C", str(src), "rev-parse", "HEAD"])


def is_clean(src: Path) -> bool:
    return _run(["git", "-C", str(src), "status", "--porcelain"]) == ""


def check(lib: Library, libs_dir: Path = LIBS_DIR) -> list[str]:
    """Problems with an existing checkout and venv (empty list = ready)."""
    src = source_dir(lib.name, libs_dir)
    if not (src / ".git").exists():
        return [f"{lib.name}: not cloned ({src})"]
    problems = []
    commit = head_commit(src)
    if commit != lib.commit:
        problems.append(f"{lib.name}: HEAD is {commit}, expected {lib.commit}")
    if not is_clean(src):
        problems.append(f"{lib.name}: working tree has changes (git status --porcelain)")
    if not venv_python(lib.name, libs_dir).is_file():
        problems.append(f"{lib.name}: no virtual environment at {venv_python(lib.name, libs_dir)}")
    return problems


def clone(lib: Library, libs_dir: Path = LIBS_DIR) -> None:
    src = source_dir(lib.name, libs_dir)
    if not (src / ".git").exists():
        src.mkdir(parents=True, exist_ok=True)
        _run(["git", "init", "-q", str(src)])
        _run(["git", "-C", str(src), "fetch", "-q", "--depth", "1", lib.url, lib.commit])
        _run(
            [
                "git",
                "-C",
                str(src),
                "-c",
                "advice.detachedHead=false",
                "checkout",
                "-q",
                "FETCH_HEAD",
            ]
        )
    commit = head_commit(src)
    if commit != lib.commit:
        raise RuntimeError(f"{lib.name}: cloned commit {commit} is not the pin {lib.commit}")


def make_venv(lib: Library, libs_dir: Path = LIBS_DIR) -> None:
    python = venv_python(lib.name, libs_dir)
    if not python.is_file():
        _run(["uv", "venv", "-q", "--python", "3.12", str(lib_root(lib.name, libs_dir) / ".venv")])
    _run(["uv", "pip", "install", "-q", "--python", str(python), *lib.test_deps])
    site = Path(_run([str(python), "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"]))
    (site / PTH_NAME).write_text(pth_line(lib) + "\n", encoding="utf-8")
    if lib.build:
        _run([str(python), "-c", lib.build], cwd=source_dir(lib.name, libs_dir))


PTH_NAME = "shipharness_source_path.pth"


def pth_line(lib: Library) -> str:
    """A `.pth` line that puts `<cwd>/<pythonpath>` first on sys.path when the current directory
    is a copy of this library's source (the shape `shipharness testgen` and the mutant runner use:
    `cd <copy> && python -m pytest ...`). The pinned source itself stays unmodified."""
    marker = f"{lib.pythonpath}/{lib.package}/__init__.py"
    return (
        "import os, sys; "
        f"_d = os.path.abspath({lib.pythonpath!r}); "
        f"os.path.isfile({marker!r}) and _d not in sys.path and sys.path.insert(0, _d)"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="*", choices=[[], *LIBS], default=[])
    parser.add_argument("--check", action="store_true", help="verify only; no network")
    parser.add_argument("--libs-dir", type=Path, default=LIBS_DIR)
    args = parser.parse_args(argv)
    names = args.names or list(LIBS)
    problems: list[str] = []
    for name in names:
        lib = LIBS[name]
        if not args.check:
            try:
                clone(lib, args.libs_dir)
                make_venv(lib, args.libs_dir)
            except RuntimeError as exc:
                problems.append(str(exc))
                continue
        found = check(lib, args.libs_dir)
        problems.extend(found)
        if not found:
            print(f"ok {lib.name} {lib.tag} {lib.commit} -> {source_dir(lib.name, args.libs_dir)}")
    for problem in problems:
        print(f"x {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
