#!/usr/bin/env python3
"""Toolchain doctor: print versions and check them against the repo pins.

Pins checked: .python-version (major.minor), .nvmrc (Node major),
package.json packageManager (pnpm major).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def run_version(command: list[str]) -> str:
    if shutil.which(command[0]) is None:
        return "NOT FOUND"
    try:
        out = subprocess.run(command, capture_output=True, text=True, timeout=30)
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except Exception as error:  # noqa: BLE001
        return f"error: {error}"


def main() -> int:
    python_pin = (REPO_ROOT / ".python-version").read_text().strip()
    node_pin = (REPO_ROOT / ".nvmrc").read_text().strip()
    package_json = json.loads((REPO_ROOT / "package.json").read_text())
    pnpm_pin = package_json.get("packageManager", "pnpm@(unpinned)")

    checks = [
        ("python", ["python", "--version"], python_pin),
        ("node", ["node", "--version"], f"v{node_pin}"),
        ("pnpm", ["pnpm", "--version"], pnpm_pin.split("@")[1].split("+")[0]
            if "@" in pnpm_pin else ""),
        ("uv", ["uv", "--version"], ""),
        ("shellcheck", ["shellcheck", "--version"], ""),
    ]

    failures = 0
    for name, command, pin in checks:
        version = run_version(command)
        if name == "shellcheck" and version not in ("NOT FOUND",):
            out = subprocess.run(command, capture_output=True, text=True).stdout
            match = re.search(r"version: ([\d.]+)", out)
            if match:
                version = f"shellcheck {match.group(1)}"
        status = "ok"
        if version == "NOT FOUND":
            status = "MISSING"
            failures += 1
        elif pin and pin not in version:
            # Major-level tolerance: compare the first numeric component.
            pin_major = re.sub(r"^v", "", pin).split(".")[0]
            ver_major_match = re.search(r"(\d+)", version)
            if not ver_major_match or ver_major_match.group(1) != re.sub(r"\D", "", pin_major):
                status = f"PIN MISMATCH (want {pin})"
                failures += 1
        print(f"doctor: {name:11s} {version:40s} [{status}]")

    if failures:
        print(f"doctor: {failures} problem(s)")
        return 1
    print("doctor: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
