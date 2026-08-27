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
import datetime as dt
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# fixtures/ and expected/ are unit test DATA, not documentation: a fixture
# may deliberately contain a broken link for a checker to catch (a seeded
# defect), and its relative paths resolve against the unit's temp working
# copy, not the repository tree.
SKIP_DIRS = {
    "node_modules", "_reference", ".git", ".venv", "__pycache__", "dist",
    "fixtures", "expected",
}
SKIP_FILES = {"RESEARCH.md", "PROPOSAL.md", "BUILD_PROGRESS.md"}

LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)
CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def markdown_files(root: Path = REPO_ROOT) -> list[Path]:
    files = []
    for path in root.rglob("*.md"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SKIP_FILES and path.parent == root:
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


def _rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)


def check_relative(files: list[Path], root: Path = REPO_ROOT) -> list[str]:
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
                    errors.append(f"{_rel(md, root)}: missing anchor #{anchor}")
                continue
            resolved = (md.parent / raw_path).resolve()
            if not resolved.exists():
                errors.append(f"{_rel(md, root)}: broken link {target}")
                continue
            if anchor:
                anchor_target = resolved / "README.md" if resolved.is_dir() else resolved
                if (
                    anchor_target.suffix == ".md"
                    and anchor_target.is_file()
                    and anchor not in anchors_in(anchor_target)
                ):
                    errors.append(f"{_rel(md, root)}: missing anchor {target}")
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
    except Exception as error:  # noqa: BLE001 -- report, don't crash the sweep
        return type(error).__name__


RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2.0


def fetch_with_retries(url: str) -> tuple[int | str, int]:
    """Fetch up to RETRY_ATTEMPTS times; return (last_status, attempts_used).

    Returns early on the first success, so an exception entry is only ever
    consulted after every attempt failed; an intermittent block clears
    itself, and a permanent skip never hides a genuinely dead link.
    """
    status: int | str = "unfetched"
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        status = fetch_status(url)
        if isinstance(status, int) and 200 <= status < 400:
            return status, attempt
        if attempt < RETRY_ATTEMPTS:
            time.sleep(RETRY_DELAY_SECONDS)
    return status, RETRY_ATTEMPTS


EXCEPTION_MAX_AGE_DAYS = 30
REQUIRED_EXCEPTION_FIELDS = ("expect", "reason", "added", "removal_trigger")


def load_exceptions() -> dict:
    path = Path(__file__).parent / "link_exceptions.json"
    return json.loads(path.read_text(encoding="utf-8"))["exceptions"]


def check_exception_hygiene(exceptions: dict, today: dt.date) -> list[str]:
    """No-network gates: entry shape and the 30-day age limit."""
    errors = []
    for url, entry in exceptions.items():
        missing = [field for field in REQUIRED_EXCEPTION_FIELDS if field not in entry]
        if missing:
            errors.append(
                f"link exception {url}: missing field(s) {', '.join(missing)} "
                "(see link_exceptions.json comment for the required shape)"
            )
            continue
        added = dt.date.fromisoformat(entry["added"])
        age = (today - added).days
        if age > EXCEPTION_MAX_AGE_DAYS:
            errors.append(
                f"link exception {url}: {age} days old (limit {EXCEPTION_MAX_AGE_DAYS}); "
                "re-verify the condition and update 'added', or remove the entry"
            )
    return errors


def repo_is_public(repo: str) -> bool | str:
    """Anonymous probe: 200 = public, 404 = private/missing, else unknown."""
    status = fetch_status(f"https://api.github.com/repos/{repo}")
    if status == 200:
        return True
    if status == 404:
        return False
    return f"probe inconclusive ({status})"


def check_removal_triggers(exceptions: dict) -> list[str]:
    """Network gates: fail when a machine-checkable trigger condition holds."""
    errors = []
    probed: dict[str, bool | str] = {}
    for url, entry in exceptions.items():
        trigger = entry.get("removal_trigger", {})
        if trigger.get("type") != "repo_public":
            continue
        repo = trigger["repo"]
        if repo not in probed:
            probed[repo] = repo_is_public(repo)
        result = probed[repo]
        if result is True:
            errors.append(
                f"link exception {url}: repo {repo} is now PUBLIC but the exception "
                "is still present; remove it (its 404 justification no longer holds)"
            )
        elif result is not False:
            print(f"  note: removal-trigger probe for {repo}: {result}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external", action="store_true", help="also fetch http(s) URLs")
    args = parser.parse_args()

    files = markdown_files()
    errors = check_relative(files, REPO_ROOT)
    print(f"lint-links: {len(files)} markdown files scanned (relative links + anchors)")

    exceptions = load_exceptions()
    errors.extend(check_exception_hygiene(exceptions, dt.date.today()))

    if args.external:
        urls = external_urls(files)
        print(f"lint-links: fetching {len(urls)} external URL(s) "
              f"(up to {RETRY_ATTEMPTS} attempts each)")
        for url in sorted(urls):
            status, attempts = fetch_with_retries(url)
            ok = isinstance(status, int) and 200 <= status < 400
            exception = exceptions.get(url)
            if not ok and exception and status == exception["expect"]:
                print(f"  [{status}*] {url} (excused after {attempts} attempts per "
                      f"link_exceptions.json, added {exception['added']})")
                continue
            suffix = "" if attempts == 1 else f" (attempt {attempts})"
            print(f"  [{status}] {url}{suffix}")
            if not ok:
                sources = ", ".join(str(p.relative_to(REPO_ROOT)) for p in urls[url])
                errors.append(f"external URL failed ({status}): {url} (in {sources})")
        errors.extend(check_removal_triggers(exceptions))

    for error in errors:
        print(f"  FAIL {error}")
    if errors:
        print(f"lint-links: {len(errors)} error(s)")
        return 1
    print("lint-links: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
