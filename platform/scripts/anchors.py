"""Walkthrough anchors: code shown in class is marked `[walkthrough:<id>] start` / `end`.

Usage:
  python platform/scripts/anchors.py list
  python platform/scripts/anchors.py extract S3:policy
  python platform/scripts/anchors.py check [--root DIR]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
SCAN_DIRS = (
    "platform/src",
    "platform/teamtrack",
    "platform/sandbox",
    "use-in-your-repo/skills",
    "section-1-instructions",
    "section-2-state-lifecycle",
    "section-3-scope-sandbox",
    "section-4-verification",
    "final-project",
)
SUFFIXES = {".py", ".md", ".html", ".sh", ".toml", ".json", ".yml", ".yaml", ""}
SKIP_PARTS = {".venv", "__pycache__", ".git", "node_modules", ".pytest_cache"}
MAX_LINES = 40
MARKER = re.compile(r"\[walkthrough:([A-Za-z0-9]+:[A-Za-z0-9_]+)\]\s+(start|end)")


@dataclass
class Anchor:
    anchor_id: str
    path: Path
    start: int  # 1-based line of the start marker
    end: int | None  # 1-based line of the end marker


def _files(root: Path) -> list[Path]:
    files: list[Path] = []
    for folder in SCAN_DIRS:
        base = root / folder
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in SUFFIXES and not SKIP_PARTS & set(path.parts):
                files.append(path)
    return sorted(files)


def collect(root: Path) -> tuple[list[Anchor], list[str]]:
    anchors: list[Anchor] = []
    problems: list[str] = []
    for path in _files(root):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        open_anchors: dict[str, Anchor] = {}
        for number, line in enumerate(lines, start=1):
            match = MARKER.search(line)
            if not match:
                continue
            anchor_id, kind = match.groups()
            if kind == "start":
                if anchor_id in open_anchors:
                    problems.append(f"{anchor_id}: started twice in {path}")
                open_anchors[anchor_id] = Anchor(anchor_id, path, number, None)
            elif anchor_id not in open_anchors:
                problems.append(f"{anchor_id}: end without start in {path}:{number}")
            else:
                anchor = open_anchors.pop(anchor_id)
                anchor.end = number
                anchors.append(anchor)
        for anchor in open_anchors.values():
            problems.append(f"{anchor.anchor_id}: start without end in {path}:{anchor.start}")
    seen: dict[str, Anchor] = {}
    for anchor in anchors:
        if anchor.anchor_id in seen:
            problems.append(
                f"{anchor.anchor_id}: defined in {seen[anchor.anchor_id].path} and {anchor.path}"
            )
        seen[anchor.anchor_id] = anchor
        assert anchor.end is not None
        length = anchor.end - anchor.start - 1
        if length > MAX_LINES:
            problems.append(
                f"{anchor.anchor_id}: {length} lines (max {MAX_LINES}) in {anchor.path}"
            )
    return anchors, problems


def extract(root: Path, anchor_id: str) -> str:
    for anchor in collect(root)[0]:
        if anchor.anchor_id == anchor_id and anchor.end is not None:
            lines = anchor.path.read_text(encoding="utf-8").splitlines()
            return "\n".join(lines[anchor.start : anchor.end - 1])
    raise KeyError(anchor_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["list", "extract", "check"])
    parser.add_argument("anchor_id", nargs="?")
    parser.add_argument("--root", type=Path, default=REPO)
    args = parser.parse_args(argv)
    if args.command == "extract":
        try:
            print(extract(args.root, args.anchor_id or ""))
        except KeyError:
            print(f"no anchor named {args.anchor_id!r}", file=sys.stderr)
            return 1
        return 0
    anchors, problems = collect(args.root)
    if args.command == "list":
        for anchor in anchors:
            rel = anchor.path.relative_to(args.root).as_posix()
            print(f"{anchor.anchor_id:<24} {rel}:{anchor.start}-{anchor.end}")
        return 0
    for problem in problems:
        print(f"x {problem}")
    print(f"{len(anchors)} anchors, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
