"""Docs checker for assignment A1: broken links and rule coverage (reference solution).

Usage (from the repository root):

    uv run python section-1-instructions/assignment/solution/work/checker/check_docs.py \
        --original section-1-instructions/assignment/starter/original/AGENTS.md \
        --tree section-1-instructions/assignment/solution/work/instructions \
        --product teamtrack

Output: one line per problem, `ERROR <kind> <key> [<detail>]`, then one summary line:
`OK: <files> files, <links> links, <rules> rules covered` (exit 0) or `FAILED: <n> problems`
(exit 1). A missing --original or --tree path prints `ERROR usage <reason>` and exits 2.

The full specification (kinds, keys, slug rules, statement rules, overlap) is in the assignment
README, section "Detailed requirements". The error lines say what to fix, so an agent that runs
this checker can act on them directly (A1, F-a-97).
"""

from __future__ import annotations

import argparse
import posixpath
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

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

_FENCE = re.compile(r"^\s*(```|~~~)")
_CODE_SPAN = re.compile(r"(`+)(.+?)\1")
_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]*)\)")
_REF_DEF = re.compile(r"^\s{0,3}\[([^\]^][^\]]*)\]:\s*(\S+)")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_PATH_SPAN = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*/?")
_BLOCK_START = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s|#|\||```|~~~)")


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


def _unfenced(lines: list[str]) -> list[bool]:
    """For each line, True when it is outside fenced code blocks (fence lines count as fenced)."""
    keep: list[bool] = []
    fence: str | None = None
    for line in lines:
        match = _FENCE.match(line)
        if fence is None and match:
            fence = match.group(1)
            keep.append(False)
        elif fence is not None:
            if line.strip().startswith(fence):
                fence = None
            keep.append(False)
        else:
            keep.append(True)
    return keep


def _blank_code(line: str) -> str:
    """The line with inline code spans replaced by spaces (positions stay the same)."""
    return _CODE_SPAN.sub(lambda m: " " * len(m.group(0)), line)


def _text_lines(text: str) -> Iterator[tuple[int, str]]:
    lines = text.splitlines()
    for number, (line, keep) in enumerate(zip(lines, _unfenced(lines), strict=True), start=1):
        if keep:
            yield number, line


def slugify(heading: str) -> str:
    """GitHub-style anchor for a heading text (without the leading #s)."""
    text = heading.strip().lower().replace("`", "").replace("*", "")
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def content_words(text: str) -> set[str]:
    """The content words of a statement: the basis of the overlap measure."""
    text = REFERENCE.sub(" ", text).lower()
    tokens = re.split(r"[^a-z0-9_]+", text)
    return {t for t in tokens if len(t) >= 2 and t not in STOPWORDS}


def overlap(original: str, new: str) -> float:
    """Share of the original statement's content words that the new statement keeps."""
    words = content_words(original)
    if not words:
        return 1.0
    return len(words & content_words(new)) / len(words)


def parse_definitions(text: str) -> list[Definition]:
    """Every definition tag outside fenced code blocks, in file order."""
    lines = text.splitlines()
    keep = _unfenced(lines)
    found: list[Definition] = []
    for index, line in enumerate(lines):
        if not keep[index]:
            continue
        tags = list(DEFINITION.finditer(_blank_code(line)))
        for position, tag in enumerate(tags):
            last = position == len(tags) - 1
            end = len(line) if last else tags[position + 1].start()
            parts = [line[tag.end() : end].strip()]
            if last:
                parts += _continuation(lines, keep, index + 1)
            statement = " ".join(p for p in parts if p)
            found.append(
                Definition(
                    rule_id=tag.group(1),
                    line=index + 1,
                    statement=statement,
                    retired=statement.lower().startswith("(retired"),
                )
            )
    return found


def _continuation(lines: list[str], keep: list[bool], start: int) -> list[str]:
    parts: list[str] = []
    for index in range(start, len(lines)):
        line = lines[index]
        if not keep[index] or not line.strip() or _BLOCK_START.match(line):
            break
        if DEFINITION.search(_blank_code(line)):
            break
        parts.append(line.strip())
    return parts


# -- links ----------------------------------------------------------------------------------------


def _md_files(tree: Path) -> list[tuple[str, Path]]:
    files = [(p.relative_to(tree).as_posix(), p) for p in tree.rglob("*.md") if p.is_file()]
    return sorted(files)


def _headings(path: Path) -> set[str]:
    seen: dict[str, int] = {}
    slugs: set[str] = set()
    for _, line in _text_lines(path.read_text(encoding="utf-8")):
        match = _HEADING.match(line)
        if not match:
            continue
        slug = slugify(match.group(1))
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        slugs.add(slug if count == 0 else f"{slug}-{count}")
    return slugs


def _locate(rel: str, tree: Path, product: Path) -> Path | None:
    """The workspace overlay: the tree first, then the same relative path in the product."""
    for base in (tree, product):
        candidate = base / rel
        if candidate.exists():
            return candidate
    return None


def _link_targets(text: str) -> Iterator[tuple[int, str]]:
    for number, line in _text_lines(text):
        visible = _blank_code(line)
        for match in _LINK.finditer(visible):
            yield number, line[match.start(1) : match.end(1)]
        ref = _REF_DEF.match(visible)
        if ref:
            yield number, ref.group(2)


def _clean_target(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("<"):
        return raw[1:].split(">", 1)[0]
    return raw.split()[0] if raw.split() else ""


def _check_link(rel_file: str, number: int, raw: str, tree: Path, product: Path) -> Problem | None:
    target = _clean_target(raw)
    if not target or _SCHEME.match(target):
        return None
    key = f"{rel_file}:{number}"
    if target.startswith("/"):
        return Problem("broken-link", key, target)
    path_part, _, anchor = target.partition("#")
    path_part = unquote(path_part)
    if path_part:
        rel = posixpath.normpath(posixpath.join(posixpath.dirname(rel_file), path_part))
        if rel == ".." or rel.startswith("../"):
            return Problem("broken-link", key, target)
        found = _locate(rel, tree, product)
        if found is None:
            return Problem("broken-link", key, target)
    else:
        found = tree / rel_file
    if anchor and found.is_file() and found.suffix == ".md" and anchor not in _headings(found):
        return Problem("broken-anchor", key, target)
    return None


def _path_spans(text: str) -> Iterator[tuple[int, str]]:
    for number, line in _text_lines(text):
        for match in _CODE_SPAN.finditer(line):
            span = match.group(2).strip()
            if span.startswith("/") or not _PATH_SPAN.fullmatch(span):
                continue
            if "/" in span or span.endswith(PATH_EXTENSIONS):
                yield number, span


def _span_exists(rel_file: str, span: str, tree: Path, product: Path) -> bool:
    folder = posixpath.dirname(rel_file)
    for rel in (span, posixpath.join(folder, span)):
        norm = posixpath.normpath(rel)
        if norm == ".." or norm.startswith("../"):
            continue
        found = _locate(norm, tree, product)
        if found is not None and (not span.endswith("/") or found.is_dir()):
            return True
    return False


def check_links(tree: Path, product: Path) -> list[Problem]:
    """broken-link, broken-anchor, and broken-path problems in every .md file under tree."""
    problems: list[Problem] = []
    for rel_file, path in _md_files(tree):
        text = path.read_text(encoding="utf-8")
        for number, raw in _link_targets(text):
            problem = _check_link(rel_file, number, raw, tree, product)
            if problem is not None:
                problems.append(problem)
        for number, span in _path_spans(text):
            if not _span_exists(rel_file, span, tree, product):
                problems.append(Problem("broken-path", f"{rel_file}:{number}", span))
    return problems


def count_links(tree: Path) -> int:
    """Local links and code-span paths checked (for the summary line)."""
    total = 0
    for _, path in _md_files(tree):
        text = path.read_text(encoding="utf-8")
        total += sum(1 for _, raw in _link_targets(text) if not _SCHEME.match(_clean_target(raw)))
        total += sum(1 for _ in _path_spans(text))
    return total


# -- rules ----------------------------------------------------------------------------------------


def _references(text: str) -> Iterator[tuple[int, str]]:
    for number, line in _text_lines(text):
        tags = [m.span() for m in DEFINITION.finditer(_blank_code(line))]
        for match in REFERENCE.finditer(line):
            if not any(start <= match.start() < end for start, end in tags):
                yield number, match.group(1)


def check_rules(original: Path, tree: Path) -> list[Problem]:
    """missing-rule, weak-rule, duplicate-rule, retired-rule, unknown-rule, rule-in-map."""
    source = parse_definitions(original.read_text(encoding="utf-8"))
    known = {d.rule_id for d in source}
    retired = {d.rule_id for d in source if d.retired}
    active: dict[str, Definition] = {}
    for d in source:
        if not d.retired:
            active.setdefault(d.rule_id, d)
    families = {rule_id.split(".")[0] for rule_id in known if rule_id.startswith("R")}

    problems: list[Problem] = []
    first: dict[str, tuple[str, Definition]] = {}
    for rel_file, path in _md_files(tree):
        text = path.read_text(encoding="utf-8")
        for d in parse_definitions(text):
            where = f"{rel_file}:{d.line}"
            if d.rule_id not in known:
                problems.append(Problem("unknown-rule", d.rule_id, where))
                continue
            if d.rule_id in retired:
                problems.append(Problem("retired-rule", d.rule_id, where))
                continue
            if rel_file == "AGENTS.md":
                problems.append(Problem("rule-in-map", d.rule_id, where))
            if d.rule_id in first:
                problems.append(Problem("duplicate-rule", d.rule_id, where))
            else:
                first[d.rule_id] = (rel_file, d)
        for number, rule_id in _references(text):
            if "." in rule_id or rule_id.startswith("CV-"):
                unknown = rule_id not in known
            else:
                unknown = rule_id not in families
            if unknown:
                problems.append(Problem("unknown-rule", rule_id, f"{rel_file}:{number}"))

    for rule_id, wanted in active.items():
        if rule_id not in first:
            problems.append(Problem("missing-rule", rule_id))
            continue
        rel_file, found = first[rule_id]
        share = overlap(wanted.statement, found.statement)
        if share < OVERLAP_THRESHOLD:
            problems.append(
                Problem("weak-rule", rule_id, f"{rel_file}:{found.line} overlap={share:.2f}")
            )
    return problems


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
