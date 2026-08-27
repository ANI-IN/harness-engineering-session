#!/usr/bin/env python3
"""Verify every unit from tracked content only.

Every other gate reads the working tree, where a file can be present and
uncommitted at the same time. Twice that gap shipped a broken tree while
`make status` stayed green: `kb-data/` withheld a project's corpus, then
`*.log` withheld four of a lecture's workspace fixtures. Both were found
by accident, in a checkout that happened to lack them.

This gate removes the accident. It exports `HEAD` (tracked content, with
ignored and untracked files absent by construction), then runs the whole
conformance suite inside that export. A unit whose fixtures or expected
outputs are not committed fails here, in both tracks, for the same
reason a learner cloning the repository would fail.

`node_modules/` is linked in rather than exported: it is an installed
dependency, not repository content, and the export deliberately has no
package manager run against it.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def export_tracked(root: Path, destination: Path, ref: str = "HEAD") -> int:
    """Extract `ref`'s tracked content into `destination`. Returns file count."""
    archive = destination.parent / "tracked.tar"
    with archive.open("wb") as handle:
        subprocess.run(
            ["git", "archive", "--format=tar", ref],
            cwd=root, stdout=handle, check=True, timeout=300,
        )
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        tar.extractall(destination, filter="data")
    archive.unlink()
    return sum(1 for member in members if member.isfile())


def run_conformance(checkout: Path, node_modules: Path | None) -> tuple[int, str]:
    """Run the exported tree's own conformance runner inside the export."""
    if node_modules is not None and node_modules.is_dir():
        link = checkout / "node_modules"
        if not link.exists():
            link.symlink_to(node_modules)
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)
    proc = subprocess.run(
        ["uv", "run", "python", "tools/conformance/runner.py"],
        cwd=checkout, capture_output=True, text=True, env=env, timeout=3600,
    )
    return proc.returncode, (proc.stdout + proc.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD", help="commit-ish to export (default HEAD)")
    parser.add_argument("--keep", action="store_true", help="leave the export in place")
    args = parser.parse_args()

    workdir = Path(tempfile.mkdtemp(prefix="fresh-checkout-"))
    checkout = workdir / "tree"
    checkout.mkdir()
    try:
        count = export_tracked(REPO_ROOT, checkout, args.ref)
        print(f"fresh-checkout: exported {count} tracked file(s) from {args.ref}")
        code, output = run_conformance(checkout, REPO_ROOT / "node_modules")
        tail = output.strip().split("\n")
        summary = next(
            (line for line in reversed(tail) if line.startswith("conformance:")), ""
        )
        print(f"fresh-checkout: {summary}" if summary else output.strip())
        if code != 0:
            print("fresh-checkout: FAIL, units do not pass from tracked content alone")
            for line in tail:
                stripped = line.strip()
                if stripped.startswith("[FAIL]") or ": FAIL" in stripped:
                    print(f"  {stripped}")
            print(
                "  A file every gate can see is not necessarily a file git has. "
                "Check .gitignore and `git status --ignored`."
            )
            return 1
        print("fresh-checkout: OK")
        return 0
    finally:
        if args.keep:
            print(f"fresh-checkout: kept {checkout}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
