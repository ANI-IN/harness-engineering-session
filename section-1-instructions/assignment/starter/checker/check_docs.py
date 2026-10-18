"""Docs checker for assignment A1: broken links and rule coverage.

Usage (from the repository root):

    uv run python section-1-instructions/assignment/starter/checker/check_docs.py \
        --original section-1-instructions/assignment/starter/original/AGENTS.md \
        --tree section-1-instructions/assignment/starter/instructions \
        --product teamtrack

Output: one line per problem, `ERROR <kind> <key> [<detail>]`, then one summary line:
`OK: <files> files, <links> links, <rules> rules covered` (exit 0) or `FAILED: <n> problems`
(exit 1). A missing --original or --tree path prints `ERROR usage <reason>` and exits 2.

The full specification (kinds, keys, slug rules, statement rules, overlap) is in the assignment
README, section "Detailed requirements". Keep the function names and signatures below: the visible
tests import them, and the grader runs this file as a command.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# A definition tag such as [R1.2] or [CV-07] (not followed by "(" or "[", which would make it a
# link). A reference is any other occurrence of an id: R1.2, the family R1, or CV-07.
RULE_ID = r"(?:R[1-9]\.\d+|CV-\d{2})"
DEFINITION = re.compile(r"\[(" + RULE_ID + r")\](?![(\[])")
REFERENCE = re.compile(r"(?<![\w.])(R[1-9](?:\.\d+)?|CV-\d{2})(?!\w)")

OVERLAP_THRESHOLD = 0.5
PATH_EXTENSIONS = (".md", ".txt", ".py", ".toml", ".ini", ".json", ".sh", ".html", ".css")

# Words that carry no rule content. Use this list exactly: the grader's reference uses it too.
_STOPWORD_TEXT = """
    a an and are as at be been but by can do does for from has have if in into is it its may
    must of on or our so than that the their then there these this those to was we were what
    when where which who will with you your also one more most other same such very should
    would could here use
"""
STOPWORDS = frozenset(_STOPWORD_TEXT.split())


@dataclass(frozen=True)
class Problem:
    kind: str  # broken-link, broken-anchor, broken-path, missing-rule, weak-rule, ...
    key: str  # "file:line" for link kinds, the rule id for rule kinds
    detail: str = ""

    def __str__(self) -> str:
        return f"ERROR {self.kind} {self.key}" + (f" {self.detail}" if self.detail else "")


@dataclass(frozen=True)
class Definition:
    rule_id: str
    line: int  # 1-based line of the tag
    statement: str  # text after the tag, plus its continuation lines
    retired: bool  # the statement starts with "(retired"


# -- text helpers ---------------------------------------------------------------------------------


def slugify(heading: str) -> str:
    """GitHub-style anchor for a heading text (without the leading #s)."""
    # TODO(A1-3): trim surrounding whitespace; lowercase; remove backticks and asterisks; drop every
    # character that is not a letter, digit, space, hyphen, or underscore; turn each space into a
    # hyphen. The -1, -2, ... suffix of a repeated heading is added where you collect a file's
    # anchors (check_links), not here.
    return ""


def content_words(text: str) -> set[str]:
    """The content words of a statement: the basis of the overlap measure."""
    # TODO(A1-4): remove rule ids, lowercase, split on every character outside [a-z0-9_], drop
    # STOPWORDS and tokens shorter than two characters.
    return set()


def overlap(original: str, new: str) -> float:
    """Share of the original statement's content words that the new statement keeps."""
    # TODO(A1-4): |words(original) & words(new)| / |words(original)|; 1.0 when the original has
    # no content words.
    return 0.0


def parse_definitions(text: str) -> list[Definition]:
    """Every definition tag outside fenced code blocks, in file order."""
    # TODO(A1-4): find each [ID] tag; collect its statement (rest of the line up to the next tag,
    # plus continuation lines as the README describes); set retired.
    return []


# -- checks ---------------------------------------------------------------------------------------


def check_links(tree: Path, product: Path) -> list[Problem]:
    """broken-link, broken-anchor, and broken-path problems in every .md file under tree."""
    # TODO(A1-3): Markdown links and images, reference-style definitions, anchors, code-span
    # paths; resolve against the tree first, then the same relative path under product.
    return []


def check_rules(original: Path, tree: Path) -> list[Problem]:
    """missing-rule, weak-rule, duplicate-rule, retired-rule, unknown-rule, rule-in-map."""
    # TODO(A1-4): compare the definitions in original with the definitions and references in
    # every .md file under tree.
    return []


def count_links(tree: Path) -> int:
    """Local links and code-span paths checked (for the summary line)."""
    # TODO(A1-3): the number of local link targets (Markdown links, images, and reference
    # definitions, leaving out targets with a scheme such as https:) plus the number of path-like
    # code spans, summed over every .md file under tree: the items check_links checks.
    return 0


# -- command line ---------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--product", type=Path, default=Path("platform/teamtrack"))
    args = parser.parse_args(argv)
    for name in ("original", "tree"):
        path: Path = getattr(args, name)
        if not path.exists():
            print(f"ERROR usage --{name} not found: {path}")
            return 2
    problems = check_links(args.tree, args.product) + check_rules(args.original, args.tree)
    for problem in problems:
        print(problem)
    if problems:
        print(f"FAILED: {len(problems)} problems")
        return 1
    files = len(list(args.tree.rglob("*.md")))
    definitions = parse_definitions(args.original.read_text(encoding="utf-8"))
    covered = sum(1 for d in definitions if not d.retired)
    print(f"OK: {files} files, {count_links(args.tree)} links, {covered} rules covered")
    return 0


if __name__ == "__main__":
    sys.exit(main())
