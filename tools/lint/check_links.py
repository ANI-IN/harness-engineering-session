#!/usr/bin/env python3
"""Link checker.

Default mode: every relative markdown link (and image) must resolve to a real
file or directory, and heading anchors must exist in the target file.
--external additionally fetches every http(s) URL and fails on anything that
does not answer 2xx/3xx (run this before committing a lecture; it needs
network, so the default CI path skips it).
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {"node_modules", "_reference", ".git", ".venv", "__pycache__", "dist"}
SKIP_FILES = {"RESEARCH.md", "PROPOSAL.md", "BUILD_PROGRESS.md"}

LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)
CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def markdown_files() -> list[Path]:
    files = []
    for path in REPO_ROOT.rglob("*.md"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SKIP_FILES and path.parent == REPO_ROOT:
            continue
        files.append(path)
    return sorted(files)


def github_slug(heading: str) -> str:
    """GitHub's anchor slug rules: lowercase, strip punctuation, spaces to dashes."""
    heading = re.sub(r"`([^`]*)`", r"\1", heading).strip()
    heading = heading.lower()
    heading = re.sub(r"[^\w\- ]", "", heading, flags=re.UNICODE)
    return heading.replace(" ", "-")


def anchors_in(path: Path) -> set[str]:
    text = CODE_FENCE_RE.sub("", path.read_text(encoding="utf-8"))
    slugs: dict[str, int] = {}
    result = set()
    for match in HEADING_RE.finditer(text):
        slug = github_slug(match.group(1))
        count = slugs.get(slug, 0)
        result.add(slug if count == 0 else f"{slug}-{count}")
        slugs[slug] = count + 1
    return result


def check_relative(files: list[Path]) -> list[str]:
    errors = []
    for md in files:
        text = CODE_FENCE_RE.sub("", md.read_text(encoding="utf-8"))
        for match in LINK_RE.finditer(text):
            target = match.group(1)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            raw_path, _, anchor = target.partition("#")
            if not raw_path:  # same-file anchor
                if anchor and anchor not in anchors_in(md):
                    errors.append(f"{md.relative_to(REPO_ROOT)}: missing anchor #{anchor}")
                continue
            resolved = (md.parent / raw_path).resolve()
            if not resolved.exists():
                errors.append(f"{md.relative_to(REPO_ROOT)}: broken link {target}")
                continue
            if anchor:
                anchor_target = resolved / "README.md" if resolved.is_dir() else resolved
                if (
                    anchor_target.suffix == ".md"
                    and anchor_target.is_file()
                    and anchor not in anchors_in(anchor_target)
                ):
                    errors.append(f"{md.relative_to(REPO_ROOT)}: missing anchor {target}")
    return errors


def external_urls(files: list[Path]) -> dict[str, list[Path]]:
    found: dict[str, list[Path]] = {}
    for md in files:
        text = CODE_FENCE_RE.sub("", md.read_text(encoding="utf-8"))
        for match in LINK_RE.finditer(text):
            target = match.group(1)
            if target.startswith(("http://", "https://")):
                found.setdefault(target.rstrip(").,"), []).append(md)
    return found


def fetch_status(url: str) -> int | str:
    request = urllib.request.Request(
        url, method="GET", headers={"User-Agent": "harness-course-linkcheck/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except Exception as error:  # noqa: BLE001 — report, don't crash the sweep
        return type(error).__name__


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external", action="store_true", help="also fetch http(s) URLs")
    args = parser.parse_args()

    files = markdown_files()
    errors = check_relative(files)
    print(f"lint-links: {len(files)} markdown files scanned (relative links + anchors)")

    if args.external:
        urls = external_urls(files)
        print(f"lint-links: fetching {len(urls)} external URL(s)")
        for url in sorted(urls):
            status = fetch_status(url)
            ok = isinstance(status, int) and 200 <= status < 400
            print(f"  [{status}] {url}")
            if not ok:
                sources = ", ".join(str(p.relative_to(REPO_ROOT)) for p in urls[url])
                errors.append(f"external URL failed ({status}): {url} (in {sources})")

    for error in errors:
        print(f"  FAIL {error}")
    if errors:
        print(f"lint-links: {len(errors)} error(s)")
        return 1
    print("lint-links: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
