"""Checks for the live evidence of A4 (used by the visible tests and by the grader).

The submission keeps the evidence of two live runs in `live/` (paths relative to the submission):

    live/testgen.txt            a `$ <command>` line, then everything `shipharness testgen ...
                                --out <dir>` printed (summary and `Cost:` line)
    live/testgen-report.json    <dir>/testgen-report.json after
                                `python -m a4_verification.apply_filter ... --update-report`
    live/ab.txt                 a `$ <command>` line, then everything `shipharness ab --section
                                demo-4 --feature F4 --purpose assignment --no-preview` printed
                                (`Cost:` line included)
    live/scores/<run_id>.json   the two ScoreRecords that A/B wrote to `exports/scores/`

Nothing here calls a model, needs a key, or re-runs anything: the files are parsed, validated
against the shipharness models (`FilterResult`, `ScoreRecord`), and checked against each other,
the command, the course model, and the class cost caps (the defaults in
`src/shipharness/config/settings.py`). Every check returns a list of problems; empty means valid.
"""

from __future__ import annotations

import ast
import json
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from shipharness.ab.demo import SECTION_STACKS
from shipharness.ab.score import ScoreRecord
from shipharness.config import Settings
from shipharness.filters.models import FilterResult
from shipharness.filters.pipeline import kept_tests

LIVE = "live"
TESTGEN_TXT = f"{LIVE}/testgen.txt"
TESTGEN_REPORT = f"{LIVE}/testgen-report.json"
AB_TXT = f"{LIVE}/ab.txt"
SCORES = f"{LIVE}/scores"


def _default(name: str) -> Any:
    return Settings.model_fields[name].default


MODEL = _default("openai_model")  # the course agent model
REVIEW_MODEL = _default("openai_eval_model")  # the reviewer's model in `shipharness ab`
RUN_CAP = _default("max_run_cost_usd")  # MAX_RUN_COST_USD, per arm and per testgen run
REVIEW_CAP = _default("max_review_cost_usd")  # MAX_REVIEW_COST_USD, per arm review
COMMAND_CAP = _default("max_batch_cost_usd")  # the per-command cap
EPS = 1e-6

AB_SECTION, AB_FEATURE, AB_VARIANT, AB_CHECKPOINT = "demo-4", "F4", "canonical", "m1-s4-start"
# `--purpose assignment` traces to the assignments project; the default, class, needs
# SHIPHARNESS_CLASS_DATE and traces into the class project (`_trace_target` in ab/commands.py).
AB_PURPOSE = "assignment"
AB_COMMAND = (
    f"shipharness ab --section {AB_SECTION} --feature {AB_FEATURE} --purpose {AB_PURPOSE} "
    "--no-preview"
)
HARNESS_LAYERS = sorted(SECTION_STACKS[AB_SECTION])

RUN_ID = re.compile(r"^r-\d{8}-\d{6}-[0-9a-f]{6}$")
AB_ID = re.compile(r"^ab-\d{8}-\d{6}-[0-9a-f]{6}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
# Commits `m1-s4-start` named before a disclosed tag move (docs/evidence/general.md, "Checkpoint
# tags moved after the harness rename"; the commits stay under refs/archive/checkpoints-*). A
# recorded run keeps the commit it ran on, so its checkpoint_sha is compared with these too.
EARLIER_CHECKPOINTS = (
    "a9d6be25aca552298374470536d6ef417065a1a7",  # 2026-10-17 build; the reference run's records
    "d0b98d03eb26fd29dc706bbf2b528824384d81a5",  # 2026-10-17 rebuild, same TeamTrack tree
)
COST = re.compile(r"^Cost: \$(\d+\.\d+) \((.*)\)\s*$")
TESTGEN_SUMMARY = re.compile(r"^testgen (\S+): (\S+); kept (\d+) of (\d+) proposed tests\s*$")
TESTGEN_NOTE = re.compile(r"^testgen, model (\S+)$")
# Optional suffix after the layers, e.g. ", profile=standard" (shipharness since 2026-10-17).
# The feature is "F4" before 2026-10-18 and "Feature 4: <name>" since.
AB_LINE = re.compile(
    r"^A/B (\S+) \((F\d+|Feature \d+: [^,]+), layers=(\[[^\]]*\])(?:, [^)]*)?\)\s*$"
)
# The arm line: "claim=done ..." before 2026-10-18, "agent said done · ..." (plain words) on
# 2026-10-18, "agent said: done (build) · not done (test phase) · ..." (per phase) since.
AB_RECORD = re.compile(r"^\s+(bare|harness)\s+(\S+(?: \S+)*?)\s+(?:claim=|agent (?:said|made)[: ])")
# The note of `cost_line` in src/shipharness/ab/runtime.py; the build part came later, so both
# forms are accepted.
AB_NOTE = re.compile(
    r"^this command: (.*?); (?:session|experiment) \$\d+\.\d+ of \$\d+\.\d+"
    r"(?:; build \$\d+\.\d+ of \$\d+\.\d+ \(\$-?\d+\.\d+ left\))?$"
)
MODEL_COST = re.compile(r"^(\S+) \$(\d+\.\d+)$")
REQUIRED_REPORT_KEYS = (
    "run_id",
    "status",
    "unsandboxed",
    "baseline_includes_doctests",
    "kept",
    "not_evaluated",
    "results",
)


# --- shared readers ------------------------------------------------------------------------------


class Transcript:
    """A `$ <command>` line (continuations with a trailing backslash joined) and the output."""

    def __init__(self, root: Path, rel: str) -> None:
        self.rel = rel
        self.problems: list[str] = []
        self.command = ""
        self.tokens: list[str] = []
        self.output: list[str] = []
        path = root / rel
        if not path.is_file():
            self.problems.append(f"{rel}: missing (the command line and its printed output)")
            return
        lines = path.read_text(encoding="utf-8").splitlines()
        start = next((i for i, line in enumerate(lines) if line.startswith("$ ")), None)
        if start is None:
            self.problems.append(f"{rel}: no command line (a line starting with '$ ')")
            return
        command = lines[start][2:].strip()
        end = start
        while command.endswith("\\") and end + 1 < len(lines):
            end += 1
            command = command[:-1].rstrip() + " " + lines[end].strip()
        self.command = command
        self.output = lines[end + 1 :]
        try:
            self.tokens = shlex.split(command)
        except ValueError as exc:
            self.problems.append(f"{rel}: cannot parse the command ({exc}): {command}")

    @property
    def ok(self) -> bool:
        return not self.problems

    def after(self, subcommand: str) -> list[str] | None:
        """The arguments after `shipharness <subcommand>`, or None when the command is another."""
        for i, token in enumerate(self.tokens[:-1]):
            if Path(token).name == "shipharness" and self.tokens[i + 1] == subcommand:
                return self.tokens[i + 2 :]
        return None

    def matches(self, pattern: re.Pattern[str]) -> list[re.Match[str]]:
        return [m for m in (pattern.match(line) for line in self.output) if m]


def _cost(t: Transcript) -> tuple[list[str], tuple[float, str] | None]:
    found = t.matches(COST)
    if len(found) != 1:
        return [f"{t.rel}: expected one `Cost: $...` line, found {len(found)}"], None
    return [], (float(found[0].group(1)), found[0].group(2))


def _load_json(root: Path, rel: str) -> tuple[list[str], Any]:
    path = root / rel
    if not path.is_file():
        return [f"{rel}: missing"], None
    try:
        return [], json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [f"{rel}: not valid JSON ({exc})"], None


def _errors(exc: ValidationError) -> str:
    parts = [f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors()[:3]]
    return "; ".join(parts)


# --- testgen run ---------------------------------------------------------------------------------


def _report_rows(report: dict[str, Any]) -> tuple[list[str], list[FilterResult]]:
    problems: list[str] = []
    rows: list[FilterResult] = []
    results = report.get("results")
    if not isinstance(results, list):
        return [f"{TESTGEN_REPORT}: `results` is not a list"], []
    for i, raw in enumerate(results):
        try:
            row = FilterResult.model_validate(raw)
        except ValidationError as exc:
            problems.append(
                f"{TESTGEN_REPORT}: results[{i}] is not a filter result: {_errors(exc)}"
            )
            continue
        if not 1 <= row.filter <= 6:
            problems.append(f"{TESTGEN_REPORT}: results[{i}] has filter {row.filter} (1-6)")
        rows.append(row)
    return problems, rows


def testgen_run_problems(root: Path) -> list[str]:
    """`live/testgen.txt` and the testgen part of `live/testgen-report.json`."""
    t = Transcript(root, TESTGEN_TXT)
    problems = list(t.problems)
    summary = None
    if t.ok:
        args = t.after("testgen")
        if args is None:
            problems.append(f"{t.rel}: the command is not `shipharness testgen ...`: {t.command}")
        elif not any(a == "--out" or a.startswith("--out=") for a in args):
            problems.append(f"{t.rel}: the command has no --out <dir> (the report comes from it)")
        found = t.matches(TESTGEN_SUMMARY)
        if len(found) != 1:
            problems.append(
                f"{t.rel}: expected one `testgen <run_id>: <status>; kept N of M proposed tests` "
                f"line, found {len(found)}"
            )
        else:
            summary = found[0]
        cost_problems, cost = _cost(t)
        problems += cost_problems
        if cost is not None:
            spent, note = cost
            note_match = TESTGEN_NOTE.match(note)
            model = note_match.group(1) if note_match else None
            if model != MODEL:
                problems.append(f"{t.rel}: the cost line names model {model}; use {MODEL}")
            if spent > RUN_CAP + EPS:
                problems.append(
                    f"{t.rel}: cost ${spent:.6f} is over MAX_RUN_COST_USD ${RUN_CAP:.2f}"
                )
            if spent <= 0:
                problems.append(f"{t.rel}: cost $0: no model call was made, not a live run")
    load_problems, report = _load_json(root, TESTGEN_REPORT)
    problems += load_problems
    if not isinstance(report, dict):
        if report is not None:
            problems.append(f"{TESTGEN_REPORT}: not a JSON object")
        return problems
    missing = [key for key in REQUIRED_REPORT_KEYS if key not in report]
    if missing:
        problems.append(f"{TESTGEN_REPORT}: missing keys {missing} (copy the file testgen wrote)")
        return problems
    run_id = str(report["run_id"])
    if not RUN_ID.match(run_id):
        problems.append(f"{TESTGEN_REPORT}: run_id {run_id!r} is not a shipharness run id")
    row_problems, rows = _report_rows(report)
    problems += row_problems
    kept = [str(x) for x in report["kept"]] if isinstance(report["kept"], list) else []
    if not row_problems and kept != kept_tests([r for r in rows if r.filter <= 5]):
        problems.append(f"{TESTGEN_REPORT}: `kept` does not follow from the filters 1-5 rows")
    if summary is not None:
        if summary.group(1) != run_id:
            problems.append(
                f"{t.rel}: run id {summary.group(1)} differs from the report's run id {run_id}"
            )
        if summary.group(2) != str(report["status"]):
            problems.append(
                f"{t.rel}: status {summary.group(2)} differs from the report's {report['status']}"
            )
        if int(summary.group(3)) != len(kept):
            problems.append(
                f"{t.rel}: says kept {summary.group(3)}, the report lists {len(kept)} kept tests"
            )
    return problems


# --- filter 6 in the report ----------------------------------------------------------------------


def filter6_problems(root: Path) -> list[str]:
    """The report shows filter 6 run over every test testgen kept (`--update-report`)."""
    problems, report = _load_json(root, TESTGEN_REPORT)
    if not isinstance(report, dict):
        return problems or [f"{TESTGEN_REPORT}: not a JSON object"]
    rows = [r for r in report.get("results", []) if isinstance(r, dict)]
    f6 = [r for r in rows if r.get("filter") == 6]
    if not f6 and "filter6" not in report:
        return [
            f"{TESTGEN_REPORT}: no filter-6 rows and no `filter6` object: run "
            "`python -m a4_verification.apply_filter --repo <repo> --kept <out> --existing "
            "<tests> --update-report`, then copy the report"
        ]
    kept = [str(x) for x in report.get("kept", [])]
    if not kept:
        return [
            f"{TESTGEN_REPORT}: testgen kept no test, so filter 6 never ran: run testgen again "
            "(another module or target) within the budget"
        ]
    ids = [str(r.get("test_id")) for r in f6]
    for test_id in kept:
        if ids.count(test_id) != 1:
            problems.append(
                f"{TESTGEN_REPORT}: {test_id}: {ids.count(test_id)} filter-6 rows (1 per kept test)"
            )
    extra = sorted(set(ids) - set(kept))
    if extra:
        problems.append(f"{TESTGEN_REPORT}: filter-6 rows for tests testgen did not keep: {extra}")
    positions = [i for i, r in enumerate(rows) if r.get("filter") == 6]
    others = [i for i, r in enumerate(rows) if r.get("filter") != 6]
    if positions and others and min(positions) < max(others):
        problems.append(
            f"{TESTGEN_REPORT}: filter-6 rows must come after the rows of filters 1-5 "
            "(filter 6 runs last)"
        )
    empty = [str(r.get("test_id")) for r in f6 if not str(r.get("reason", "")).strip()]
    if empty:
        problems.append(f"{TESTGEN_REPORT}: filter-6 rows without a reason: {empty}")
    block = report.get("filter6")
    passed = [str(r.get("test_id")) for r in f6 if r.get("passed") is True]
    if not isinstance(block, dict) or not isinstance(block.get("kept"), list):
        problems.append(f"{TESTGEN_REPORT}: no `filter6` object with a `kept` list")
    elif [str(x) for x in block["kept"]] != passed:
        problems.append(
            f"{TESTGEN_REPORT}: filter6.kept {block['kept']} does not match the passed "
            f"filter-6 rows {passed}"
        )
    return problems


# --- A/B command and cost ------------------------------------------------------------------------


def _ab_transcript(root: Path) -> Transcript:
    return Transcript(root, AB_TXT)


def ab_id_printed(t: Transcript) -> str | None:
    found = t.matches(AB_LINE)
    return found[0].group(1) if len(found) == 1 else None


def ab_cost_models(note: str) -> dict[str, float]:
    """Model -> cost from the note of an A/B `Cost:` line ({} when it lists no model)."""
    note_match = AB_NOTE.match(note)
    models: dict[str, float] = {}
    if note_match and note_match.group(1) != "no calls":
        for part in note_match.group(1).split(", "):
            m = MODEL_COST.match(part.strip())
            if m:
                models[m.group(1)] = float(m.group(2))
    return models


def ab_run_problems(root: Path) -> list[str]:
    """`live/ab.txt`: the command of the assignment README, one A/B, and a cost line within the
    caps."""
    t = _ab_transcript(root)
    if not t.ok:
        return t.problems
    problems: list[str] = []
    args = t.after("ab")
    if args is None:
        return [f"{t.rel}: the command is not `{AB_COMMAND}`: {t.command}"]
    values: dict[str, str] = {}
    flags: set[str] = set()
    i = 0
    while i < len(args):
        token = args[i]
        name, eq, value = token.partition("=")
        if name in ("--section", "--feature", "--k", "--purpose"):
            if not eq:
                i += 1
                value = args[i] if i < len(args) else ""
            values[name] = value
        elif token in ("--no-preview", "--reviewer", "--no-reviewer"):
            flags.add(token)
        else:
            problems.append(f"{t.rel}: option {token} is not part of the live step ({AB_COMMAND})")
        i += 1
    if values.get("--section") != AB_SECTION:
        problems.append(f"{t.rel}: the command needs --section {AB_SECTION}")
    if values.get("--feature") != AB_FEATURE:
        problems.append(f"{t.rel}: the command needs --feature {AB_FEATURE}")
    if values.get("--purpose") != AB_PURPOSE:
        problems.append(
            f"{t.rel}: the command needs --purpose {AB_PURPOSE} (the default, class, needs "
            "SHIPHARNESS_CLASS_DATE and traces into the class project)"
        )
    if "--no-preview" not in flags:
        problems.append(f"{t.rel}: the command needs --no-preview")
    if values.get("--k", "1") != "1":
        problems.append(f"{t.rel}: --k must be 1 (one A/B), got {values['--k']}")
    found = t.matches(AB_LINE)
    if len(found) != 1:
        problems.append(f"{t.rel}: expected one A/B line (k=1), found {len(found)}")
    else:
        ab_id, feature, layers = found[0].groups()
        if feature.startswith("Feature "):
            feature = "F" + feature.split()[1].rstrip(":")
        if not AB_ID.match(ab_id):
            problems.append(f"{t.rel}: {ab_id} is not a shipharness A/B id")
        if feature != AB_FEATURE:
            problems.append(f"{t.rel}: the A/B ran feature {feature}, expected {AB_FEATURE}")
        try:
            printed = sorted(ast.literal_eval(layers))
        except (ValueError, SyntaxError):
            printed = None
        if printed != HARNESS_LAYERS:
            problems.append(f"{t.rel}: harness layers {layers}, expected {HARNESS_LAYERS}")
    cost_problems, cost = _cost(t)
    problems += cost_problems
    if cost is not None:
        spent, note = cost
        if spent > COMMAND_CAP + EPS:
            problems.append(
                f"{t.rel}: command cost ${spent:.6f} is over the per-command cap ${COMMAND_CAP:.2f}"
            )
        models = ab_cost_models(note)
        if not models:
            problems.append(f"{t.rel}: the cost line lists no model costs: not a live run")
        elif models.get(MODEL, 0.0) <= 0:
            problems.append(f"{t.rel}: the cost line has no {MODEL} cost: the arms run on {MODEL}")
        for name in sorted(set(models) - {MODEL, REVIEW_MODEL}):
            problems.append(
                f"{t.rel}: model {name} is neither the course model {MODEL} nor the reviewer's "
                f"{REVIEW_MODEL}"
            )
    return problems


# --- A/B score records ---------------------------------------------------------------------------


def load_records(root: Path) -> tuple[list[str], list[tuple[str, ScoreRecord]]]:
    problems: list[str] = []
    records: list[tuple[str, ScoreRecord]] = []
    paths = sorted((root / SCORES).glob("*.json")) if (root / SCORES).is_dir() else []
    if len(paths) != 2:
        problems.append(
            f"{SCORES}: expected 2 score records (bare and harness) from one A/B, "
            f"found {len(paths)}"
        )
    for path in paths:
        name = f"{SCORES}/{path.name}"
        try:
            record = ScoreRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except ValueError as exc:
            detail = _errors(exc) if isinstance(exc, ValidationError) else str(exc)
            problems.append(f"{name}: not a ScoreRecord: {detail}")
            continue
        if path.stem != record.run_id:
            problems.append(f"{name}: the file name must be <run_id>.json ({record.run_id})")
        records.append((name, record))
    return problems, records


def score_record_problems(root: Path, expected_sha: str | None) -> list[str]:
    """The two ScoreRecords of the F4 A/B. `expected_sha`: the commit `m1-s4-start` names."""
    problems, records = load_records(root)
    for name, r in records:
        if r.recorded:
            problems.append(f"{name}: recorded is true: a replay is not a live run")
        if not r.sandboxed:
            problems.append(f"{name}: sandboxed is false: the arms must run in the Docker sandbox")
        if not RUN_ID.match(r.run_id):
            problems.append(f"{name}: run_id {r.run_id!r} is not a shipharness run id")
        if r.feature_id != AB_FEATURE:
            problems.append(f"{name}: feature_id {r.feature_id}, expected {AB_FEATURE}")
        if r.variant != AB_VARIANT:
            problems.append(f"{name}: variant {r.variant}, expected {AB_VARIANT}")
        if r.checkpoint != AB_CHECKPOINT:
            problems.append(f"{name}: checkpoint {r.checkpoint}, expected {AB_CHECKPOINT}")
        if r.checkpoint_sha is None or not SHA.match(r.checkpoint_sha):
            problems.append(
                f"{name}: checkpoint_sha {r.checkpoint_sha!r} is not a commit sha "
                "(run from the checkpoint tag, not --from-working-tree)"
            )
        elif expected_sha and not matches_checkpoint(
            _course_repo(), r.checkpoint_sha, expected_sha
        ):
            problems.append(
                f"{name}: checkpoint_sha {r.checkpoint_sha[:12]} is not the commit "
                f"{AB_CHECKPOINT} names ({expected_sha[:12]})"
            )
        want = HARNESS_LAYERS if r.arm == "harness" else []
        if sorted(r.layers) != want:
            problems.append(f"{name}: layers {r.layers}, expected {want} for the {r.arm} arm")
        if r.cost_usd > RUN_CAP + EPS:
            problems.append(
                f"{name}: cost_usd {r.cost_usd:.6f} is over MAX_RUN_COST_USD {RUN_CAP:.2f}"
            )
        if r.review_cost_usd > REVIEW_CAP + EPS:
            problems.append(
                f"{name}: review_cost_usd {r.review_cost_usd:.6f} is over MAX_REVIEW_COST_USD "
                f"{REVIEW_CAP:.2f}"
            )
    if len(records) == 2:
        arms = sorted(r.arm for _, r in records)
        if arms != ["bare", "harness"]:
            problems.append(f"{SCORES}: arms {arms}, expected one bare and one harness record")
        shas = {r.checkpoint_sha for _, r in records}
        if len(shas) != 1:
            problems.append(f"{SCORES}: the two records name different checkpoint_sha values")
    t = _ab_transcript(root)
    if t.ok:
        printed = ab_id_printed(t)
        for name, r in records:
            if printed and r.ab_id != printed:
                problems.append(
                    f"{name}: ab_id {r.ab_id} is not the A/B ab.txt printed ({printed})"
                )
        statuses = {m.group(1): m.group(2) for m in t.matches(AB_RECORD)}
        for name, r in records:
            if r.arm in statuses and statuses[r.arm] != r.status:
                problems.append(
                    f"{name}: status {r.status}, but ab.txt printed {statuses[r.arm]} "
                    f"for the {r.arm} arm"
                )
        _, cost = _cost(t)
        total = sum(r.cost_usd + r.review_cost_usd for _, r in records)
        if cost is not None and total > cost[0] + 1e-4:
            problems.append(
                f"{SCORES}: the records' costs (${total:.6f}) are more than the command's "
                f"cost line (${cost[0]:.6f})"
            )
    return problems


# --- LangSmith page, checkpoint ------------------------------------------------------------------


def trace_link_problems(root: Path, page: str) -> list[str]:
    """The LangSmith page links at least one trace of the A/B records (when they have any)."""
    _, records = load_records(root)
    urls = {u for _, r in records for u in (r.trace_url, r.referee_trace_url) if u}
    if not urls or any(u in page for u in urls):
        return []
    return [
        "portfolio/langsmith.md: link at least one trace of your A/B "
        f"(a `trace_url` in {SCORES}/*.json)"
    ]


def _course_repo() -> Path | None:
    """The course repository this file lives in (None outside a git checkout)."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file() and (parent / ".git").exists():
            return parent
    return None


def _teamtrack_tree(repo: Path, sha: str) -> str | None:
    """The TeamTrack tree of a checkpoint commit: platform/teamtrack, or teamtrack in older ones."""
    for sub in ("platform/teamtrack", "teamtrack"):
        try:
            run = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"{sha}:{sub}"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if run.returncode == 0 and run.stdout.strip():
            return run.stdout.strip()
    return None


def same_checkpoint(repo: Path | None, a: str, b: str) -> bool:
    """Two checkpoint commits are the same checkpoint when their TeamTrack trees are identical
    (checkpoint tags can be rebuilt; recorded runs keep the commit they ran on)."""
    if repo is None:
        return False
    tree_a, tree_b = _teamtrack_tree(repo, a), _teamtrack_tree(repo, b)
    return tree_a is not None and tree_a == tree_b


def matches_checkpoint(repo: Path | None, sha: str, expected_sha: str) -> bool:
    """`sha` is the checkpoint `expected_sha` names: the same commit, the same TeamTrack tree, or
    one of the EARLIER_CHECKPOINTS this tag named before a disclosed move (or its tree)."""
    if sha == expected_sha or same_checkpoint(repo, sha, expected_sha):
        return True
    return any(sha == old or same_checkpoint(repo, sha, old) for old in EARLIER_CHECKPOINTS)


def course_checkpoint_sha(repo: Path, tag: str = AB_CHECKPOINT) -> str | None:
    """The commit `tag` names in the course repo (None when the tag is not there)."""
    try:
        run = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"{tag}^{{commit}}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    sha = run.stdout.strip()
    return sha if run.returncode == 0 and SHA.match(sha) else None
