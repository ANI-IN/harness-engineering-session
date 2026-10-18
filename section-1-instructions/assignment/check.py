"""Self-check for assignment A1 (Instructions). No API keys, no Docker, no model calls.

Usage (from the repository root):

    uv run python section-1-instructions/assignment/check.py [--work DIR] [--allow-pending]

DIR is your work folder (default: assignment/starter): `instructions/` (your restructured tree),
`checker/` (your check_docs.py and its tests), `ab-report.md`, and `live/` (the live evidence of
your A/B, collected by live_evidence.py). The original 900-line file is always read from
assignment/starter/original/AGENTS.md.

Prints one PASS or FAIL line per check, each FAIL with what to fix, then a summary line. Exits 0
when every check passes, 1 otherwise. `--allow-pending` accepts a well-formed [[PENDING: ...]]
marker in place of A/B values and live evidence; it exists for the reference solution, whose A/B
has not been captured yet. The instructor's grader runs these checks plus hidden ones and prints
the score.
"""

from __future__ import annotations

import argparse
import importlib.util
import posixpath
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from urllib.parse import unquote


def _course_root(assignment: Path) -> Path:
    """The course repository root: the nearest folder above `assignment` with a pyproject.toml
    (found by that marker, not a fixed depth), else the folder that holds the section folder."""
    for folder in assignment.parents:
        if (folder / "pyproject.toml").is_file():
            return folder
    return assignment.parents[1]


ASSIGNMENT = Path(__file__).resolve().parent
REPO = _course_root(ASSIGNMENT)
STARTER = ASSIGNMENT / "starter"
ORIGINAL = STARTER / "original" / "AGENTS.md"
PRODUCT = REPO / "platform" / "teamtrack"


def _load_live() -> ModuleType:
    """live_evidence.py, loaded by path (the submodule folder name is not a package name)."""
    name = "a1_live"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ASSIGNMENT / "live_evidence.py")
        assert spec is not None and spec.loader is not None
        sys.modules[name] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sys.modules[name])
    return sys.modules[name]


live = _load_live()

# A1's layout (F-a-30) as the course's instructions layer places it.
REQUIRED = [
    "AGENTS.md",
    "ARCHITECTURE.md",
    "docs/SECURITY.md",
    "docs/RELIABILITY.md",
    "docs/QUALITY_SCORE.md",
    "docs/PLANS.md",
    "docs/design-docs/index.md",
    "docs/product-specs/index.md",
]
MAP_LINES = (30, 120)  # "roughly 100 lines" (A1, F-a-28)
TEMPLATE_HEADINGS = ["## When to use", "## Steps", "## Checks before you finish"]
REPORT_SECTIONS = [
    "Setup",
    "Results",
    "Links",
    "Cost and traces",
    "Reading the result",
    "Limits",
]
MAX_COST_USD = 2.50  # course budget: A1 at most $2.50
MAX_TRACES = 150  # course budget: A1 at most 150 traces
TIMEOUT_S = 300

PENDING = live.PENDING
REFERENCE = re.compile(r"(?<![\w.])(R[1-9](?:\.\d+)?|CV-\d{2})(?!\w)")
_FENCE = re.compile(r"^\s*(```|~~~)")
_SPAN = re.compile(r"`([^`\n]+)`")
_LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]*)")
_REF_DEF = re.compile(r"^\s{0,3}\[[^\]^][^\]]*\]:\s*(\S+)")
_PATH = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*/?")
_PATH_EXT = (".md", ".txt", ".py", ".toml", ".ini", ".json", ".sh", ".html", ".css")
_PLACEHOLDER = re.compile(r"<[A-Z][^<>\n]*>")


@dataclass(frozen=True)
class Result:
    name: str
    ok: bool
    detail: str = ""
    score: float = 1.0  # share of the check met, 0..1 (the grader weights it)


def _result(name: str, score: float, detail: str = "") -> Result:
    return Result(name, score >= 1.0, "" if score >= 1.0 else detail, max(0.0, min(1.0, score)))


# -- text helpers ---------------------------------------------------------------------------------


def _unfenced(text: str) -> list[str]:
    """Lines outside fenced code blocks (fenced lines become empty, so numbering stays)."""
    out: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        match = _FENCE.match(line)
        if fence is None and match:
            fence = match.group(1)
            out.append("")
        elif fence is not None:
            if line.strip().startswith(fence):
                fence = None
            out.append("")
        else:
            out.append(line)
    return out


def _normalise(text: str) -> str:
    text = text.replace("**", "").replace("`", "").replace("’", "'")
    return re.sub(r"\s+", " ", text).lower()


def _looks_like_path(span: str) -> bool:
    span = span.strip()
    if span.startswith("/") or not _PATH.fullmatch(span):
        return False
    return "/" in span or span.endswith(_PATH_EXT)


def _docs(tree: Path) -> list[str]:
    files = [p for p in tree.rglob("*") if p.is_file() and p.suffix in (".md", ".txt")]
    return sorted(p.relative_to(tree).as_posix() for p in files)


def _pointers(text: str) -> list[str]:
    """Link targets, reference definitions, and path-like code spans, without anchors."""
    found: list[str] = []
    for line in _unfenced(text):
        bare = _SPAN.sub(lambda m: " " * len(m.group(0)), line)
        found += [m.group(1) for m in _LINK.finditer(bare)]
        ref = _REF_DEF.match(bare)
        if ref:
            found.append(ref.group(1))
        found += [s.strip() for s in _SPAN.findall(line) if _looks_like_path(s)]
    cleaned = []
    for target in found:
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
            continue
        target = unquote(target.split("#", 1)[0])
        if target:
            cleaned.append(target)
    return cleaned


def _exists(rel_file: str, span: str, tree: Path, product: Path) -> bool:
    folder = posixpath.dirname(rel_file)
    for rel in (span, posixpath.join(folder, span)):
        norm = posixpath.normpath(rel)
        if norm == ".." or norm.startswith("../"):
            continue
        if any((base / norm).exists() for base in (tree, product)):
            return True
    return False


# -- the tree -------------------------------------------------------------------------------------


def check_layout(tree: Path) -> Result:
    missing = [rel for rel in REQUIRED if not (tree / rel).is_file()]
    detail = f"missing {', '.join(missing)}; follow A1's layout (SPEC.md, 'Files you must produce')"
    return _result("layout", (len(REQUIRED) - len(missing)) / len(REQUIRED), detail)


def check_map_length(tree: Path) -> Result:
    path = tree / "AGENTS.md"
    if not path.is_file():
        return _result("map-length", 0, "AGENTS.md is missing")
    text = path.read_text(encoding="utf-8")
    lines = len(text.splitlines())
    low, high = MAP_LINES
    if "TODO" in text:
        return _result("map-length", 0, "AGENTS.md still holds the starter TODO stub")
    detail = f"AGENTS.md has {lines} lines; a map is roughly 100 lines ({low} to {high} allowed)"
    return _result("map-length", 1.0 if low <= lines <= high else 0.0, detail)


def check_map_reach(tree: Path) -> Result:
    """Every .md and .txt file in the tree can be reached from AGENTS.md by following pointers."""
    files = set(_docs(tree))
    if "AGENTS.md" not in files:
        return _result("map-reach", 0, "AGENTS.md is missing")
    seen = {"AGENTS.md"}
    queue = ["AGENTS.md"]
    while queue:
        current = queue.pop()
        for target in _pointers((tree / current).read_text(encoding="utf-8")):
            for rel in (posixpath.join(posixpath.dirname(current), target), target):
                norm = posixpath.normpath(rel).rstrip("/")
                hits = {f for f in files if f == norm or f.startswith(norm + "/")}
                for hit in hits - seen:
                    seen.add(hit)
                    queue.append(hit)
    orphans = sorted(files - seen)
    detail = f"not reachable from AGENTS.md: {', '.join(orphans)}; link each from the map or a doc"
    return _result("map-reach", len(seen & files) / len(files), detail)


def check_no_overwrite(tree: Path, product: Path) -> Result:
    """The layer copies the tree over the workspace; it must not replace a TeamTrack file."""
    clashes = sorted(
        p.relative_to(tree).as_posix()
        for p in tree.rglob("*")
        if p.is_file() and (product / p.relative_to(tree)).exists()
    )
    detail = f"would overwrite TeamTrack files: {', '.join(clashes)}; rename or move them"
    return _result("no-overwrite", 0.0 if clashes else 1.0, detail)


def new_facts(tree: Path, product: Path, original: Path) -> list[str]:
    """Code spans in the tree that are neither in the original file nor an existing path."""
    known = _normalise(original.read_text(encoding="utf-8"))
    unknown: list[str] = []
    for rel in _docs(tree):
        if not rel.endswith(".md"):
            continue
        for line in _unfenced((tree / rel).read_text(encoding="utf-8")):
            for span in _SPAN.findall(line):
                if _normalise(span).strip() in known:
                    continue
                if _looks_like_path(span) and _exists(rel, span.strip(), tree, product):
                    continue
                unknown.append(f"{rel}: `{span}`")
    return unknown


def check_no_new_facts(tree: Path, product: Path, original: Path) -> Result:
    unknown = new_facts(tree, product, original)
    detail = (
        f"{len(unknown)} code spans are not in the original file and are not existing paths: "
        + "; ".join(unknown[:8])
        + ("; ..." if len(unknown) > 8 else "")
        + " (restructure, do not add facts: the A/B must stay fair)"
    )
    # Worth 3 points in the grader: one point off per unknown span.
    return _result("no-new-facts", 1.0 - len(unknown) / 3 if unknown else 1.0, detail)


def check_tree(tree: Path, product: Path = PRODUCT, original: Path = ORIGINAL) -> list[Result]:
    if not tree.is_dir():
        missing = f"{shown(tree)} is not a folder"
        names = ["layout", "map-length", "map-reach", "no-overwrite", "no-new-facts"]
        return [_result(name, 0, missing) for name in names]
    layout = check_layout(tree)
    results = [layout, check_map_length(tree)]
    # Reach and overwrite checks only mean something once the layout exists.
    gate = 1.0 if layout.score >= 0.5 else 0.0
    for result in (check_map_reach(tree), check_no_overwrite(tree, product)):
        score = result.score * gate
        detail = result.detail or "build the layout first"
        results.append(_result(result.name, score, detail))
    results.append(check_no_new_facts(tree, product, original))
    return results


# -- the skill ------------------------------------------------------------------------------------


def check_skill(tree: Path) -> list[Result]:
    from shipharness.runner.skills_loader import parse_frontmatter
    from shipharness.skills_cli.validate import validate_skill

    skills_dir = tree / ".agents" / "skills"
    folders = sorted(p for p in skills_dir.iterdir() if p.is_dir()) if skills_dir.is_dir() else []
    names = ["skill-valid", "skill-frontmatter", "skill-sections", "skill-linked", "skill-cites"]
    if len(folders) != 1:
        found = ", ".join(p.name for p in folders) or "none"
        detail = f"need exactly one skill in .agents/skills/ (found: {found})"
        return [_result(name, 0, detail) for name in names]
    folder = folders[0]
    report = validate_skill(folder)
    problems = report.errors + report.warnings
    valid = _result(
        "skill-valid",
        0.0 if problems else 1.0,
        "; ".join(problems) + f" (run: uv run shipharness skills validate {shown(folder)})",
    )
    skill_md = folder / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8") if skill_md.is_file() else ""
    fields = parse_frontmatter(text) or {}
    name, description = fields.get("name", ""), fields.get("description", "")
    good_name = name == folder.name and name != "skill-template"
    front = _result(
        "skill-frontmatter",
        (0.5 if good_name else 0.0) + (0.5 if "use when" in description.lower() else 0.0),
        "rename the copy of skills/skill-template and set name to the folder name; start the "
        "'when' part of the description with 'Use when'",
    )
    missing = [h for h in TEMPLATE_HEADINGS if h not in text]
    placeholders = _PLACEHOLDER.findall(text.split("---", 2)[-1])
    sections = _result(
        "skill-sections",
        0.0 if missing or placeholders else 1.0,
        f"template sections missing: {missing}; placeholders left: {placeholders[:3]}",
    )
    agents = tree / "AGENTS.md"
    map_text = agents.read_text(encoding="utf-8") if agents.is_file() else ""
    linked = _result(
        "skill-linked",
        1.0 if f".agents/skills/{folder.name}/SKILL.md" in map_text else 0.0,
        f"AGENTS.md does not point to .agents/skills/{folder.name}/SKILL.md",
    )
    cites = _result(
        "skill-cites",
        1.0 if REFERENCE.search(text.split("---", 2)[-1]) else 0.0,
        "the skill's steps cite no rule tag (for example R1.1); cite the rules each step serves",
    )
    return [valid, front, sections, linked, cites]


# -- the checker ----------------------------------------------------------------------------------


def run_checker(
    checker: Path, original: Path, tree: Path, product: Path
) -> subprocess.CompletedProcess[str]:
    argv = [sys.executable, str(checker), "--original", str(original), "--tree", str(tree)]
    return subprocess.run(
        [*argv, "--product", str(product)],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
        cwd=REPO,
    )


def check_checker(work: Path, original: Path = ORIGINAL, product: Path = PRODUCT) -> list[Result]:
    checker_dir = work / "checker"
    checker = checker_dir / "check_docs.py"
    if not checker.is_file():
        detail = f"{shown(checker)} is missing"
        return [_result("checker-tests", 0, detail), _result("checker-clean", 0, detail)]
    tests = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(checker_dir)],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
        cwd=REPO,
    )
    summary = (tests.stdout.strip().splitlines() or ["no output"])[-1]
    results = [
        _result(
            "checker-tests",
            1.0 if tests.returncode == 0 else 0.0,
            f"pytest {shown(checker_dir)}: {summary}",
        )
    ]
    if tests.returncode != 0:
        detail = "make the checker tests pass first: a checker that finds nothing proves nothing"
        return [*results, _result("checker-clean", 0, detail)]
    run = run_checker(checker, original, work / "instructions", product)
    errors = [line for line in run.stdout.splitlines() if line.startswith("ERROR ")]
    results.append(
        _result(
            "checker-clean",
            1.0 if run.returncode == 0 else 0.0,
            f"your checker exits {run.returncode} on your tree; first problems: "
            + "; ".join(errors[:5]),
        )
    )
    return results


# -- the A/B report -------------------------------------------------------------------------------


def _sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = ""
        elif current is not None:
            sections[current] += line + "\n"
    return sections


def _words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text))


def check_report(path: Path, allow_pending: bool = False) -> list[Result]:
    names = ["report-sections", "report-command", "report-results", "report-links"]
    names += ["report-cost", "report-reading"]
    if not path.is_file():
        return [_result(name, 0, f"{shown(path)} is missing") for name in names]
    text = path.read_text(encoding="utf-8")
    sections = _sections(text)

    def pending(section: str) -> bool:
        return allow_pending and bool(PENDING.search(sections.get(section, "")))

    missing = [s for s in REPORT_SECTIONS if s not in sections]
    todo = "TODO" in text
    problems = [f"missing sections: {', '.join(missing)}"] if missing else []
    problems += ["TODO markers are left in the report"] if todo else []
    results = [
        _result(
            "report-sections",
            0.0 if todo else 1 - len(missing) / len(REPORT_SECTIONS),
            "; ".join(problems) + f" (sections needed: {', '.join(REPORT_SECTIONS)})",
        )
    ]

    setup = sections.get("Setup", "")
    command = re.search(r"uv run shipharness experiments[^`\n]*", setup)
    cmd = command.group(0) if command else ""
    wanted = ["--split section-1", "--k 3", "--layers instructions"]
    command_ok = bool(command) and all(w in cmd for w in wanted) and "TODO" not in cmd
    command_ok = command_ok and bool(re.search(r"--batch [A-Za-z0-9_.-]+", cmd))
    commit = re.search(r"Instructions tree commit: [0-9a-f]{7,40}\b", setup)
    runs_match = re.search(r"Runs per arm: (\d+)", setup)
    values_ok = bool(commit and runs_match) or pending("Setup")
    results.append(
        _result(
            "report-command",
            (0.5 if command_ok else 0.0) + (0.5 if values_ok else 0.0),
            "Setup needs the exact command (--split section-1 --k 3 --layers instructions "
            "--batch <name>), 'Instructions tree commit: <sha>', and 'Runs per arm: <n>'",
        )
    )

    runs = int(runs_match.group(1)) if runs_match else None
    rows = [r for r in sections.get("Results", "").splitlines() if r.strip().startswith("|")]
    ok_rows = 0
    for measure in ("R1", "R3"):
        row = next((r for r in rows if r.strip("| ").startswith(measure)), None)
        if row is None:
            continue
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        counts = [re.fullmatch(r"(\d+)/(\d+)", c) for c in cells[1:3]]
        good = len(cells) >= 3 and "%" not in row and all(counts)
        good = good and all(
            int(m.group(1)) <= int(m.group(2)) == runs for m in counts if m is not None
        )
        if good or pending("Results"):
            ok_rows += 1
    results.append(
        _result(
            "report-results",
            ok_rows / 2,
            "Results needs an R1 row and an R3 row, each with 'failing/runs' counts per arm "
            "(for example 3/24), runs equal to 'Runs per arm', and no percentages",
        )
    )

    links = set(re.findall(r"https://smith\.langchain\.com/\S+", sections.get("Links", "")))
    results.append(
        _result(
            "report-links",
            1.0 if len(links) >= 2 or pending("Links") else 0.0,
            "Links needs the two LangSmith experiment URLs (bare and harness)",
        )
    )

    costs = sections.get("Cost and traces", "")
    cost = re.search(r"Cost: \$(\d+(?:\.\d+)?)", costs)
    traces = re.search(r"Traces: (\d+)", costs)
    budget_ok = bool(cost and traces)
    budget_ok = budget_ok and float(cost.group(1)) <= MAX_COST_USD  # type: ignore[union-attr]
    budget_ok = budget_ok and int(traces.group(1)) <= MAX_TRACES  # type: ignore[union-attr]
    results.append(
        _result(
            "report-cost",
            1.0 if budget_ok or pending("Cost and traces") else 0.0,
            f"'Cost: $<x>' at most {MAX_COST_USD:.2f} and 'Traces: <n>' at most {MAX_TRACES}",
        )
    )

    reading = sections.get("Reading the result", "")
    limits = sections.get("Limits", "")
    reading_ok = _words(reading) >= 60 and "R1" in reading and "R3" in reading
    reading_ok = reading_ok and "TODO" not in reading
    limits_ok = _words(limits) >= 20 and "TODO" not in limits
    results.append(
        _result(
            "report-reading",
            (0.5 if reading_ok else 0.0) + (0.5 if limits_ok else 0.0),
            "Reading the result: at least 60 words that discuss R1 and R3; Limits: at least 20",
        )
    )
    return results


# -- leftovers ------------------------------------------------------------------------------------


def check_todos(work: Path) -> Result:
    places = [work / "ab-report.md", work / "checker" / "check_docs.py"]
    if (work / "instructions").is_dir():
        places += sorted(p for p in (work / "instructions").rglob("*") if p.is_file())
    found = []
    for path in places:
        if path.is_file() and "TODO" in path.read_text(encoding="utf-8", errors="replace"):
            found.append(path.relative_to(work).as_posix())
    detail = f"TODO markers left in: {', '.join(found)}"
    return _result("todo", 0.0 if found else 1.0, detail)


# -- all checks -----------------------------------------------------------------------------------


def run_checks(
    work: Path,
    *,
    allow_pending: bool = False,
    original: Path = ORIGINAL,
    product: Path = PRODUCT,
) -> list[Result]:
    tree = work / "instructions"
    results = check_tree(tree, product, original)
    results += check_skill(tree)
    results += check_checker(work, original, product)
    results += check_report(work / "ab-report.md", allow_pending)
    results += [_result(*item) for item in live.check_live(work, allow_pending=allow_pending)]
    results.append(check_todos(work))
    return results


def shown(path: Path) -> str:
    """A path relative to the repository when it is inside it (keeps host paths out of logs)."""
    return path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A1 self-check")
    parser.add_argument("--work", type=Path, default=STARTER)
    parser.add_argument("--allow-pending", action="store_true")
    args = parser.parse_args(argv)
    work = args.work.resolve()
    print(f"A1 self-check: {shown(work)}")
    results = run_checks(work, allow_pending=args.allow_pending)
    for result in results:
        print(f"PASS {result.name}" if result.ok else f"FAIL {result.name}: {result.detail}")
    passed = sum(r.ok for r in results)
    print(f"self-check: {passed} of {len(results)} checks pass")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
