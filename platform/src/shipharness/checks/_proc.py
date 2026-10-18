"""Subprocess helpers: build tools (pytest, Alembic, import-linter) run in a child interpreter.

A child process keeps the build's `app` package and tool caches out of the checker's own process,
and inside the referee container it runs as the same unprivileged user with no network.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

DEFAULT_TIMEOUT_S = 600


def child_env(build_dir: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(Path(build_dir).resolve()), env.get("PYTHONPATH", "")) if p
    )
    env.update(extra or {})
    return env


def run_python(
    args: list[str],
    build_dir: Path,
    env: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> subprocess.CompletedProcess[str]:
    """`python <args>` with the build directory as working directory and on sys.path."""
    try:
        return subprocess.run(
            [sys.executable, *args],
            cwd=build_dir,
            env=child_env(build_dir, env),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout if isinstance(exc.stdout, str) else ""
        return subprocess.CompletedProcess(exc.cmd, 124, out, f"timed out after {timeout}s")


def tail(text: str, lines: int = 8) -> str:
    return " | ".join(line.strip() for line in text.strip().splitlines()[-lines:] if line.strip())
