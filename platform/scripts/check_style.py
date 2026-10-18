"""Style check for the public course pages: the rules of docs/STYLE.md that a machine can check.

Usage:
    uv run python platform/scripts/check_style.py [PATH ...]   # default: every public course page
    uv run python platform/scripts/check_style.py --list-checks
    uv run python platform/scripts/check_style.py --strict      # warnings fail the run too
    uv run python platform/scripts/check_style.py --warn-only   # report everything, always exit 0

PATH may be a file or a folder (walked for *.md), relative to the repository root or absolute. A
file that is not a public course page is skipped, so private files never fail the check. The
default run also reads the scripts and other text files of the skills and kit templates (copied
into learners' repositories) for the id checks SC08, SC09, and SC21.

Output: one line per problem, `x <path>:<line>: SCnn <message>` for an error and `! ...` for a
warning, then `<files> files checked, <errors> errors, <warnings> warnings, <n> allowed lines`.
A line ending with `<!-- check-style: allow SCnn <reason> -->` skips check SCnn on that line; the
reason is required.

Exit code: 1 when there is an error (with --strict, an error or a warning), 2 when a PATH does not
exist, else 0. With --warn-only the exit code is 0 unless a PATH does not exist.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())

ERROR = "error"
WARNING = "warning"

# id -> (name, severity). A check marked "error" can still report some cases as warnings (SC12
# long cells, SC13 missing or misplaced note); the severity here is its main rule.
CHECKS: dict[str, tuple[str, str]] = {
    "SC00": ("Allow marker without a reason", ERROR),
    "SC01": ("Leftover markers: TODO, TBD, FIXME, XXX, [[PENDING, [[CAPTURE, {{...}}", ERROR),
    "SC02": ("Empty value placeholders, such as 'captured on , run ;'", ERROR),
    "SC03": ("Angle-bracket leftovers and placeholder clone URLs", ERROR),
    "SC04": ("Empty or unclosed fenced code block", ERROR),
    "SC05": ("Fenced code block whose only content is comments", ERROR),
    "SC06": ("Image file missing, empty, or remote", ERROR),
    "SC07": ("Image without a caption line", ERROR),
    "SC08": ("Run ids outside the evidence pages (docs/evidence.md, docs/evidence/)", ERROR),
    "SC09": ("Finding ids outside the evidence pages", ERROR),
    "SC10": ("Commit hashes outside the evidence pages", ERROR),
    "SC11": ("Length limits per document type", WARNING),
    "SC12": ("Tables wider than 4 columns (long cells: warning)", ERROR),
    "SC13": ("More than one 'your output will differ' note (missing or misplaced: warning)", ERROR),
    "SC14": ("Banned internal phrases", ERROR),
    "SC15": ("Module 1 title on the first heading, one H1 per page", ERROR),
    "SC16": ("Template headings and required lines", WARNING),
    "SC17": ("Illustrative scenario label", WARNING),
    "SC18": ("Glossary box: at most one, no repeated term", WARNING),
    "SC19": ("Section and final-project folders hold every required file", ERROR),
    "SC20": ("Every diagram (.png, .svg in a diagrams/ folder) has its .excalidraw source", ERROR),
    "SC21": (
        "Bare codes in prose: F1-F7, R1-R8, S1-S4, A1-A4, source ids A1-A7 and B1-B14",
        ERROR,
    ),
    "SC22": (
        "First mention of a Feature, House rule, Section, Assignment, or Filter "
        "without its full '<Kind> N: <name>'",
        ERROR,
    ),  # fmt: skip
    "SC23": (
        "A source mentioned without a link to it, or a 'Source N' with no list entry",
        ERROR,
    ),  # fmt: skip
    "SC24": ("Empty links, '[link]' placeholders, and malformed link URLs", ERROR),
    "SC25": ("Sources list at the end: 'Source N: title, link, author, date', in order", ERROR),
    "SC26": ("Image alt text empty, only a file name, or a bare word such as 'image'", ERROR),
    "SC30": ("Relative link to a missing file, folder, or heading (images: SC06)", ERROR),
}

# The owner's names (docs/STYLE.md rule 5; the same as shipharness.datasets.names, which a test
# keeps equal). The first mention of each on a page is "<Kind> N: <name>", later ones "<Kind> N".
NAMES: dict[str, dict[int, str]] = {
    "Feature": {
        1: "Org-wide issue search",
        2: "Comments on issues",
        3: "Safe retries for issue creation",
        4: "Version checks on issue edits",
        5: "Bulk close",
        6: "Watchers",
        7: "Labels",
    },
    "House rule": {
        1: "Tenant isolation",
        2: "Roles",
        3: "API conventions",
        4: "Safe retries",
        5: "Audit log",
        6: "Layering",
        7: "Migrations",
        8: "Deleted issues stay hidden",
    },
    "Section": {
        1: "Instructions",
        2: "State and sessions",
        3: "Scope and sandbox",
        4: "Verification",
    },  # fmt: skip
    "Assignment": {
        1: "Instructions",
        2: "State and sessions",
        3: "Scope and sandbox",
        4: "Verification",
    },  # fmt: skip
    "Filter": {
        1: "Builds and collects",
        2: "Passes five runs",
        3: "Adds coverage or catches a mutant",
        4: "Real assertions",
        5: "No source changes",
        6: "No duplicate tests",
    },
}
# The code letter of each kind, for the bare-code message.
CODE_KIND = {"F": "Feature", "R": "House rule", "S": "Section", "A": "Assignment"}

MODULE_TITLE = "Module 1: Harness Engineering for Coding Agents"

# The H2 headings of each document type, in order. A test keeps this equal to the
# `skeleton:<type>` blocks in docs/STYLE.md.
TEMPLATES: dict[str, list[str]] = {
    "root-readme": [
        "The problem",
        "Why it happens",
        "The harness",
        "The class plan",
        "What we measured",
        "Quick start",
        "Where next",
    ],
    "section-readme": [
        "The problem",
        "Why it happens",
        "How this section fixes it",
        "How to work through this section",
        "Where next",
    ],
    "concepts": [
        "The problem",
        "The idea in one sentence",
        "How it works",
        "How shipharness does it",
        "What we measured",
        "When it helps, and when it does not",
        "Key takeaways",
        "Check your understanding",
        "Further reading",
    ],
    "walkthrough": [
        "What this code does",
        "The code, explained",
        "If you copy this into your repo",
    ],
    "demo-readme": [
        "The problem",
        "What you'll see",
        "Run it",
        "What to watch",
        "What the result means",
        "If it fails",
    ],
    "final-project": [
        "The problem",
        "What you'll see",
        "Run it",
        "What to watch",
        "What the result means",
        "If it fails",
        "Use it on your own repository",
    ],
    "assignment-readme": [
        "The problem",
        "What you'll build",
        "Step by step",
        "Grading criteria (100 points)",
        "Solution walkthrough",
    ],
    "spec": [
        "Inputs",
        "Files you must produce",
        "Requirements",
        "Self-check",
        "Evidence to hand in",
        "Limits",
    ],
    "solution": [
        "The approach, step by step",
        "Design choices and why",
        "Alternatives considered",
        "Common mistakes this avoids",
        "Run and verify it",
        "Evidence",
    ],
    "reading-index": ["Readings", "How to use these"],
    "reading": ["Why it matters", "Three key ideas", "Apply it to your repo"],
    "session-notes": [
        "What we showed",
        "Key ideas",
        "What the result showed",
        "Questions from class",
        "What to try next",
    ],
    "setup-index": ["What you will install", "Pick your system", "Get help"],
    "setup-os": ["Before you start", "Steps", "Common errors", "You're ready"],
    "instructor-guide": [
        "Class-day cheat sheet",
        "The day before",
        "Thirty minutes before",
        "Section by section",
        "If something breaks",
        "After class",
    ],
    "reference": ["Make targets", "Settings and variables", "Caps and limits", "Folders"],
    "evidence": [
        "How to use this page",
        "Results",
        "Captures",
        "Sources and findings",
        "Commits and tags",
    ],
}

# Checks that do not apply to a file. "SC14:pilot-run" exempts only the "pilot run N" phrase.
EVIDENCE_EXEMPT = {"SC08", "SC09", "SC10", "SC21", "SC22", "SC23", "SC25", "SC14:pilot-run"}
FILE_EXEMPT: dict[str, set[str]] = {
    "docs/evidence.md": EVIDENCE_EXEMPT,  # the index of the evidence pages
    "docs/STYLE.md": {
        "SC01",
        "SC02",
        "SC03",
        "SC08",
        "SC10",
        "SC13",
        "SC14",
        "SC21",
        "SC22",
        "SC23",
        "SC24",
        "SC25",
    },
}
# Fill-in templates in an assignment's starter/ folder (not its README.md): the learner replaces
# their TODO markers and <placeholders>, so the leftover checks do not apply.
_STARTER_TEMPLATE = re.compile(
    r"^section-[1-9]-[a-z0-9-]+/assignment/starter/(?!README\.md$).+\.md$"
)
TEMPLATE_EXEMPT = {"SC01", "SC02", "SC03"}
# The evidence pages, one per section (docs/evidence/s1.md ... s4.md, final.md, general.md): the
# only pages besides the index that may hold run ids, finding ids, and commit hashes.
EVIDENCE_DIR = "docs/evidence/"


def exemptions(rel: str) -> set[str]:
    """The checks that do not apply to `rel`."""
    if rel.startswith(EVIDENCE_DIR):
        return EVIDENCE_EXEMPT
    if _STARTER_TEMPLATE.match(rel):
        return TEMPLATE_EXEMPT
    return FILE_EXEMPT.get(rel, set())


# -- which files are checked ----------------------------------------------------------------------

_SECTION = r"section-[1-9]-[a-z0-9-]+"
_PUBLIC = re.compile(
    rf"^(?:README\.md|setup/.+|{_SECTION}/.+|final-project/.+|use-in-your-repo/.+|docs/.+|guide/.+"
    r"|slides/README\.md)$"
)
# docs/REFERENCES.md is generated by the release build (every source and finding id).
_NOT_PUBLIC = {"docs/CHANGELOG.md", "docs/REFERENCES.md"}
# Files an agent reads, not a learner: the demo harness copies, Assignment 1's instruction trees
# (the AGENTS.md files the learner writes for an agent), the kit templates, and skills.
_AGENT = re.compile(
    rf"^(?:{_SECTION}/demo/harness/.+"
    r"|final-project/harness/(?!README\.md$).+"
    rf"|{_SECTION}/assignment/(?:starter|solution)/(?:[^/]+/)*(?:instructions|original)/.+"
    rf"|{_SECTION}/assignment/(?:starter|solution)/skill/[^/]+/.+"
    r"|(?:.+/)?\.(?:agents|claude)/skills/.+"
    r"|use-in-your-repo/(?:templates|skills|kit/templates)/.+"
    r"|use-in-your-repo/kit/examples/[^/]+/filled/.+)$"
)
_TYPES = [
    (r"README\.md", "root-readme"),
    (rf"{_SECTION}/README\.md", "section-readme"),
    (rf"{_SECTION}/concepts\.md", "concepts"),
    (rf"{_SECTION}/demo/README\.md", "demo-readme"),
    (rf"{_SECTION}/demo/walkthrough\.md", "walkthrough"),
    (rf"{_SECTION}/assignment/README\.md", "assignment-readme"),
    (rf"{_SECTION}/assignment/SPEC\.md", "spec"),
    (rf"{_SECTION}/assignment/solution/SOLUTION\.md", "solution"),
    (rf"{_SECTION}/post-class-reading/README\.md", "reading-index"),
    (rf"{_SECTION}/post-class-reading/\d\d-[^/]+\.md", "reading"),
    (rf"{_SECTION}/session-notes\.md", "session-notes"),
    (r"setup/README\.md", "setup-index"),
    (r"setup/(?:windows|macos|linux)\.md", "setup-os"),
    (r"docs/instructor-guide\.md", "instructor-guide"),
    (r"docs/reference\.md", "reference"),
    (r"docs/evidence/[^/]+\.md", "evidence"),
    (r"final-project/README\.md", "final-project"),
    (r"use-in-your-repo/README\.md", "section-readme"),
]
_DEFAULT_DIRS = ("setup", "final-project", "use-in-your-repo", "docs", "guide")
# Files copied into a learner's repository: the skills and the kit templates. Besides their
# Markdown, their scripts and other text files are read for the label checks.
_COPY_OUT = re.compile(r"^use-in-your-repo/(?:skills|templates|kit/templates)/.+")
TEXT_SUFFIXES = (".py", ".sh", ".json", ".yaml", ".yml", ".toml", ".txt", ".cfg", ".ini")


def _norm(rel: str) -> str:
    rel = rel.replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    return rel


def is_public(rel: str) -> bool:
    """True for a public course page path (POSIX, relative to the repository root). Grader
    folders and hidden test cases in the section folders are not part of the course text."""
    rel = _norm(rel)
    if not _PUBLIC.match(rel) or rel in _NOT_PUBLIC:
        return False
    if re.match(rf"^{_SECTION}/", rel):
        dirs = rel.split("/")[:-1]
        if "grader" in dirs or any(d.startswith("hidden") for d in dirs):
            return False
    return True


def is_agent_file(rel: str) -> bool:
    """Files an agent reads rather than a learner: only the image checks apply to them."""
    return bool(_AGENT.match(_norm(rel)))


def is_copy_out(rel: str) -> bool:
    """Files copied into a learner's repository: no source, finding, run, or assignment ids."""
    return bool(_COPY_OUT.match(_norm(rel)))


# A skill a learner writes or reads as an assignment's solution: an agent file, but its prose
# follows the label rules like the skills in use-in-your-repo/.
_ASSIGNMENT_SKILL = re.compile(rf"^{_SECTION}/assignment/(?:starter|solution)/skill/.+\.md$")
# The harness docs that ship with the course: the demo copies and the final project's harness,
# generated from the TeamTrack harness, which carries the course's names (option B, 2026-10-18).
_SHIPPED_HARNESS = re.compile(rf"^(?:{_SECTION}/demo/harness/.+|final-project/harness/.+)\.md$")


def gets_label_rules(rel: str) -> bool:
    """Every label rule (SC21 to SC25) applies: learner pages, files copied into a learner's
    repository, the shipped harness docs, and the skills of an assignment. Assignment 1's
    instruction trees (the AGENTS.md files a learner writes, which a grader reads) keep their
    own wording."""
    rel = _norm(rel)
    return (
        is_copy_out(rel)
        or bool(_ASSIGNMENT_SKILL.match(rel) or _SHIPPED_HARNESS.match(rel))
        or not is_agent_file(rel)
    )


def is_checked(rel: str) -> bool:
    """A public page, or a text file copied into a learner's repository."""
    rel = _norm(rel)
    if not is_public(rel):
        return False
    return rel.endswith(".md") or (is_copy_out(rel) and rel.endswith(TEXT_SUFFIXES))


def doc_type(rel: str) -> str:
    rel = _norm(rel)
    for pattern, kind in _TYPES:
        if re.fullmatch(pattern, rel):
            return kind
    return "other"


def _walk(folder: Path) -> list[Path]:
    return sorted(
        p
        for p in folder.rglob("*.md")
        if not any(
            part.startswith(".") or part == "node_modules" for part in p.relative_to(folder).parts
        )
    )


def default_files(root: Path) -> list[Path]:
    """Every public course page under `root`."""
    found: list[Path] = []
    if (root / "README.md").is_file():
        found.append(root / "README.md")
    for top in sorted(root.iterdir()):
        if top.is_dir() and (top.name in _DEFAULT_DIRS or re.fullmatch(_SECTION, top.name)):
            found += _walk(top)
    if (root / "slides" / "README.md").is_file():
        found.append(root / "slides" / "README.md")
    kit = root / "use-in-your-repo"
    if kit.is_dir():
        found += sorted(
            p
            for p in kit.rglob("*")
            if p.is_file()
            and p.suffix in TEXT_SUFFIXES
            and not any(
                part.startswith(".") or part in _SKIP_DIRS for part in p.relative_to(kit).parts
            )
            and is_copy_out(p.relative_to(root).as_posix())
        )
    return [p for p in found if is_checked(p.relative_to(root).as_posix())]


# -- folder checks (default run only) -------------------------------------------------------------

# Every section folder holds these; a trailing slash is a folder. diagrams/README.md is required
# once the section has a diagrams/ folder.
SECTION_ITEMS = (
    "README.md",
    "concepts.md",
    "session-notes.md",
    "demo/README.md",
    "demo/run.sh",
    "demo/walkthrough.md",
    "demo/harness/",
    "demo/expected/",
    "assignment/README.md",
    "assignment/SPEC.md",
    "assignment/starter/",
    "assignment/solution/SOLUTION.md",
    "post-class-reading/",
)
FINAL_ITEMS = (
    "README.md",
    "run.sh",
    "tasks/",
    "harness/",
    "walkthrough.md",
    "expected/",
    "your-repo/",
    "CHECKLIST.md",
)
DIAGRAM_SUFFIXES = (".png", ".svg")
_SKIP_DIRS = {".git", ".venv", "node_modules", "dist", "__pycache__"}


def _missing(root: Path, folder: str, items: Iterable[str]) -> list[Problem]:
    out = []
    for item in items:
        path = root / folder / item
        present = path.is_dir() if item.endswith("/") else path.is_file()
        if not present:
            out.append(Problem(f"{folder}/{item}", 0, "SC19", ERROR, f"{folder}/ needs {item}"))
    return out


def section_problems(root: Path) -> list[Problem]:
    """SC19 for every section folder: the required files and folders."""
    out: list[Problem] = []
    for folder in sorted(
        p for p in root.iterdir() if p.is_dir() and re.fullmatch(_SECTION, p.name)
    ):
        items = list(SECTION_ITEMS)
        if (folder / "diagrams").is_dir():
            items.append("diagrams/README.md")
        out += _missing(root, folder.name, items)
    return out


def final_project_problems(root: Path) -> list[Problem]:
    """SC19 for final-project/: the required files and folders."""
    return _missing(root, "final-project", FINAL_ITEMS)


def diagram_problems(root: Path) -> list[Problem]:
    """SC20: every .png or .svg under a diagrams/ folder has a .excalidraw file with its stem."""
    out: list[Problem] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in _SKIP_DIRS or part.startswith(".") for part in rel.parts[:-1]):
            continue
        if path.suffix.lower() in DIAGRAM_SUFFIXES and "diagrams" in rel.parts[:-1]:
            source = path.with_suffix(".excalidraw")
            if not source.is_file():
                message = f"no source {source.name} next to it"
                out.append(Problem(rel.as_posix(), 0, "SC20", ERROR, message))
    return out


def folder_problems(root: Path) -> list[Problem]:
    """Every folder problem: sections, the final project, diagram sources."""
    return section_problems(root) + final_project_problems(root) + diagram_problems(root)


# -- how a page is read ---------------------------------------------------------------------------


@dataclass
class Line:
    no: int
    text: str  # the raw line
    kind: str  # prose, code, fence (an opening or closing fence line), comment
    prose: str = ""  # prose lines: the line without HTML comments
    masked: str = ""  # prose with inline code and link targets filled with "x" (same length)
    nocode: str = ""  # prose with inline code filled with "x" (links kept)


@dataclass
class Fence:
    start: int
    end: int | None
    lang: str
    content: list[Line] = field(default_factory=list)


@dataclass
class Page:
    lines: list[Line]
    fences: list[Fence]


_FENCE_OPEN = re.compile(r"^\s*(`{3,}|~{3,})\s*([^`\s]*)(.*)$")
_FENCE_CLOSE = re.compile(r"^\s*(`{3,}|~{3,})\s*$")
_CODE_SPAN = re.compile(r"(`+)(.+?)\1")
_LINK_TARGET = re.compile(r"\]\(([^)]*)\)")


def _fill(match: re.Match[str]) -> str:
    return "x" * len(match.group(0))


def _mask_code(text: str, tick: str = "") -> tuple[str, str]:
    """`text` with inline code filled with "x", and the backtick run of a code span still open at
    the end of the line (a span may go on to the next line of its paragraph). `tick` is the run
    of a span opened on an earlier line."""
    head = ""
    if tick:
        end = text.find(tick)
        if end < 0:
            return "x" * len(text), tick
        head, text = "x" * (end + len(tick)), text[end + len(tick) :]
    masked = _CODE_SPAN.sub(_fill, text)
    stray = re.search(r"`+", masked)
    if stray:
        return head + masked[: stray.start()] + "x" * (len(masked) - stray.start()), stray.group(0)
    return head + masked, ""


def _mask_links(text: str) -> str:
    return _LINK_TARGET.sub(lambda m: "](" + "x" * len(m.group(1)) + ")", text)


def parse_page(text: str) -> Page:
    lines: list[Line] = []
    fences: list[Fence] = []
    fence: Fence | None = None
    marker = ""
    tick = ""  # an inline code span open from the previous prose line
    in_comment = False
    for no, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            tick = ""
        if fence is not None:
            close = _FENCE_CLOSE.match(raw)
            if close and close.group(1)[0] == marker[0] and len(close.group(1)) >= len(marker):
                fence.end = no
                fence = None
                lines.append(Line(no, raw, "fence"))
            else:
                line = Line(no, raw, "code")
                fence.content.append(line)
                lines.append(line)
            continue
        if in_comment:
            if "-->" not in raw:
                lines.append(Line(no, raw, "comment"))
                continue
            in_comment = False
            rest = raw.split("-->", 1)[1]
        else:
            opening = _FENCE_OPEN.match(raw)
            if opening and not (opening.group(1)[0] == "`" and "`" in opening.group(3)):
                marker, tick = opening.group(1), ""
                fence = Fence(no, None, opening.group(2).lower())
                fences.append(fence)
                lines.append(Line(no, raw, "fence"))
                continue
            rest = raw
        prose, in_comment = _strip_comments(rest)
        if not prose.strip() and (in_comment or "<!--" in raw or "-->" in raw):
            lines.append(Line(no, raw, "comment"))
            continue
        nocode, tick = _mask_code(prose, tick)
        lines.append(Line(no, raw, "prose", prose, _mask_links(nocode), nocode))
    return Page(lines, fences)


def _strip_comments(text: str) -> tuple[str, bool]:
    """`text` without HTML comments, and whether a comment is still open at the end."""
    out = ""
    while True:
        start = text.find("<!--")
        if start < 0:
            return out + text, False
        end = text.find("-->", start + 4)
        if end < 0:
            return out + text[:start], True
        out += text[:start]
        text = text[end + 3 :]


# -- checks ---------------------------------------------------------------------------------------


@dataclass(frozen=True, order=True)
class Problem:
    path: str
    line: int
    check: str
    severity: str
    message: str


_ALLOW = re.compile(r"<!--\s*check-style:\s*allow\s+(SC\d\d)\b(.*?)-->\s*$")

# "TODO 1a" names a numbered gap in starter code and "TODO markers" a handoff field: not leftovers.
_MARKERS = re.compile(
    r"\b(?:TODO(?!\s*\d|\s+markers?\b)|TBD|FIXME|XXX)\b|\[\[\s*(?i:PENDING|CAPTURE)\b"
)
_BRACES_PROSE = re.compile(r"(?<!\$)\{\{[^{}\n]*\}\}")
# In code, Go templates such as {{.Names}} or {{json .}} are real commands, not leftovers.
_BRACES_CODE = re.compile(r"(?<!\$)\{\{(?!\s*(?:\.|json\b))[^{}\n]*\}\}")
_EMPTY_VALUE = [
    re.compile(r"[\w)\]`'\"]\s+[,;]"),
    re.compile(r"\b(?:on|at|from|commit|run|by|in|of)\s+[.:)]", re.I),
    re.compile(r"\(\s*\)"),
]
_ANGLE = re.compile(
    r"<(?!!--|/?(?:details|summary|br|sub|sup|kbd|img|a|p)\b|https?://)[^<>\n]{1,80}>"
)
_IMAGE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<src><[^>]+>|[^)\s]+)(?:\s+\"[^\"]*\")?\)")
_IMG_TAG = re.compile(r"<img\b[^>]*\bsrc=\"(?P<src>[^\"]+)\"[^>]*>", re.I)
_IMAGE_REF = re.compile(r"!\[[^\]]*\]\[[^\]]*\]")
_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")
_CAPTION = re.compile(r"^\*(?!\*)\S.*\S\*$|^_(?!_)\S.*\S_$")
_RUN_ID = re.compile(r"\b(?:ab|r)-\d{8}-\d{6}-[0-9a-f]{6}\b")
_FINDING = re.compile(r"\bF-[ab]-\d+\b")
# A source id (A1 to A7, B1 to B14) or an assignment id (A1 to A4). "Part A1" names a part of
# Assignment 3; tokens in code spans and fenced code are identifiers and are not read.
_LABEL = re.compile(r"(?<!Part )\b[AB]\d{1,2}\b")
# A bare code in prose: F1 to F7, R1 to R8, S1 to S4, A1 to A7, B1 to B14. "S4:gate" is a slide
# anchor, "R-S1" a requirement id, "f1.md" a file, "F1-trap" a task name (in a code span), and
# "Part A1" a part of Assignment 3.
_BARE_CODE = re.compile(
    r"(?<![-\w./])(?<!Part )(?:F[1-7]|R[1-8]|S[1-4]|A[1-7]|B(?:1[0-4]|[1-9]))(?![\w]|-[a-z]|:\w)"
)
# A singular mention of a kind with its number; plurals ("Sections 1 to 4") are not mentions.
_KIND_MENTION = re.compile(
    r"(?<![\w-])(?P<kind>[Ff]eature|[Hh]ouse rule|[Ss]ection|[Aa]ssignment|[Ff]ilter) "
    r"(?P<n>[1-9])(?![\w.]\d|\d)"
)
_SOURCE_REF = re.compile(r"\bSource (\d+)\b")
_QUOTE = re.compile(r"^\s*(?:>\s*)+")
_MD_LINK = re.compile(r"(?<!!)\[(?P<text>[^\]]*)\]\((?P<url>[^)\s]*)[^)]*\)")
_EMPTY_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(\s*\)|(?<!!)\[\s*\]\([^)]*\)|\[link\]", re.I)
_URL_TARGET = re.compile(r"\]\((https?:[^)\s]*)")
_GOOD_URL = re.compile(r"^https?://[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+(?::\d+)?(?:[/?#][^\s<>\"]*)?$")
# The list of sources at the end of a page, and one entry of it:
# "- Source 1: <title>, <link>, <author>, <date>"; the link is a <URL>, a URL, or a Markdown link.
_SOURCES_HEADING = re.compile(r"^#{2,3} Sources\s*$")
_SOURCE_ITEM = re.compile(
    r"^(?:[-*+]|\d+\.)\s+Source (?P<n>\d+): (?P<title>\S.*?), "
    r"(?P<link><https?://[^>\s]+>|\[[^\]]+\]\(https?://[^)\s]+\)|https?://[^\s,]+), "
    r"(?P<author>\S.*?), (?P<date>\d{4}(?:-\d{2}){0,2}|n\.d\.)\.?$"
)
_ITEM_URL = re.compile(r"https?://[^>\s),]+")
# The sources a page may name: a short-name pattern, and the URL a link to it must use (from the
# course's source register). The module title "Harness Engineering" is not a source name.
_OWNER = r"(?:,|['’]s)?\s+[\"“]?"
SOURCES: list[tuple[str, re.Pattern[str], re.Pattern[str]]] = [
    (
        "OpenAI, Harness engineering",
        re.compile(rf"\bOpenAI{_OWNER}Harness engineering\b|Harness engineering: leveraging"),
        re.compile(r"https://openai\.com/index/harness-engineering/?"),
    ),
    (
        "Anthropic, Effective harnesses",
        re.compile(r"\bEffective harnesses\b"),
        re.compile(r"https://www\.anthropic\.com/engineering/effective-harnesses-for-long-running"),
    ),
    (
        "Anthropic, Harness design",
        re.compile(rf"\bAnthropic{_OWNER}Harness design\b|Harness design for long-running"),
        re.compile(r"https://www\.anthropic\.com/engineering/harness-design-long-running-apps"),
    ),
    (
        "Anthropic, C compiler",
        re.compile(rf"\bAnthropic{_OWNER}(?:Building a )?C compiler\b"),
        re.compile(r"https://www\.anthropic\.com/engineering/building-c-compiler"),
    ),
    (
        "Anthropic, Autonomous coding demo",
        re.compile(r"\bAutonomous [Cc]oding (?:[Aa]gent )?[Dd]emo\b"),
        re.compile(r"https://github\.com/anthropics/claude-quickstarts"),
    ),
    (
        "Anthropic, Prompting best practices",
        re.compile(r"\bPrompting best practices\b"),
        re.compile(r"https://platform\.claude\.com/docs/en/build-with-claude/prompt-engineering/"),
    ),
    (
        "OpenAI, Exec plans",
        re.compile(rf"\bOpenAI{_OWNER}Exec(?:ution)? plans\b|Using PLANS\.md for"),
        re.compile(r"https://cookbook\.openai\.com/articles/codex_exec_plans"),
    ),
    (
        "Agent Skills, Specification",
        re.compile(r"\bAgent Skills,? [Ss]pecification\b"),
        re.compile(r"https://agentskills\.io/specification"),
    ),
    (
        "Agent Skills, Agent Skills Overview",
        re.compile(r"\bAgent Skills, (?:Agent Skills )?Overview\b"),
        re.compile(r"https://agentskills\.io/home"),
    ),
    (
        "Agent Skills, Client guide",
        re.compile(r"\bAgent Skills, Client guide\b"),
        re.compile(r"https://agentskills\.io/client-implementation/"),
    ),
    (
        "Agent Skills, skills-ref",
        re.compile(r"\bAgent Skills, skills-ref\b"),
        re.compile(r"https://(?:github\.com/agentskills/agentskills|pypi\.org/project/skills-ref)"),
    ),
    (
        "Claude Code, Skills",
        re.compile(r"\bClaude Code, [Ss]kills\b|\bExtend Claude with skills\b"),
        re.compile(r"https://code\.claude\.com/docs/en/skills"),
    ),
    (
        "Codex, Skills",
        re.compile(r"\bCodex, [Ss]kills\b|\bBuild skills \(Codex\)"),
        re.compile(
            r"https://(?:learn\.chatgpt\.com/docs/build-skills|developers\.openai\.com/codex/skills)"
        ),
    ),
    (
        "Cursor, Skills",
        re.compile(r"\bCursor, [Ss]kills\b"),
        re.compile(r"https://cursor\.com/docs/(?:context/)?skills"),
    ),
    (
        "Cursor 2.4 changelog",
        re.compile(r"\bCursor 2\.4\b"),
        re.compile(r"https://cursor\.com/changelog/2-4"),
    ),
    (
        "Meta, TestGen-LLM",
        re.compile(r"\bTestGen-LLM\b"),
        re.compile(r"https://arxiv\.org/abs/2402\.09171"),
    ),
    (
        "Meta, ACH",
        re.compile(r"\bMeta,? ACH\b|\bACH\b(?=[ ,.)])"),
        re.compile(r"https://arxiv\.org/abs/2501\.12862"),
    ),
    (
        "SpecBench",
        re.compile(r"\bSpecBench\b"),
        re.compile(r"https://(?:arxiv\.org/abs/2605\.21384|github\.com/WecoAI/SpecBench)"),
    ),
]
_HASH_CONTEXT = re.compile(r"\b(?:commit|sha|checkpoint_sha|tag)\b", re.I)
_HASH_TOKEN = re.compile(r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b")
_HASH_FULL = re.compile(r"\b[0-9a-f]{40}\b")
_WORD = re.compile(r"[A-Za-z0-9][\w'’.-]*")
_DELIMITER = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$")
_DIFFER = re.compile(r"\byour (?:output|run|results?|numbers?|times?) will differ\b", re.I)
_BANNED: list[tuple[str, re.Pattern[str]]] = [
    ("owner scope", re.compile(r"\bowner[- ]scope\b", re.I)),
    # "owner's" about the course's owner; a resource owner in TeamTrack ("a project owner's
    # token", "the owner's role") is the product's wording and stays.
    (
        "owner's",
        re.compile(
            r"(?<!project )(?<!org )(?<!team )(?<!tenant )(?<!resource )(?<!issue )(?<!file )"
            r"\bowner['’]s\b(?!\s+(?:role|id|org|organi[sz]ation|project|account|token|"
            r"permissions?|issues?|data)\b)",
            re.I,
        ),
    ),
    ("class host", re.compile(r"\bclass[- ]host\b", re.I)),
    ("build repository", re.compile(r"\bbuild repo(?:sitory)?\b", re.I)),
    ("build branch", re.compile(r"\bbuild branch\b", re.I)),
    ("this release", re.compile(r"\bthis release\b", re.I)),
    ("not a make target", re.compile(r"\bnot a make target(?: in this release)?\b", re.I)),
    ("pilot-run", re.compile(r"\bpilot runs? \d+\b", re.I)),
    ("PENDING or CAPTURE", re.compile(r"\b(?:PENDING|CAPTURE)\b")),
    ("milestone code", re.compile(r"(?<!Apple )\bM(?:1[0-9]|[1-9])\b")),
    ("brief", re.compile(r"\b(?:the|course|original) brief\b|\bbrief §", re.I)),
    ("lead (a role)", re.compile(r"\b(?:the|course|class|tech|team) lead\b", re.I)),
    (
        "release leftover",
        re.compile(r"\bgenerated (?:when|at) (?:the course is )?release(?:d)?\b|\(private\)", re.I),
    ),
    (
        "sentence about labels",
        re.compile(
            r"\bnote on labels\b|\b(?:are|is) (?:a )?course labels?\b|\bnot source terms?\b", re.I
        ),
    ),
]
_ROOT_TITLE = re.compile(rf"^# {re.escape(MODULE_TITLE)}$")
_PAGE_TITLE = re.compile(rf"^# {re.escape(MODULE_TITLE)}(?: - \S.*)?$")
_TRY_IT = re.compile(
    r"Try it yourself first\. The full solution is in \[?`?\./solution/`?\]?(\([^)]*\))? "
    r"with a step-by-step walkthrough\."
)
_GLOSSARY = re.compile(r"^> \*\*Terms on this page\*\*\s*$")
_GLOSSARY_ITEM = re.compile(r"^>\s*- \*\*(?P<term>[^*]+)\*\*: \S")
_COMMENT_BY_LANG: dict[str, str] = {}
for _lang in ("bash", "sh", "shell", "zsh", "console", "python", "py", "toml", "yaml", "yml",
              "text", "ini", "make", "makefile", "dockerfile", "powershell", "ps1"):  # fmt: skip
    _COMMENT_BY_LANG[_lang] = r"^\s*#(?!!)"
for _lang in ("js", "javascript", "ts", "typescript", "json5", "c", "go", "rust"):
    _COMMENT_BY_LANG[_lang] = r"^\s*(?://|/\*.*\*/\s*$)"
for _lang in ("sql", "lua"):
    _COMMENT_BY_LANG[_lang] = r"^\s*--"
for _lang in ("html", "xml", "markdown", "md"):
    _COMMENT_BY_LANG[_lang] = r"^\s*<!--.*-->\s*$"
_COMMENT_BY_LANG[""] = r"^\s*(?:#(?!!)|//)"

_LINE_LIMITS = {
    "root-readme": 250,
    "demo-readme": 250,
    "section-readme": 120,
    "assignment-readme": 250,
    "final-project": 250,
    "session-notes": 150,
    "reading": 80,
}
CONCEPTS_WORDS = 1800
EXCERPT_LINES = 40
CHEAT_SHEET_LINES = 60
WALKTHROUGH_CODE = (25, 45)
TABLE_COLUMNS = 4
TABLE_CELL = 80
CAPTION_MAX = 200


class _Collector:
    def __init__(self, rel: str) -> None:
        self.rel = rel
        self.items: list[Problem] = []

    def add(self, line: int, check: str, message: str, severity: str | None = None) -> None:
        self.items.append(Problem(self.rel, line, check, severity or CHECKS[check][1], message))


def _h2s(page: Page) -> list[tuple[int, str]]:
    out = []
    for ln in page.lines:
        match = re.match(r"^## (.+?)\s*$", ln.text) if ln.kind == "prose" else None
        if match:
            out.append((ln.no, match.group(1)))
    return out


def _section(page: Page, heading: str) -> list[Line]:
    """The lines under `## heading`, up to the next H2."""
    out: list[Line] = []
    inside = False
    for ln in page.lines:
        if ln.kind == "prose" and ln.text.startswith("## "):
            if inside:
                break
            inside = ln.text[3:].strip() == heading
            continue
        if inside:
            out.append(ln)
    return out


def _images(ln: Line) -> list[tuple[str, str | None, str]]:
    """(source, alt or None for an <img> without alt, matched text) for each image on a line."""
    out: list[tuple[str, str | None, str]] = []
    for m in _IMAGE.finditer(ln.nocode):
        out.append((ln.prose[m.start("src") : m.end("src")], m.group("alt"), m.group(0)))
    for m in _IMG_TAG.finditer(ln.nocode):
        tag = ln.prose[m.start() : m.end()]
        alt = re.search(r"\balt=\"([^\"]*)\"", tag)
        out.append((m.group("src"), alt.group(1) if alt else None, tag))
    return out


def count_words(page: Page) -> int:
    """Words in prose, headings, lists, quotes, and table cells: fences, comments, and image lines
    are left out; link targets are removed."""
    total = 0
    for ln in page.lines:
        if ln.kind != "prose" or _is_alone(ln):
            continue
        total += len(_WORD.findall(_LINK_TARGET.sub("]", ln.prose)))
    return total


def _is_alone(ln: Line) -> bool:
    """The line is a single image and nothing else."""
    return any(ln.nocode.strip() == matched for _, _, matched in _images(ln))


def _check_markers(page: Page, c: _Collector) -> None:
    for ln in page.lines:
        if ln.kind == "fence":
            continue
        if ln.kind == "prose":
            # A marker named in inline code is a mention; one in an HTML comment is a leftover.
            comments = " ".join(re.findall(r"<!--(.*?)(?:-->|$)", ln.text))
            text, braces = f"{ln.nocode} {comments}", _BRACES_PROSE.search(ln.masked)
        else:
            text, braces = ln.text, _BRACES_CODE.search(ln.text)
        match = _MARKERS.search(text)
        if match:
            c.add(ln.no, "SC01", f"leftover marker '{match.group(0)}'")
        if braces:
            c.add(ln.no, "SC01", f"leftover template value '{braces.group(0)}'")


def _check_prose_values(page: Page, c: _Collector) -> None:
    for ln in page.lines:
        if ln.kind != "prose":
            continue
        for regex in _EMPTY_VALUE:
            match = regex.search(ln.masked)
            if match:
                c.add(ln.no, "SC02", f"empty value: '{match.group(0).strip()}'")
                break
        angle = _ANGLE.search(ln.masked)
        if angle:
            c.add(ln.no, "SC03", f"angle-bracket placeholder '{angle.group(0)}'")
    for fence in page.fences:
        for ln in fence.content:
            stripped = ln.text.strip()
            if stripped.startswith("git clone") and (
                "https://github.com/" not in stripped or "<" in stripped
            ):
                c.add(ln.no, "SC03", "git clone needs the real https://github.com/ URL")


def _check_fences(page: Page, c: _Collector) -> None:
    for fence in page.fences:
        if fence.end is None:
            c.add(fence.start, "SC04", "unclosed fenced code block")
            continue
        body = [ln.text for ln in fence.content if ln.text.strip()]
        if not body:
            c.add(fence.start, "SC04", "empty fenced code block")
            continue
        comment = _COMMENT_BY_LANG.get(fence.lang)
        if comment and all(re.match(comment, line) for line in body):
            c.add(fence.start, "SC05", "the block holds only comments")


def _check_images(page: Page, c: _Collector, root: Path, rel: str, agent: bool) -> None:
    lines = page.lines
    for index, ln in enumerate(lines):
        if ln.kind != "prose":
            continue
        if _IMAGE_REF.search(ln.nocode):
            c.add(ln.no, "SC06", "use inline image syntax: ![alt](path)")
        for src, _alt, _matched in _images(ln):
            if _is_badge(src):
                continue  # a CI status badge: remote by design, and it needs no caption
            problem = _image_problem(root, rel, src)
            if problem:
                c.add(ln.no, "SC06", problem)
            if agent:
                continue
            if not _is_alone(ln):
                c.add(ln.no, "SC07", "an image stands alone on its line")
                continue
            blank = index + 1 < len(lines) and not lines[index + 1].text.strip()
            caption = lines[index + 2].text.strip() if index + 2 < len(lines) else ""
            if not blank or not _CAPTION.match(caption) or len(caption) > CAPTION_MAX:
                c.add(ln.no, "SC07", "an image needs a blank line, then an italic caption line")


# The one remote image a page may show: the CI status badge GitHub Actions serves for a workflow.
_BADGE = re.compile(
    r"^https://github\.com/[\w.-]+/[\w.-]+/actions/workflows/[\w.-]+\.ya?ml/badge\.svg$"
)


def _is_badge(src: str) -> bool:
    return bool(_BADGE.match(src.strip("<>")))


def _image_problem(root: Path, rel: str, src: str) -> str | None:
    if src.startswith(("http://", "https://")):
        return f"remote image {src}: store images in the repository"
    path = unquote(src.strip("<>").split("#", 1)[0])
    if not path.lower().endswith(_IMAGE_SUFFIXES):
        return f"image {src} is not one of {' '.join(_IMAGE_SUFFIXES)}"
    target = root / path.lstrip("/") if path.startswith("/") else (root / rel).parent / path
    if not target.is_file():
        return f"image file {src} does not exist"
    if target.stat().st_size == 0:
        return f"image file {src} is empty"
    return None


# Alt text that names no content: a screen reader would read only this word.
_EMPTY_ALT_WORDS = {"image", "img", "picture", "photo", "screenshot", "screen shot", "diagram",
                    "figure", "chart", "graph", "icon", "logo", "alt", "alt text"}  # fmt: skip


def _plain_words(text: str) -> str:
    """Lowercase words only: separators and a trailing image suffix removed."""
    text = text.strip().lower()
    for suffix in _IMAGE_SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return " ".join(re.split(r"[\s_./-]+", text)).strip()


def alt_text_problem(src: str, alt: str | None) -> str | None:
    """Why the alt text of the image at `src` says nothing to a reader who cannot see it, or None:
    empty or missing, the image's file name, or one generic word such as "image"."""
    if alt is None or not alt.strip():
        return f"image {src} has no alt text: say what the image shows"
    name = unquote(src.strip("<>").split("#", 1)[0]).rsplit("/", 1)[-1]
    words = _plain_words(alt)
    if alt.strip().lower().endswith(_IMAGE_SUFFIXES) or words == _plain_words(name):
        return f"image {src}: the alt text is only its file name; say what the image shows"
    if words in _EMPTY_ALT_WORDS:
        return f"image {src}: the alt text '{alt.strip()}' says nothing; say what the image shows"
    return None


def _check_alt_text(page: Page, c: _Collector) -> None:
    """SC26: every image has alt text that says what it shows (STYLE rule 11)."""
    for ln in page.lines:
        if ln.kind != "prose":
            continue
        for src, alt, _matched in _images(ln):
            problem = alt_text_problem(src, alt)
            if problem:
                c.add(ln.no, "SC26", problem)


def _scanned(page: Page) -> Iterable[tuple[Line, str]]:
    """Prose (without comments) and code lines, for the id and phrase checks."""
    for ln in page.lines:
        if ln.kind == "prose":
            yield ln, ln.prose
        elif ln.kind == "code":
            yield ln, ln.text


# The Live Demo Guide (guide/) follows one recorded run per demo, so a reader types and
# reads its run id: `make replay RUN=<id>`, the console's run list, terminal output. There, and only
# there, a run id may stand in a code span or a fenced block; in plain prose it still fails SC08.
WALKTHROUGH_DIR = "guide/"


def _check_ids(page: Page, c: _Collector, rel: str = "") -> None:
    ids_in_code_ok = rel.startswith(WALKTHROUGH_DIR)
    for ln, text in _scanned(page):
        if ids_in_code_ok:
            text = ln.nocode if ln.kind == "prose" else ""
        match = _RUN_ID.search(text)
        if match:
            c.add(ln.no, "SC08", f"run id {match.group(0)}: ids go in the evidence pages")
        full = _HASH_FULL.search(text)
        token = _HASH_TOKEN.search(text) if _HASH_CONTEXT.search(text) else None
        if full or token:
            found = (full or token).group(0)  # type: ignore[union-attr]
            c.add(ln.no, "SC10", f"commit hash {found}: hashes go in the evidence pages")


def _ids_in_script(no: int, text: str, c: _Collector) -> None:
    """SC21 in a script or other text file copied out: source and assignment ids only (code ids
    such as a check named "S1" are identifiers)."""
    for match in _LABEL.finditer(text):
        c.add(no, "SC21", f"source or assignment id {match.group(0)}: name the source (with a "
              "link to it) or write 'Assignment N: <name>'")  # fmt: skip


def _bare_code_message(code: str) -> str:
    letter, number = code[0], int(code[1:])
    if letter == "B" or (letter == "A" and number > 4):
        return f"source id {code}: cite the source by its linked title"
    kind = CODE_KIND[letter]
    full = f"{kind} {number}: {NAMES[kind][number]}"
    if letter == "A":
        return f"source or assignment id {code}: cite the source by its linked title, or '{full}'"
    return f"bare code {code}: write '{full}' (the first time on the page), then '{kind} {number}'"


def _check_bare_codes(page: Page, c: _Collector) -> None:
    """SC21: no bare F1-F7, R1-R8, S1-S4, A1-A7, or B1-B14 in prose or HTML comments. Code
    spans, fenced code, and link targets are not read."""
    for ln in page.lines:
        if ln.kind in ("fence", "code"):
            continue
        masked = _mask_links(_mask_code(ln.text)[0])
        for match in _BARE_CODE.finditer(masked):
            c.add(ln.no, "SC21", _bare_code_message(match.group(0)))


def _paragraphs(lines: list[Line]) -> Iterable[list[Line]]:
    """Runs of consecutive prose lines (a paragraph, list, or table)."""
    run: list[Line] = []
    for ln in lines:
        if ln.kind == "prose" and ln.prose.strip():
            run.append(ln)
            continue
        if run:
            yield run
        run = []
    if run:
        yield run


def _joined(run: list[Line], attr: str) -> tuple[str, list[tuple[int, int]]]:
    """The run's lines joined with newlines, and (offset, line number) for each line."""
    text, starts = "", []
    for ln in run:
        starts.append((len(text), ln.no))
        # A quote marker at the start of a line is not part of the sentence it continues.
        text += _QUOTE.sub(lambda m: " " * len(m.group(0)), getattr(ln, attr)) + "\n"
    return text, starts


def _line_at(starts: list[tuple[int, int]], offset: int) -> int:
    return [no for start, no in starts if start <= offset][-1]


def _check_full_names(page: Page, c: _Collector) -> None:
    """SC22: the first mention of Feature N, House rule N, Section N, Assignment N, or Filter N on
    a page is the full '<Kind> N: <exact name>'."""
    seen: set[tuple[str, int]] = set()
    for run in _paragraphs(page.lines):
        text, starts = _joined(run, "masked")
        for match in _KIND_MENTION.finditer(text):
            kind = match.group("kind")
            kind = kind[0].upper() + kind[1:]
            number = int(match.group("n"))
            name = NAMES[kind].get(number)
            if name is None or (kind, number) in seen:
                continue
            seen.add((kind, number))
            after = " ".join(text[match.end() : match.end() + len(name) + 40].split())
            rest = after[len(name) + 2 :]
            if not after.startswith(f": {name}") or rest[:1].isalnum():
                want = f"{kind} {number}: {name}"
                c.add(_line_at(starts, match.start()), "SC22", f"first mention of "
                      f"'{kind} {number}' on the page: write '{want}'")  # fmt: skip


def _sources_start(page: Page) -> int | None:
    """The index in page.lines of the last 'Sources' heading, if no H2 follows it."""
    heading = max(
        (
            i
            for i, ln in enumerate(page.lines)
            if ln.kind == "prose" and _SOURCES_HEADING.match(ln.text)
        ),
        default=None,
    )
    if heading is None:
        return None
    after = page.lines[heading + 1 :]
    if any(ln.kind == "prose" and ln.text.startswith("## ") for ln in after):
        return None
    return heading


def _source_items(page: Page, heading: int) -> list[tuple[int, str]]:
    """(line number, text) for each list item under the Sources heading, continuation lines
    joined."""
    items: list[tuple[int, str]] = []
    for ln in page.lines[heading + 1 :]:
        if ln.kind != "prose" or not ln.text.strip():
            continue
        if re.match(r"^(?:[-*+]|\d+\.)\s", ln.text):
            items.append((ln.no, ln.text.strip()))
        elif items and ln.text.startswith(" "):
            items[-1] = (items[-1][0], f"{items[-1][1]} {ln.text.strip()}")
        else:
            items.append((ln.no, ln.text.strip()))
    return items


def _norm_url(url: str) -> str:
    return url.strip("<>").split("#", 1)[0].rstrip("/").lower()


def _body(page: Page) -> list[Line]:
    heading = _sources_start(page)
    return page.lines if heading is None else page.lines[:heading]


def _body_links(page: Page) -> list[tuple[int, str]]:
    """(line, URL) for each Markdown link in the page body, in order (a link may wrap)."""
    out: list[tuple[int, str]] = []
    for run in _paragraphs(_body(page)):
        nocode, starts = _joined(run, "nocode")
        for m in _MD_LINK.finditer(nocode):
            out.append((_line_at(starts, m.start()), m.group("url")))
    return out


def _cited(page: Page) -> list[tuple[int, str]]:
    """(line, source name) for each registered source the page body cites, by a link to its URL
    or by naming it, in page order."""
    out: list[tuple[int, str]] = []
    for no, target in _body_links(page):
        out += [(no, name) for name, _, url in SOURCES if url.match(target)]
    for ln in _body(page):
        if ln.kind == "prose":
            out += [(ln.no, name) for name, mention, _ in SOURCES if mention.search(ln.masked)]
    return sorted(out)


def _check_source_links(page: Page, c: _Collector) -> None:
    """SC23: every mention of a registered source's title is the text of a link to its URL, and
    every 'Source N' has an entry N in the page's Sources list."""
    for run in _paragraphs(_body(page)):
        nocode, starts = _joined(run, "nocode")
        masked = _mask_links(nocode)
        links = [
            (m.start("text"), m.end("text"), m.group("url")) for m in _MD_LINK.finditer(nocode)
        ]
        for name, mention, url in SOURCES:
            for match in mention.finditer(masked):
                inside = any(
                    start <= match.start() and match.end() <= end and url.match(target)
                    for start, end, target in links
                )
                if not inside:
                    c.add(_line_at(starts, match.start()), "SC23", f"'{name}' is named without "
                          "a link: cite it as [its title](its URL)")  # fmt: skip
    heading = _sources_start(page)
    items = _source_items(page, heading) if heading is not None else []
    listed = {int(m.group("n")) for _, text in items for m in [_SOURCE_ITEM.match(text)] if m}
    for ln in _body(page):
        if ln.kind != "prose":
            continue
        for match in _SOURCE_REF.finditer(ln.masked):
            if int(match.group(1)) not in listed:
                c.add(ln.no, "SC23", f"'Source {match.group(1)}' has no entry in the Sources list")


def _check_link_format(page: Page, c: _Collector) -> None:
    """SC24: an empty link, a '[link]' placeholder, or a link URL that is not well formed."""
    for ln in page.lines:
        if ln.kind in ("fence", "code"):
            continue
        text = _mask_code(ln.text)[0]
        match = _EMPTY_LINK.search(text)
        if match:
            c.add(ln.no, "SC24", f"empty or placeholder link '{match.group(0)}'")
        for target in _LINK_TARGET.findall(text):
            url = target.strip().split(" ", 1)[0].strip("<>")
            looks_remote = "://" in url or url.startswith(("http", "htp", "www.")) or "//" in url
            if looks_remote and not _GOOD_URL.match(url):
                c.add(ln.no, "SC24", f"malformed link URL '{url}'")


def _check_sources_list(page: Page, c: _Collector) -> None:
    """SC25: a page that cites a source (a link to a registered source, its name, or 'Source N')
    ends with a Sources list: one '- Source N: <title>, <link>, <author>, <date>' per source,
    numbered from 1 in the order the page first links them, each cited source listed."""
    cited = _cited(page)
    refs = [ln.no for ln in _body(page) if ln.kind == "prose" and _SOURCE_REF.search(ln.masked)]
    heading = _sources_start(page)
    if heading is None:
        has_heading = any(
            ln.kind == "prose" and _SOURCES_HEADING.match(ln.text) for ln in page.lines
        )
        if cited or refs:
            where = min([line for line, _ in cited] + refs)
            c.add(where, "SC25", "a page that cites a source ends with a '## Sources' list"
                  + (" (after the last H2)" if has_heading else ""))  # fmt: skip
        elif has_heading:
            c.add(1, "SC25", "the '## Sources' list is the last H2 of the page")
        return
    items = _source_items(page, heading)
    urls: list[str] = []
    for number, (no, text) in enumerate(items, start=1):
        match = _SOURCE_ITEM.match(text)
        if not match:
            c.add(no, "SC25", "a Sources entry reads '- Source N: <title>, <link>, <author>, "
                  "<date>'")  # fmt: skip
            urls.append("")
            continue
        if int(match.group("n")) != number:
            c.add(no, "SC25", f"Source {match.group('n')} is entry {number}: number them 1, 2, ...")
        found = _ITEM_URL.search(match.group("link"))
        urls.append(_norm_url(found.group(0)) if found else "")
    listed = "\n".join(text for _, text in items)
    for name in dict.fromkeys(name for _, name in cited):
        url = next(u for n, _, u in SOURCES if n == name)
        if not url.search(listed):
            line = next(line for line, n in cited if n == name)
            c.add(line, "SC25", f"'{name}' needs an entry, with its link, in the Sources list")
    # Source 1 is the first source the body links to.
    first: dict[str, int] = {}
    for no, target in _body_links(page):
        first.setdefault(_norm_url(target), no)
    order = [first[u] for u in urls if u in first]
    if order != sorted(order):
        c.add(page.lines[heading].no, "SC25", "number the sources in the order the page first "
              "links them")  # fmt: skip


def _check_labels(page: Page, c: _Collector, rel: str) -> None:
    """SC09 on every line, and SC08 too in the files copied into a learner's repository; the label
    rules SC21 to SC25 on the pages that follow them (`gets_label_rules`)."""
    copy_out = is_copy_out(rel)
    for ln in page.lines:
        if ln.kind == "fence":
            continue
        match = _FINDING.search(ln.text)
        if match:
            c.add(ln.no, "SC09", f"finding id {match.group(0)}: ids go in the evidence pages")
        match = _RUN_ID.search(ln.text) if copy_out else None
        if match:
            c.add(ln.no, "SC08", f"run id {match.group(0)}: ids go in the evidence pages")
    if gets_label_rules(rel):
        _check_bare_codes(page, c)
        _check_full_names(page, c)
        _check_source_links(page, c)
        _check_link_format(page, c)
        _check_sources_list(page, c)


# -- relative links resolve (SC30) ----------------------------------------------------------------

# A link's target: inline `[text](target "title")`, a reference definition `[id]: target`, or an
# HTML `<a href="target">`. Images are SC06's.
_INLINE_LINK = re.compile(
    r"(?<!!)\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*(<[^>]*>|[^)\s]*)(?:\s+\"[^\"]*\")?\s*\)"
)
_REF_DEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*(<[^>]*>|\S+)")
_HTML_HREF = re.compile(r"<a\b[^>]*\bhref=\"([^\"]+)\"", re.I)
_HTML_ID = re.compile(r"\b(?:id|name)=\"([^\"]+)\"")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:|^//")
# Generated by the release build: absent from the repository until then.
_GENERATED = {"docs/REFERENCES.md"}
# The kit templates and the skill templates are copied into a learner's repository: their links
# point into that repository (docs/STYLE.md, rule 5).
_LEARNER_REPO_LINKS = re.compile(
    r"^use-in-your-repo/(?:templates|kit/templates|skills/[^/]+/assets/templates)/"
)


def gets_link_check(rel: str) -> bool:
    """SC30 applies to learner pages and to the skills copied into a learner's repository, whose
    links point inside the skill. The other agent files point into the repository the agent works
    in, and the kit templates into the learner's own repository."""
    rel = _norm(rel)
    if _LEARNER_REPO_LINKS.match(rel):
        return False
    return is_copy_out(rel) or not is_agent_file(rel)


def slug(heading: str) -> str:
    """GitHub's anchor for a heading: rendered text, lower case, punctuation removed, spaces to
    hyphens."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    text = re.sub(r"<[^>]+>", "", text).strip().lower()
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def anchors(text: str) -> set[str]:
    """The anchors of a Markdown page: one per heading (a repeated heading gets -1, -2, ...) and
    every HTML id or name."""
    found: set[str] = set()
    seen: dict[str, int] = {}
    for ln in parse_page(text).lines:
        if ln.kind == "prose":
            match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", ln.prose)
            if match:
                base = slug(match.group(1))
                count = seen.get(base, 0)
                seen[base] = count + 1
                found.add(base if count == 0 else f"{base}-{count}")
        if ln.kind in ("prose", "comment"):
            found.update(_HTML_ID.findall(ln.text))
    return found


def _link_targets(page: Page) -> Iterable[tuple[int, str]]:
    for ln in page.lines:
        if ln.kind != "prose":
            continue
        for match in _INLINE_LINK.finditer(ln.nocode):
            yield ln.no, ln.prose[match.start(1) : match.end(1)]
        match = _REF_DEF.match(ln.nocode)
        if match:
            yield ln.no, ln.prose[match.start(1) : match.end(1)]
        for match in _HTML_HREF.finditer(ln.nocode):
            yield ln.no, match.group(1)


def link_problems(
    page: Page, root: Path, rel: str, cache: dict[Path, set[str]]
) -> list[tuple[int, str]]:
    """(line, message) for each relative link whose file, folder, or Markdown heading is missing."""
    out: list[tuple[int, str]] = []
    here = (root / rel).parent
    for no, target in _link_targets(page):
        target = target.strip("<>").strip()
        if not target or _SCHEME.match(target):
            continue
        path, _, anchor = target.partition("#")
        path = unquote(path)
        if not path:
            file = root / rel
        elif path.startswith("/"):
            file = root / path.lstrip("/")
        else:
            file = here / path
        try:
            key = file.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            key = ""
        if key in _GENERATED:
            continue
        exists = file.is_dir() if path.endswith("/") else file.exists()
        if not exists:
            out.append((no, f"link target {target} does not exist"))
            continue
        if anchor and file.is_file() and file.suffix.lower() == ".md":
            resolved = file.resolve()
            if resolved not in cache:
                cache[resolved] = anchors(file.read_text(encoding="utf-8"))
            if unquote(anchor) not in cache[resolved]:
                out.append(
                    (no, f"link target {target}: no heading or id '{anchor}' in {file.name}")
                )
    return out


def _check_links_resolve(page: Page, c: _Collector, root: Path, rel: str) -> None:
    if not gets_link_check(rel):
        return
    for no, message in link_problems(page, root, rel, {}):
        c.add(no, "SC30", message)


def check_script(rel: str, text: str) -> list[Problem]:
    """The label checks on a script or other text file copied into a learner's repository."""
    c = _Collector(_norm(rel))
    for no, line in enumerate(text.splitlines(), start=1):
        for check, regex in (("SC08", _RUN_ID), ("SC09", _FINDING)):
            match = regex.search(line)
            if match:
                c.add(no, check, f"id {match.group(0)}: ids go in the evidence pages")
        _ids_in_script(no, line, c)
    return sorted(set(c.items))


def _check_phrases(page: Page, c: _Collector, exempt: set[str]) -> None:
    for ln, text in _scanned(page):
        for name, regex in _BANNED:
            if f"SC14:{name}" in exempt:
                continue
            match = regex.search(text)
            if match:
                c.add(ln.no, "SC14", f"internal phrase '{match.group(0)}' ({name})")


def _check_lengths(page: Page, c: _Collector, kind: str) -> None:
    limit = _LINE_LIMITS.get(kind)
    if limit and len(page.lines) > limit:
        c.add(1, "SC11", f"{len(page.lines)} lines, limit {limit} for a {kind} page")
    if kind == "concepts":
        words = count_words(page)
        if words > CONCEPTS_WORDS:
            c.add(1, "SC11", f"{words} prose words, limit about {CONCEPTS_WORDS}")
    code_total = 0
    for fence in page.fences:
        if fence.lang in ("text", "mermaid"):
            continue
        size = len(fence.content)
        code_total += size
        if size > EXCERPT_LINES:
            c.add(fence.start, "SC11", f"code excerpt of {size} lines, limit {EXCERPT_LINES}")
    if kind == "walkthrough":
        low, high = WALKTHROUGH_CODE
        if not low <= code_total <= high:
            c.add(1, "SC11", f"{code_total} code lines in total, expected {low} to {high}")
    if kind == "instructor-guide":
        sheet = _section(page, "Class-day cheat sheet")
        if len(sheet) > CHEAT_SHEET_LINES:
            c.add(1, "SC11", f"cheat sheet of {len(sheet)} lines, limit {CHEAT_SHEET_LINES}")


def _cells(text: str) -> list[str]:
    text = text.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith("\\|"):
        text = text[:-1]
    return re.split(r"(?<!\\)\|", text)


def _check_tables(page: Page, c: _Collector) -> None:
    lines = page.lines
    index = 0
    while index < len(lines) - 1:
        head, delim = lines[index], lines[index + 1]
        if not (
            head.kind == "prose"
            and delim.kind == "prose"
            and "|" in head.masked
            and _DELIMITER.match(delim.masked)
        ):
            index += 1
            continue
        columns = len(_cells(delim.masked))
        if columns > TABLE_COLUMNS:
            c.add(head.no, "SC12", f"table of {columns} columns, at most {TABLE_COLUMNS}")
        row = index
        while row < len(lines) and lines[row].kind == "prose" and "|" in lines[row].masked:
            plain = _LINK_TARGET.sub("]", _CODE_SPAN.sub("", lines[row].prose))
            if row != index + 1 and any(len(cell.strip()) > TABLE_CELL for cell in _cells(plain)):
                c.add(lines[row].no, "SC12", f"table cell over {TABLE_CELL} characters", WARNING)
            row += 1
        index = row


def _check_output_note(page: Page, c: _Collector) -> None:
    notes = [ln.no for ln in page.lines if ln.kind == "prose" for _ in _DIFFER.finditer(ln.masked)]
    captured = [f.start for f in page.fences if f.lang == "text"]
    for ln in page.lines:
        if ln.kind == "prose" and any(
            "expected/" in src
            or "docs/images/" in src
            or src.startswith("images/")
            or ("/" not in src and not src.startswith(("http:", "https:")))
            for src, _, _ in _images(ln)
        ):
            captured.append(ln.no)
    if len(notes) > 1:
        c.add(notes[1], "SC13", f"{len(notes)} 'your output will differ' notes, at most 1")
    if captured and not notes:
        c.add(min(captured), "SC13", "captured output needs one 'your output will differ' note "
              "before it", WARNING)  # fmt: skip
    elif captured and notes[0] > min(captured):
        c.add(notes[0], "SC13", "the 'your output will differ' note goes before the first "
              "captured block or image", WARNING)  # fmt: skip
    elif notes and not captured:
        c.add(notes[0], "SC13", "no captured output on this page: the note is not needed", WARNING)


def _check_titles(page: Page, c: _Collector, rel: str) -> None:
    h1 = [ln for ln in page.lines if ln.kind == "prose" and ln.text.startswith("# ")]
    if rel.rsplit("/", 1)[-1] == "README.md" or rel.startswith("setup/"):
        first = next((ln for ln in page.lines if ln.text.strip()), None)
        title = _ROOT_TITLE if rel == "README.md" else _PAGE_TITLE
        if first is None or not title.match(first.text.rstrip()):
            want = f"# {MODULE_TITLE}" + ("" if rel == "README.md" else " - <page name>")
            c.add(first.no if first else 1, "SC15", f"the first line must be '{want}'")
    for ln in h1[1:]:
        c.add(ln.no, "SC15", "a second H1: a page has one H1")


def _check_template(page: Page, c: _Collector, rel: str, kind: str) -> None:
    for ln in page.lines:
        if ln.kind == "prose" and re.match(r"^#{4,} ", ln.text):
            c.add(ln.no, "SC16", "headings go no deeper than H3")
    want = TEMPLATES.get(kind)
    if want is None:
        return
    have = [name for _, name in _h2s(page)]
    if have[-1:] == ["Sources"]:  # the Sources list may close any page (rule 5)
        have = have[:-1]
    if have != want:
        missing = [h for h in want if h not in have]
        extra = [h for h in have if h not in want]
        detail = []
        if missing:
            detail.append("missing: " + ", ".join(missing))
        if extra:
            detail.append("not in the template: " + ", ".join(extra))
        if not detail:
            detail.append("order differs")
        c.add(1, "SC16", f"H2 headings differ from the {kind} template ({'; '.join(detail)})")
    h1 = next((ln for ln in page.lines if ln.kind == "prose" and ln.text.startswith("# ")), None)
    after = [ln.text for ln in page.lines if h1 and h1.no < ln.no <= h1.no + 5]
    final = rel == "final-project/README.md"
    if kind == "assignment-readme" and not final and not any(_TRY_IT.search(t) for t in after):
        c.add(1, "SC16", "the 'Try it yourself first' line must follow the H1")
    if kind == "reading":
        if not any(re.match(r"^Reading time: about \d+ minutes\.$", t) for t in after[:3]):
            c.add(1, "SC16", "'Reading time: about N minutes.' must follow the H1")
        if not any(ln.kind == "prose" and ln.text.startswith("Source: ") for ln in page.lines):
            c.add(1, "SC16", "a 'Source: ' line is required")
    if kind == "concepts" and "Key takeaways" in have:
        items = [ln for ln in _section(page, "Key takeaways") if ln.kind == "prose"
                 and re.match(r"^(?:[-*+]|\d+\.)\s", ln.text)]  # fmt: skip
        if len(items) != 3:
            c.add(1, "SC16", f"Key takeaways holds {len(items)} items, exactly 3 expected")
    if kind == "setup-os" and "Steps" in have:
        _check_setup_steps(_section(page, "Steps"), c)


_STEP_LABELS = ("**Why.**", "**Do this.**", "**You should see.**", "**Check it worked.**",
                "**If it fails.**")  # fmt: skip


def _check_setup_steps(lines: list[Line], c: _Collector) -> None:
    steps: list[tuple[Line, list[Line]]] = []
    for ln in lines:
        if ln.kind == "prose" and ln.text.startswith("### "):
            steps.append((ln, []))
        elif steps:
            steps[-1][1].append(ln)
    for number, (head, body) in enumerate(steps, start=1):
        match = re.match(r"^### Step (\d+): \S", head.text)
        if not match:
            c.add(head.no, "SC16", "a setup step heading reads '### Step N: <what you do>'")
        elif int(match.group(1)) != number:
            c.add(head.no, "SC16", f"step number {match.group(1)}, expected {number}")
        text = "\n".join(ln.text for ln in body if ln.kind == "prose")
        positions = [text.find(label) for label in _STEP_LABELS]
        if -1 in positions or positions != sorted(positions):
            c.add(head.no, "SC16", "a step has Why, Do this, You should see, Check it worked, "
                  "If it fails, in that order")  # fmt: skip


def _check_scenario(page: Page, c: _Collector) -> None:
    lines = page.lines
    start = next(
        (
            i
            for i, ln in enumerate(lines)
            if ln.kind == "prose" and ln.text.strip() == "## The problem"
        ),
        None,
    )
    if start is None:
        c.add(1, "SC17", "no '## The problem' section with an illustrative scenario")
        return
    index = start + 1
    while index < len(lines) and (not lines[index].text.strip() or lines[index].kind == "comment"):
        index += 1
    if index < len(lines) and _GLOSSARY.match(lines[index].text):
        while index < len(lines) and (
            lines[index].text.startswith(">") or not lines[index].text.strip()
        ):
            index += 1
    if index >= len(lines) or lines[index].kind != "prose":
        c.add(lines[start].no, "SC17", "'## The problem' starts with '**Illustrative scenario.**'")
        return
    first = lines[index]
    if not first.text.startswith("**Illustrative scenario.**"):
        c.add(first.no, "SC17", "the problem starts with '**Illustrative scenario.**'")
        return
    paragraph = []
    while index < len(lines) and lines[index].kind == "prose" and lines[index].text.strip():
        paragraph.append(lines[index].masked)
        index += 1
    if re.search(r"\d", " ".join(paragraph)):
        c.add(first.no, "SC17", "the scenario holds a number; a scenario is a story", WARNING)


def _check_glossary(page: Page, c: _Collector) -> None:
    lines = page.lines
    boxes = [i for i, ln in enumerate(lines) if ln.kind == "prose" and _GLOSSARY.match(ln.text)]
    for i in boxes[1:]:
        c.add(lines[i].no, "SC18", "a second glossary box: one per page")
    for i in boxes:
        seen: set[str] = set()
        j = i + 1
        while j < len(lines) and lines[j].text.startswith(">"):
            match = _GLOSSARY_ITEM.match(lines[j].text)
            if match:
                term = match.group("term").strip().casefold()
                if term in seen:
                    c.add(lines[j].no, "SC18", f"'{match.group('term')}' is defined twice")
                seen.add(term)
            j += 1


# The root README tells its story without the label (STYLE, 2026-10-18).
_SCENARIO_TYPES = {"section-readme", "concepts", "demo-readme", "assignment-readme"}


def check_text(rel: str, text: str, root: Path) -> list[Problem]:
    """Every problem in one public page `rel` (relative to `root`) with content `text`."""
    rel = _norm(rel)
    if not rel.endswith(".md"):
        return check_script(rel, text)
    page = parse_page(text)
    c = _Collector(rel)
    agent = is_agent_file(rel)
    _check_images(page, c, root, rel, agent)
    _check_alt_text(page, c)
    _check_labels(page, c, rel)
    _check_links_resolve(page, c, root, rel)
    if not agent:
        kind = doc_type(rel)
        exempt = exemptions(rel)
        _check_markers(page, c)
        _check_prose_values(page, c)
        _check_fences(page, c)
        _check_ids(page, c, rel)
        _check_lengths(page, c, kind)
        _check_tables(page, c)
        _check_output_note(page, c)
        _check_phrases(page, c, exempt)
        _check_titles(page, c, rel)
        _check_template(page, c, rel, kind)
        if kind in _SCENARIO_TYPES:
            _check_scenario(page, c)
        _check_glossary(page, c)
    allowed: dict[int, set[str]] = {}
    for ln in page.lines:
        match = _ALLOW.search(ln.text)
        if match:
            allowed.setdefault(ln.no, set()).add(match.group(1))
            if not match.group(2).strip():
                c.add(ln.no, "SC00", f"allow marker for {match.group(1)} needs a reason")
            if ln.text.lstrip().startswith("<!--"):
                fence = next((f for f in page.fences if f.start == ln.no + 1), None)
                if fence is not None:
                    for no in range(fence.start, (fence.end or fence.start) + 1):
                        allowed.setdefault(no, set()).add(match.group(1))
    exempt = exemptions(rel)
    return sorted(
        p for p in set(c.items) if p.check not in exempt and p.check not in allowed.get(p.line, ())
    )


def allowed_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if _ALLOW.search(line))


@dataclass
class Report:
    files: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)
    allowed: int = 0


def run(root: Path, paths: list[str], folders: bool | None = None) -> Report:
    """Check `paths` (default: every public page). The folder checks (SC19, SC20) run with the
    default targets, or when `folders` is True."""
    root = root.resolve()
    report = Report()
    candidates: list[tuple[str, Path]] = []
    if not paths:
        candidates = [(p.relative_to(root).as_posix(), p) for p in default_files(root)]
    for given in paths:
        path = Path(given) if Path(given).is_absolute() else root / given
        if not path.exists():
            report.missing.append(given)
            continue
        for file in _walk(path) if path.is_dir() else [path]:
            resolved = file.resolve()
            if not resolved.is_relative_to(root):
                report.skipped.append(str(file))
                continue
            candidates.append((resolved.relative_to(root).as_posix(), resolved))
    seen: set[str] = set()
    for rel, file in candidates:
        if rel in seen:
            continue
        seen.add(rel)
        if not is_checked(rel):
            report.skipped.append(rel)
            continue
        text = file.read_text(encoding="utf-8")
        report.files.append(rel)
        report.problems += check_text(rel, text, root)
        report.allowed += allowed_lines(text)
    if folders if folders is not None else not paths:
        report.problems += folder_problems(root)
    report.problems.sort()
    return report


def check_paths(root: Path, paths: list[str]) -> list[Problem]:
    """Every problem in the public course pages among `paths` (default: all of them); the folder
    checks are left to `run` and their own functions."""
    return run(root, paths, folders=False).problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("paths", nargs="*", help="files or folders (default: every public page)")
    parser.add_argument("--list-checks", action="store_true", help="list the checks and exit")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--strict", action="store_true", help="warnings fail the run too")
    mode.add_argument("--warn-only", action="store_true", help="report only; exit 0")
    parser.add_argument("--root", type=Path, default=REPO, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.list_checks:
        for check, (name, severity) in CHECKS.items():
            print(f"{check} {severity:<7} {name}")
        return 0
    report = run(args.root, args.paths)
    for rel in report.skipped:
        print(f"- {rel}: skipped (not a public course file)")
    for given in report.missing:
        print(f"x {given}: not found")
    for p in report.problems:
        mark = "x" if p.severity == ERROR else "!"
        print(f"{mark} {p.path}:{p.line}: {p.check} {p.message}")
    errors = sum(1 for p in report.problems if p.severity == ERROR)
    warnings = len(report.problems) - errors
    print(
        f"{len(report.files)} files checked, {errors} errors, {warnings} warnings, "
        f"{report.allowed} allowed lines"
    )
    if report.missing:
        return 2
    if args.warn_only:
        return 0
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
