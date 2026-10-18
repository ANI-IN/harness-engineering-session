#!/usr/bin/env python3
"""Run `shipharness testgen` on one module: propose tests, keep only those that pass every filter.

Usage:
    python run_testgen.py --repo <path> --module <path inside repo> [--layers verify|none]
        [--max-tests N] [--sandbox docker --image <image>] [--dry-run]

`--layers verify` (default) sends every proposed test through the five filters and keeps only the
survivors; `--layers none` keeps whatever the agent writes, for comparison. The command calls a
model, so it costs money; it prints a `Cost:` line when it ends. Without `--sandbox docker`,
generated tests run on this machine (UNSANDBOXED). Exit code is the command's (0 done, 2 aborted
by a cap or timeout, 1 error). Standard library only (Python 3.10+).
"""

from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

Runner = Callable[[list[str]], int]


def default_launcher() -> list[str]:
    """The shipharness CLI on PATH, or through uv from the course checkout."""
    found = shutil.which("shipharness")
    return [found] if found else ["uv", "run", "shipharness"]


def run_command(command: list[str]) -> int:
    return subprocess.run(command, check=False).returncode


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, required=True, help="repository with the module")
    parser.add_argument("--module", required=True, help="module path relative to --repo")
    parser.add_argument("--layers", choices=["verify", "none"], default="verify")
    parser.add_argument("--max-tests", type=int, help="most tests to propose")
    parser.add_argument("--sandbox", choices=["docker"], help="run generated tests in a container")
    parser.add_argument("--image", help="container image with the repo's dependencies")
    parser.add_argument("--dry-run", action="store_true", help="print the command, run nothing")
    args = parser.parse_args(argv)
    if args.image and args.sandbox != "docker":
        parser.error("--image needs --sandbox docker")
    if args.max_tests is not None and args.max_tests < 1:
        parser.error("--max-tests must be at least 1")
    return args


def build_command(args: argparse.Namespace, launcher: list[str]) -> list[str]:
    command = [*launcher, "testgen", "--repo", str(args.repo), "--module", args.module]
    command += ["--layers", args.layers]
    if args.max_tests is not None:
        command += ["--max-tests", str(args.max_tests)]
    if args.sandbox:
        command += ["--sandbox", args.sandbox]
    if args.image:
        command += ["--image", args.image]
    return command


def main(
    argv: list[str] | None = None,
    runner: Runner = run_command,
    launcher: list[str] | None = None,
) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    module = args.repo / args.module
    if not args.repo.is_dir():
        print(f"ERROR --repo is not a directory: {args.repo}")
        return 2
    if not module.is_file():
        print(f"ERROR module not found: {module}. Give the path relative to --repo.")
        return 2
    command = build_command(args, launcher or default_launcher())
    print("command: " + " ".join(shlex.quote(part) for part in command))
    if not args.sandbox:
        print(
            "note: UNSANDBOXED. Generated tests will run on this machine with your permissions."
            " Use --sandbox docker --image <image> to run them in a container."
        )
    print("note: this calls a model and costs money; the command prints a Cost: line at the end.")
    if args.dry_run:
        return 0
    return runner(command)


if __name__ == "__main__":
    raise SystemExit(main())
