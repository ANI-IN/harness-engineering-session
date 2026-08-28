#!/usr/bin/env python3
"""Execute every learner-facing README command literally.

The C6 fresh-clone review found the project READMEs' documented commands
failing on a fresh clone while nineteen units of gates stayed green:
`verify.sh` self-locates, so nothing ever ran what the learner actually
types. A command printed for a learner that has never been executed is the
same defect class as a hand-typed figure.

This gate closes it mechanically: every ```sh fence inside a `Setup`,
`Usage`, `Demo`, or `Demo flow` section of a lecture or project README is
executed literally, as one `bash -e -o pipefail` script, from the
repository root (the documented working directory for every such stanza).
A fence is expected to exit 0 unless the line immediately above it is the
annotation `<!-- fence-exit: N -->` (used by demos whose README states a
non-zero exit, e.g. lecture 06's doctor on the broken repo).

Identical fences (e.g. the projects' shared `make setup` stanza) execute
once. Fences from different READMEs run in a worker pool; fences within
one README run in order, because a Usage stanza may build on its own
earlier commands. A project's gitignored `kb-data/` learner directory is
removed before and after its README's fences so runs are deterministic.

The number of discovered fences must meet min_readme_command_fences in
tools/expected_counts.json: an empty sweep is a failure, never a pass.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COUNTS_MANIFEST = REPO_ROOT / "tools" / "expected_counts.json"
SECTIONS = {"Quick start", "Setup", "Usage", "Demo", "Demo flow"}
H2_SPLIT = re.compile(r"(?m)^## (?=\S)")
FENCE_RE = re.compile(r"(?:<!-- fence-exit: (\d+) -->\n)?```sh\n(.*?)```", re.S)


@dataclass
class Fence:
    readme: Path
    section: str
    index: int
    script: str
    expected_exit: int

    @property
    def label(self) -> str:
        rel = (
            self.readme.relative_to(REPO_ROOT)
            if self.readme.is_relative_to(REPO_ROOT)
            else self.readme
        )
        return f"{rel} [{self.section} #{self.index}]"


# The root README is the most-read file here, so its commands are executed
# like any other. A command that only a human ever ran is the defect class
# this gate exists to prevent.
def discover_fences(root: Path = REPO_ROOT) -> list[Fence]:
    root_readme = [root / "README.md"] if (root / "README.md").is_file() else []
    readmes = (
        root_readme
        + sorted(root.glob("lectures/lecture-*/README.md"))
        + sorted(root.glob("projects/project-*/README.md"))
    )
    fences = []
    for readme in readmes:
        text = readme.read_text(encoding="utf-8")
        for section in H2_SPLIT.split(text)[1:]:
            title = section.split("\n", 1)[0].strip()
            if title not in SECTIONS:
                continue
            for position, match in enumerate(FENCE_RE.finditer(section), start=1):
                expected = int(match.group(1)) if match.group(1) else 0
                fences.append(Fence(readme, title, position, match.group(2), expected))
    return fences


SHARED_STATE = re.compile(
    r"\bmake setup\b"
    r"|\bpnpm (install|add|remove|update)\b"
    r"|\bnpm (install|i|ci|add)\b"
    r"|\buv (sync|add|remove|pip)\b"
    r"|\bcorepack\b"
    r"|node_modules"
    r"|\.venv\b"
    r"|pnpm-lock\.yaml|uv\.lock|package-lock\.json"
)


# A fence that invokes a repo-wide gate would re-enter this checker and
# recurse forever. Such a command belongs in prose, not in an executed
# fence, and saying so by name beats discovering it as a hang.
RECURSIVE = re.compile(
    r"\bmake (status|verify|verify-dedup|conformance|check-fresh)\b"
    # A clone fence checks the repository out inside itself. This one is
    # not hypothetical: bringing the root README into scope ran it once,
    # and left a full copy of the repository in the working tree.
    r"|\bgit clone\b"
)


def recurses_into_the_gate(fence: Fence) -> bool:
    """True when running this fence would re-enter the gate that runs it."""
    return bool(RECURSIVE.search(fence.script))


def mutates_shared_state(fence: Fence) -> bool:
    """True when running this fence beside another could break that other one.

    Every fence in a run shares one toolchain. A fence that installs into it,
    or touches node_modules, .venv, or a lockfile, must never overlap a
    sibling: `pnpm install` tears down and recreates `node_modules/.bin/`
    while a sibling is launching `pnpm exec tsx` out of it, and the sibling
    dies with "cannot open ./node_modules/.bin/tsx: No such file". That
    failed CI once while 61 fences of the identical form passed in the same
    run, which is the signature of a race rather than a missing install.
    """
    return bool(SHARED_STATE.search(fence.script))


def run_readme_fences(readme: Path, fences: list[Fence]) -> list[str]:
    """Run one README's fences in order; returns failure messages."""
    failures = []
    kb_data = readme.parent / "kb-data"
    shutil.rmtree(kb_data, ignore_errors=True)
    try:
        for fence in fences:
            proc = subprocess.run(
                ["bash", "-e", "-o", "pipefail", "-c", fence.script],
                cwd=REPO_ROOT, capture_output=True, text=True, timeout=600,
            )
            if proc.returncode != fence.expected_exit:
                tail = (proc.stdout + proc.stderr).strip().split("\n")[-4:]
                failures.append(
                    f"{fence.label}: exit {proc.returncode} != expected "
                    f"{fence.expected_exit}\n    " + "\n    ".join(tail)
                )
    finally:
        shutil.rmtree(kb_data, ignore_errors=True)
    return failures


def main() -> int:
    fences = discover_fences()
    floor = int(
        json.loads(COUNTS_MANIFEST.read_text(encoding="utf-8"))["min_readme_command_fences"]
    )
    if len(fences) < floor:
        print(
            f"readme-commands: FAIL: discovered {len(fences)} fence(s) but "
            f"tools/expected_counts.json requires at least {floor}. "
            "Either discovery is broken or the manifest is stale."
        )
        return 1

    # Identical fences (the shared `make setup` stanza) are claimed by the
    # first README, deterministically, before any thread starts: dedup can
    # never race, and two `make setup` runs can never overlap.
    by_readme: dict[Path, list[Fence]] = {}
    claimed: set = set()
    for fence in fences:
        key = (fence.script, fence.expected_exit)
        if key in claimed:
            continue
        claimed.add(key)
        by_readme.setdefault(fence.readme, []).append(fence)

    # Two phases, because the toolchain is shared. Fences that mutate it run
    # alone, first; everything else runs in the pool afterwards. The split is
    # by classification, not by timing, so a future fence that adds an
    # installer is serialized automatically instead of failing CI at random
    # on a machine with fewer cores.
    serial: list[tuple[Path, Fence]] = []
    parallel: dict[Path, list[Fence]] = {}
    for readme, group in by_readme.items():
        for fence in group:
            if mutates_shared_state(fence):
                serial.append((readme, fence))
            else:
                parallel.setdefault(readme, []).append(fence)

    failures: list[str] = []
    for fence in fences:
        if recurses_into_the_gate(fence):
            failures.append(
                f"{fence.label}: invokes a repo-wide gate or clones the "
                f"repository, either of which re-enters or duplicates the tree "
                f"this gate runs in; move it into prose"
            )

    for readme, fence in sorted(serial, key=lambda item: item[1].label):
        failures.extend(run_readme_fences(readme, [fence]))

    # The invariant, asserted rather than assumed: nothing in the parallel
    # phase may touch what every worker shares.
    escaped = [
        fence.label
        for group in parallel.values()
        for fence in group
        if mutates_shared_state(fence)
    ]
    for label in escaped:
        failures.append(
            f"{label}: mutates shared toolchain state but was dispatched to the "
            f"parallel phase; it must run in the serial phase"
        )

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [
            pool.submit(run_readme_fences, readme, group)
            for readme, group in sorted(parallel.items())
        ]
        for future in futures:
            failures.extend(future.result())

    unique = len({(f.script, f.expected_exit) for f in fences})
    for failure in failures:
        print(f"readme-commands: FAIL {failure}")
    print(
        f"readme-commands: {len(fences)} fence(s) in {len(by_readme)} README(s), "
        f"{unique} unique, {len(serial)} serialized (shared toolchain state), "
        f"{len(failures)} failure(s)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
