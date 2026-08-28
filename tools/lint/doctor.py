#!/usr/bin/env python3
"""Toolchain doctor: print versions and check them against the repo pins.

Pins checked: .python-version (major.minor), .nvmrc (Node major),
package.json packageManager (pnpm major).

--track scopes the requirements to what that track actually needs:

  python      python + uv. A Python-only machine passes.
  typescript  node + pnpm, AND python + uv, because the course's
              verification machinery (the conformance runner, the verify
              loop, every lint) is Python tooling by declared exception
              (docs/conventions.md); uv reaches it with zero project
              installs.
  both        everything above plus shellcheck (repo-level gates).

`make doctor TRACK=python` and `make setup TRACK=python` honor the same
choice; docs/choosing-your-track.md states the model.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Directories a file-sync client owns. A working copy inside one of these is
# raced by the client: it recreates directories the gates have just removed,
# mutates files mid-run (including .git/index), and leaves numbered conflict
# copies such as `kb-data 2`. The visible symptom is a gate failing on a tree
# nobody touched, which reads as a defect in this repository and is not one.
# Warn, never fail: it is the user's machine and their choice.
SYNC_ROOTS = (
    ("iCloud Drive", "Library/Mobile Documents"),
    ("iCloud Drive", "Library/CloudStorage/iCloud"),
    ("Dropbox", "Dropbox"),
    ("OneDrive", "OneDrive"),
    ("Google Drive", "Google Drive"),
    ("Google Drive", "Library/CloudStorage/GoogleDrive"),
    ("a cloud sync client", "Library/CloudStorage"),
)


def sync_client_owning(path: Path, home: Path) -> str | None:
    """The sync client that owns `path`, or None.

    Two ways a path lands inside one: it literally sits under the client's
    directory, or macOS has redirected Desktop and Documents into iCloud,
    which leaves the paths looking ordinary while the storage is synced.
    """
    resolved = Path(path).resolve()
    parts = resolved.parts
    for label, marker in SYNC_ROOTS:
        needle = tuple(Path(marker).parts)
        for index in range(len(parts) - len(needle) + 1):
            window = parts[index:index + len(needle)]
            # All components but the last must match exactly; the last may be
            # a prefix, because these clients append an account to the folder
            # name ("OneDrive - Acme", "GoogleDrive-me@example.com").
            if window[:-1] == needle[:-1] and window[-1].startswith(needle[-1]):
                return label
    # macOS "Desktop & Documents" sync: the folder is redirected, so the path
    # reads as ~/Desktop while the bytes live in CloudDocs.
    icloud = home / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
    for folder in ("Desktop", "Documents"):
        if (icloud / folder).is_dir() and resolved.is_relative_to(home / folder):
            return "iCloud Drive (Desktop and Documents sync)"
    return None


def report_sync_warning(root: Path) -> bool:
    """Print a loud warning when the working copy is inside a sync root."""
    client = sync_client_owning(root, Path.home())
    if client is None:
        return False
    print()
    print("doctor: WARNING  this working copy is inside " + client + ".")
    print("doctor: WARNING  A sync client races the working tree: it recreates")
    print("doctor: WARNING  directories the gates just removed, edits files")
    print("doctor: WARNING  mid-run including .git/index, and leaves numbered")
    print("doctor: WARNING  conflict copies such as 'kb-data 2'.")
    print("doctor: WARNING  The symptom is `make status` failing on a tree you")
    print("doctor: WARNING  did not touch. That is the sync, not this module.")
    print("doctor: WARNING  Fix: clone to an unsynced path, for example ~/src.")
    print("doctor: WARNING  This is a warning, not a failure. Your machine.")
    print()
    return True


TRACK_TOOLS = {
    "python": ("python", "uv"),
    "typescript": ("python", "node", "pnpm", "uv"),
    "both": ("python", "node", "pnpm", "uv", "shellcheck"),
}


def run_version(command: list[str]) -> str:
    if shutil.which(command[0]) is None:
        return "NOT FOUND"
    try:
        out = subprocess.run(command, capture_output=True, text=True, timeout=30)
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except Exception as error:  # noqa: BLE001
        return f"error: {error}"


def main() -> int:
    parser = argparse.ArgumentParser(description="toolchain doctor")
    parser.add_argument(
        "--track", choices=["python", "typescript", "both"], default="both",
        help="scope the required toolchain to one track (default: both)",
    )
    args = parser.parse_args()

    python_pin = (REPO_ROOT / ".python-version").read_text().strip()
    node_pin = (REPO_ROOT / ".nvmrc").read_text().strip()
    package_json = json.loads((REPO_ROOT / "package.json").read_text())
    pnpm_pin = package_json.get("packageManager", "pnpm@(unpinned)")

    all_checks = [
        ("python", ["python", "--version"], python_pin),
        ("node", ["node", "--version"], f"v{node_pin}"),
        ("pnpm", ["pnpm", "--version"], pnpm_pin.split("@")[1].split("+")[0]
            if "@" in pnpm_pin else ""),
        ("uv", ["uv", "--version"], ""),
        ("shellcheck", ["shellcheck", "--version"], ""),
    ]
    required = TRACK_TOOLS[args.track]
    checks = [check for check in all_checks if check[0] in required]

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

    if args.track != "both":
        skipped = ", ".join(
            name for name, _, _ in all_checks if name not in required
        )
        note = "python + uv power the course's verification tooling for every track"
        print(f"doctor: track={args.track} ({skipped} not required; {note})")
    synced = report_sync_warning(REPO_ROOT)
    if failures:
        print(f"doctor: {failures} problem(s)")
        return 1
    print("doctor: OK" + (" (with 1 warning)" if synced else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
