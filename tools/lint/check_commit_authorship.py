"""Commit authorship: no co-author trailers, no tool attributions.

CONTRIBUTING.md, "Commit style": *No co-author trailers or tool
attributions.* Until this gate existed the rule was enforced by memory,
and three commits shipped a `Co-Authored-By:` trailer without any gate
noticing.

The defect that let it through is worth stating, because it is the one
this module teaches against: the obvious check reads `%an` and `%cn`,
the author and committer fields. A trailer does not live there. It lives
in the commit *body*, so a check over the identity fields reports green
while the trailer sits one field away, untouched. This gate reads the
full raw body of every commit in range, which is the only place the
thing it forbids can appear.

Range: `main..HEAD` by default, so a branch is checked against the
history it will be merged into and existing history is not re-litigated.
`--all` checks every commit reachable from every ref, which is what a
one-off audit wants.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Trailers that attribute the commit to a second party.
TRAILER = re.compile(r"^[ \t]*co-authored-by[ \t]*:.*$", re.IGNORECASE | re.MULTILINE)

# Tool attributions. These are matched as whole words against the body,
# then filtered by ALLOWED below, because the module legitimately names
# `CLAUDE.md`, `claude-progress.md`, and cites Anthropic and OpenAI posts
# as primary sources. A citation is not an attribution.
ATTRIBUTION = re.compile(
    r"(generated\s+with|written\s+by|authored\s+by|created\s+by|"
    r"with\s+help\s+from|on\s+behalf\s+of)\s+[^\n]*"
    r"(claude|anthropic|openai|gpt|copilot|cursor|codex|gemini|llm|ai\b)",
    re.IGNORECASE,
)

# Substrings whose presence makes a `claude`/`openai` hit legitimate.
ALLOWED = (
    "claude.md",
    "claude-progress.md",
    "claude-code",
    "openai.com",
    "anthropic.com",
)


def _rev_exists(rev: str) -> bool:
    return subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", rev],
        cwd=REPO_ROOT, capture_output=True, text=True,
    ).returncode == 0


def resolve_range(rev_range: str) -> str:
    """`main..HEAD` needs a `main`. CI checks out a detached PR merge ref, so
    the local branch may not exist; `origin/main` usually does.

    Two ways this range can degenerate, and neither may report green:

    1. No base ref resolves. Widen to `--all` rather than fail open.
    2. The base resolves but the range is *empty*, which is the normal state
       on `main` itself, where `main..HEAD` selects nothing. A gate that
       checks zero commits and prints OK is the failure this whole file
       exists to prevent, so an empty range also widens to `--all`.
    """
    if rev_range != "main..HEAD":
        return rev_range
    for base in ("main", "origin/main"):
        if _rev_exists(base):
            candidate = f"{base}..HEAD"
            if commit_list(candidate):
                return candidate
            return "--all"
    return "--all"


def commit_list(rev_range: str) -> list[str]:
    args = ["git", "rev-list"]
    args += ["--all"] if rev_range == "--all" else [rev_range]
    out = subprocess.run(
        args, cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [line for line in out.split("\n") if line]


def bodies(rev_range: str) -> list[tuple[str, str]]:
    """Every (sha, full body) in range, in one git call.

    `%B` is the whole message: subject, body, and every trailer line. The
    identity fields `%an`/`%cn` are deliberately not what is scanned; a
    co-author trailer is invisible there, which is how three of them shipped.
    """
    args = ["git", "log", "-z", "--format=%H%n%B"]
    args += ["--all"] if rev_range == "--all" else [rev_range]
    out = subprocess.run(
        args, cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout
    records = []
    for chunk in out.split("\0"):
        if not chunk.strip():
            continue
        sha, _, body = chunk.partition("\n")
        records.append((sha.strip(), body))
    return records


def identity(sha: str) -> tuple[str, str]:
    out = subprocess.run(
        ["git", "log", "-1", "--format=%an|%ae|%cn|%ce", sha],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip().split("|")
    return f"{out[0]} <{out[1]}>", f"{out[2]} <{out[3]}>"


def check_commit(sha: str, body: str) -> list[str]:
    errors = []
    short = sha[:8]
    subject = body.split("\n", 1)[0]
    for match in TRAILER.finditer(body):
        line = match.group(0).strip()
        errors.append(
            f"{short} ({subject}): co-author trailer in the commit body: "
            f"{line!r}; CONTRIBUTING.md forbids co-author trailers"
        )
    for match in ATTRIBUTION.finditer(body):
        hit = match.group(0).strip()
        if any(allowed in hit.lower() for allowed in ALLOWED):
            continue
        errors.append(
            f"{short} ({subject}): tool attribution in the commit body: "
            f"{hit!r}; CONTRIBUTING.md forbids tool attributions"
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--range", default="main..HEAD",
        help="commit range to check (default: main..HEAD), or --all",
    )
    parser.add_argument(
        "--all", action="store_const", const="--all", dest="range",
        help="check every commit reachable from every ref",
    )
    args = parser.parse_args()

    rev_range = resolve_range(args.range)
    try:
        shas = commit_list(rev_range)
    except subprocess.CalledProcessError as error:
        print(f"lint-authorship: cannot read {rev_range}: {error}")
        return 1

    if not shas:
        print(
            f"lint-authorship: {rev_range} selected no commits; refusing to "
            f"report green on an empty range"
        )
        return 1

    errors: list[str] = []
    for sha, body in bodies(rev_range):
        errors.extend(check_commit(sha, body))

    print(
        f"lint-authorship: {len(shas)} commit(s) in {rev_range}, "
        f"author, committer and full body checked"
    )
    if shas:
        author, committer = identity(shas[0])
        print(f"  tip author:    {author}")
        print(f"  tip committer: {committer}")
    for error in errors:
        print(f"  FAIL {error}")
    if errors:
        print(f"lint-authorship: {len(errors)} error(s)")
        return 1
    print("lint-authorship: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
