"""Collect and check the live evidence of the A1 A/B (the required live step).

Usage (from the repository root, on your work branch, after the A/B command in SPEC.md):

    uv run python section-1-instructions/assignment/live_evidence.py --batch a1-<name>
        --output <file> [--work DIR] [--exports exports] [--runs .shipharness/runs]

`--output` is the file you saved the command and its printed output to (SPEC.md, "Run the A/B").
The script copies, into `<work>/live/`:

- `output.txt`: that file (first line `$ <the exact command>`, last line `Cost: $...`);
- `experiments/<name>.json`: the two experiment exports of the batch (one per arm);
- `scores/<run_id>.json`: the ScoreRecord of every run in them (`shipharness.ab.score`);
- `runs/<run_id>/events.jsonl`: the run log of every harness-arm run (`shipharness.events.models`).

Then it runs the live checks and prints one PASS or FAIL line per check. The self-check and the
grader run the same checks. They read files only: no keys, no Docker, no model calls, and they
never re-run anything. Exit 0 when the evidence was collected and is well formed, 1 when it is
not, 2 when the batch or the output file is not found.

How the checks prove that your tree was used: the instructions layer writes one note to each
harness run's log when it prepares the workspace, "placed N instruction files", with the list of
files it copied from `teamtrack/harness/instructions/` (`InstructionsLayer.prepare_workspace`).
That list must equal the files of the `instructions/` tree you submit.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any


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
DATASET = REPO / "platform" / "datasets" / "teamtrack-features-v1.jsonl"

ARMS = ("bare", "harness")
COMMAND_START = "uv run shipharness experiments"
SPLIT = "section-1"
K = 3
LAYERS = ["instructions"]
DATASET_NAME = "teamtrack-features-v1"
MODEL = "gpt-6-luna"  # OPENAI_MODEL (src/shipharness/config/settings.py)
MAX_RUN_COST_USD = 0.20  # MAX_RUN_COST_USD, per arm per run (settings.py)
MAX_REVIEW_COST_USD = 0.04  # MAX_REVIEW_COST_USD, per review (settings.py)
MAX_COMMAND_COST_USD = 2.50  # MAX_BATCH_COST_USD, per command (settings.py; the A1 budget)
NAMES = ["live-files", "live-command", "live-caps", "live-tree", "live-report"]
HOW = "collect it with live_evidence.py (SPEC.md, 'Run the A/B')"

PENDING = re.compile(
    r"^\[\[PENDING: [^|\]]+ \| source: (?:M6 pilot|M8 batch 1|M8 ablation|live class)"
    r" \| how: [^\]]+\]\]$",
    re.M,
)
RUN_ID = re.compile(r"r-\d{8}-\d{6}-[0-9a-f]{6}")
SHA = re.compile(r"[0-9a-f]{40}")
_COST = re.compile(r"^Cost: \$(\d+(?:\.\d+)?) \((.*)\)\s*$", re.M)
_ARM_LINE = re.compile(r"^(bare|harness): (\S+)", re.M)
_SKIP_PARTS = {"__pycache__", ".DS_Store"}  # as InstructionsLayer.source_files skips them
_EPS = 1e-9

Check = tuple[str, float, str]


# -- inputs ---------------------------------------------------------------------------------------


def section_tasks(dataset: Path = DATASET, split: str = SPLIT) -> set[tuple[str, str, str]]:
    """(feature_id, variant, checkpoint) of every dataset example in the split."""
    tasks = set()
    for line in dataset.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        if split in data.get("split", []):
            inputs = data["inputs"]
            tasks.add((inputs["feature_id"], inputs["variant"], inputs["checkpoint"]))
    return tasks


def tree_files(tree: Path) -> list[str]:
    """Tree-relative paths the instructions layer would place, sorted (same rule as the layer)."""
    if not tree.is_dir():
        return []
    return sorted(
        p.relative_to(tree).as_posix()
        for p in tree.rglob("*")
        if p.is_file() and not _SKIP_PARTS & set(p.parts)
    )


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class Evidence:
    """The parsed contents of <work>/live/. `problems` lists what is missing or malformed."""

    def __init__(self, live: Path) -> None:
        self.live = live
        self.problems: list[str] = []
        self.command = ""
        self.output = ""
        self.exports: dict[str, dict[str, Any]] = {}
        self.records: dict[str, list[Any]] = {arm: [] for arm in ARMS}
        self.logs: dict[str, list[dict[str, Any]]] = {}
        self._load()

    def _problem(self, text: str) -> None:
        self.problems.append(text)

    def _load(self) -> None:
        if not self.live.is_dir():
            self._problem(f"no live/ folder in the work folder; {HOW}")
            return
        self._load_output()
        self._load_exports()
        for arm in ARMS:
            for run_id in self.exports.get(arm, {}).get("rows", []):
                self._load_record(arm, str(run_id))
                if arm == "harness":
                    self._load_log(str(run_id))

    def _load_output(self) -> None:
        path = self.live / "output.txt"
        if not path.is_file():
            self._problem("live/output.txt is missing (the command and its printed output)")
            return
        self.output = path.read_text(encoding="utf-8")
        lines = [ln for ln in self.output.splitlines() if ln.strip()]
        if not lines or not lines[0].startswith(f"$ {COMMAND_START}"):
            self._problem(f"live/output.txt must start with the line '$ {COMMAND_START} ...'")
        else:
            self.command = lines[0][2:].strip()
        if not _COST.search(self.output):
            self._problem("live/output.txt has no 'Cost: $...' line (the command's cost line)")

    def _load_exports(self) -> None:
        folder = self.live / "experiments"
        found: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
        for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            try:
                data = _read_json(path)
            except (OSError, ValueError) as exc:
                self._problem(f"live/experiments/{path.name} is not JSON ({exc})")
                continue
            if not isinstance(data, dict) or data.get("arm") not in ARMS:
                self._problem(f"live/experiments/{path.name} has no arm 'bare' or 'harness'")
                continue
            for key in ("name", "split", "k", "metadata", "rows", "checkpoint_shas", "stats"):
                if key not in data:
                    self._problem(f"live/experiments/{path.name} has no '{key}'")
            if not isinstance(data.get("rows"), list) or not isinstance(data.get("metadata"), dict):
                self._problem(f"live/experiments/{path.name}: 'rows' or 'metadata' malformed")
                continue
            found[data["arm"]].append(data)
        for arm in ARMS:
            if len(found[arm]) != 1:
                self._problem(
                    f"need exactly one {arm} experiment export in live/experiments/ "
                    f"(found {len(found[arm])})"
                )
            else:
                self.exports[arm] = found[arm][0]

    def _load_record(self, arm: str, run_id: str) -> None:
        from pydantic import ValidationError

        from shipharness.ab.score import ScoreRecord

        path = self.live / "scores" / f"{run_id}.json"
        if not path.is_file():
            self._problem(f"live/scores/{run_id}.json is missing ({arm} run in the export)")
            return
        try:
            data = _read_json(path)
        except (OSError, ValueError) as exc:
            self._problem(f"live/scores/{run_id}.json is not JSON ({exc})")
            return
        missing = sorted(set(ScoreRecord.model_fields) - set(data))
        if missing:
            self._problem(f"live/scores/{run_id}.json lacks ScoreRecord fields: {missing[:5]}")
            return
        try:
            record = ScoreRecord.model_validate(data)
        except ValidationError as exc:
            first = exc.errors()[0]
            where = ".".join(str(p) for p in first["loc"])
            self._problem(
                f"live/scores/{run_id}.json is not a ScoreRecord: {where}: {first['msg']}"
            )
            return
        if record.run_id != run_id:
            self._problem(f"live/scores/{run_id}.json holds run {record.run_id}")
            return
        self.records[arm].append(record)

    def _load_log(self, run_id: str) -> None:
        from pydantic import ValidationError

        from shipharness.events.models import EVENT_DATA_MODELS, Event

        path = self.live / "runs" / run_id / "events.jsonl"
        if not path.is_file():
            self._problem(f"live/runs/{run_id}/events.jsonl is missing (harness run log)")
            return
        events = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                event = Event.model_validate(json.loads(line))
                EVENT_DATA_MODELS[event.type].model_validate(event.data)
            except (ValueError, ValidationError) as exc:
                reason = str(exc).splitlines()[0]
                self._problem(f"live/runs/{run_id}/events.jsonl:{number} is not an event: {reason}")
                return
            events.append(event.model_dump(mode="json"))
        self.logs[run_id] = events


# -- the checks -----------------------------------------------------------------------------------


def _score(name: str, failures: list[str], total: int) -> Check:
    failed = len(failures)
    return name, max(0.0, (total - failed) / total), "; ".join(failures)


def _flags(command: str) -> dict[str, str]:
    try:
        words = shlex.split(command)
    except ValueError:
        return {}
    flags: dict[str, str] = {}
    for i, word in enumerate(words):
        if word.startswith("--"):
            key, _, value = word.partition("=")
            if not value and i + 1 < len(words) and not words[i + 1].startswith("--"):
                value = words[i + 1]
            flags[key] = value
    return flags


def check_command(ev: Evidence, tasks: set[tuple[str, str, str]]) -> Check:
    """Run ids, batch, split, k, layers, and tasks consistent with the command."""
    flags = _flags(ev.command)
    batch = flags.get("--batch", "")
    failures: list[str] = []
    wanted = {"--split": SPLIT, "--k": str(K), "--layers": "instructions"}
    bad = [f"{key} {value}" for key, value in wanted.items() if flags.get(key) != value]
    if flags.get("--dataset", DATASET_NAME) != DATASET_NAME:
        bad.append(f"--dataset {DATASET_NAME} (or no --dataset)")
    flag_problems = []
    if bad or not batch:
        flag_problems.append(f"the command needs {', '.join(bad) or '--batch <label>'}")
    if "--from-working-tree" in flags:
        flag_problems.append("the command used --from-working-tree; the A/B runs from tags")
    if flag_problems:
        failures.append("; ".join(flag_problems))

    export_problems = []
    named = dict(_ARM_LINE.findall(ev.output))
    for arm, export in ev.exports.items():
        meta = export["metadata"]
        layers = LAYERS if arm == "harness" else []
        if export.get("split") != SPLIT or export.get("k") != K:
            export_problems.append(
                f"{arm} export has split {export.get('split')}, k {export.get('k')}"
            )
        if export.get("dataset", DATASET_NAME) != DATASET_NAME:
            export_problems.append(f"{arm} export is on dataset {export.get('dataset')}")
        if meta.get("batch") != batch:
            export_problems.append(f"{arm} export has batch {meta.get('batch')}, command {batch}")
        if meta.get("layers") != layers:
            export_problems.append(f"{arm} export has layers {meta.get('layers')}, need {layers}")
        if named.get(arm) != export.get("name"):
            export_problems.append(
                f"the command output does not name the {arm} export {export.get('name')}"
            )
    if export_problems:
        failures.append("; ".join(export_problems))

    record_problems = []
    for arm, records in ev.records.items():
        layers = LAYERS if arm == "harness" else []
        shas = ev.exports[arm].get("checkpoint_shas", {})
        for r in records:
            where = f"{arm} run {r.run_id}"
            if not RUN_ID.fullmatch(r.run_id):
                record_problems.append(f"{where}: run id is not r-<date>-<time>-<hex>")
            if r.arm != arm:
                record_problems.append(f"{where}: arm {r.arm} in the {arm} export")
            if r.layers != layers or r.ab_id is not None:
                record_problems.append(f"{where}: layers {r.layers}, need {layers}")
            if (
                not SHA.fullmatch(r.checkpoint_sha or "")
                or shas.get(r.checkpoint) != r.checkpoint_sha
            ):
                record_problems.append(
                    f"{where}: checkpoint_sha {r.checkpoint_sha} is not the tag's commit"
                )
            if (r.feature_id, r.variant, r.checkpoint) not in tasks:
                record_problems.append(
                    f"{where}: task {r.feature_id} {r.variant} {r.checkpoint} is not in {SPLIT}"
                )
    if record_problems:
        failures.append("; ".join(record_problems[:4]))

    counts = []
    for arm, records in ev.records.items():
        per_task = Counter((r.feature_id, r.variant, r.checkpoint) for r in records)
        if len(records) != len(tasks) * K or any(n != K for n in per_task.values()):
            counts.append(f"{arm} has {len(records)} runs")
    if counts:
        failures.append(
            f"{', '.join(counts)}; {SPLIT} with --k {K} needs {len(tasks) * K} runs per arm, "
            f"{K} per task (every run is a dot: never drop runs)"
        )
    return _score("live-command", failures, 4)


def check_caps(ev: Evidence) -> Check:
    """Model gpt-6-luna, recorded false, sandboxed, run and command cost within the caps."""
    failures: list[str] = []
    models = [e["metadata"].get("model") for e in ev.exports.values()]
    log_models = set()
    for events in ev.logs.values():
        for event in events:
            if event["type"] == "run_start":
                log_models.add(event["data"]["spec"].get("model"))
            elif event["type"] == "cost":
                log_models.add(event["data"].get("model"))
    if any(m != MODEL for m in models) or log_models - {MODEL}:
        seen = sorted({str(m) for m in models} | {str(m) for m in log_models})
        failures.append(f"model: the runs used {', '.join(seen)}; the course model is {MODEL}")

    records = [r for arm in ARMS for r in ev.records[arm]]
    logged = [e for events in ev.logs.values() for e in events]
    if any(r.recorded for r in records) or any(e["recorded"] for e in logged):
        failures.append(
            "recorded: a record or event is a recorded replay; the live step is a live run"
        )
    if any(not r.sandboxed for r in records):
        failures.append("sandbox: a run was not sandboxed (SANDBOX_MODE must stay docker)")

    over = [r.run_id for r in records if r.cost_usd > MAX_RUN_COST_USD + _EPS]
    over += [r.run_id for r in records if r.review_cost_usd > MAX_REVIEW_COST_USD + _EPS]
    if over:
        failures.append(
            f"run cost above MAX_RUN_COST_USD ${MAX_RUN_COST_USD:.2f} (or a review above "
            f"${MAX_REVIEW_COST_USD:.2f}): {', '.join(over[:3])}"
        )

    match = _COST.search(ev.output)
    command_cost = float(match.group(1)) if match else 0.0
    spent = sum(r.cost_usd + r.review_cost_usd for r in records)
    command_problems = []
    if command_cost > MAX_COMMAND_COST_USD + _EPS or spent > MAX_COMMAND_COST_USD + _EPS:
        command_problems.append(
            f"the command cost ${max(command_cost, spent):.2f}, above the per-command cap "
            f"${MAX_COMMAND_COST_USD:.2f}"
        )
    if match is None or MODEL not in match.group(2):
        command_problems.append(f"the cost line does not name {MODEL}")
    if command_problems:
        failures.append("; ".join(command_problems))
    return _score("live-caps", failures, 5)


def check_tree_used(ev: Evidence, tree: Path) -> Check:
    """Every harness run log shows the instructions layer placed exactly the submitted tree."""
    files = tree_files(tree)
    status = {r.run_id: r.status for r in ev.records["harness"]}
    problems: list[str] = []
    mismatched: dict[tuple[tuple[str, ...], tuple[str, ...]], list[str]] = {}
    placements = 0
    for run_id, events in sorted(ev.logs.items()):
        start = next((e for e in events if e["type"] == "run_start"), None)
        spec = start["data"]["spec"] if start else {}
        if (
            spec.get("run_id") != run_id
            or spec.get("arm") != "harness"
            or spec.get("layers") != LAYERS
        ):
            problems.append(f"{run_id}: the run log's run_start is not a harness run with {LAYERS}")
            continue
        placed = [
            e["data"]
            for e in events
            if e["type"] == "harness_decision"
            and e["data"].get("layer") == "instructions"
            and str(e["data"].get("message", "")).startswith("placed ")
        ]
        if not placed:
            if status.get(run_id) != "ERROR":
                problems.append(f"{run_id}: no 'placed ... instruction files' note in the run log")
            continue
        placements += 1
        paths = sorted(placed[0].get("paths", []))
        if paths != files or "AGENTS.md" not in paths:
            key = (tuple(sorted(set(files) - set(paths))), tuple(sorted(set(paths) - set(files))))
            mismatched.setdefault(key, []).append(run_id)
    for (missing, extra), run_ids in mismatched.items():
        problems.append(
            f"{len(run_ids)} harness run(s) (first: {run_ids[0]}) placed a different tree; "
            f"in your tree but not placed: {', '.join(missing[:4]) or 'none'}; placed but not "
            f"in your tree: {', '.join(extra[:4]) or 'none'}"
            + ("" if missing or extra else "; no AGENTS.md map was placed")
        )
    if not placements and not problems:
        problems.append("no harness run log shows the instructions layer placing a tree")
    detail = "; ".join(problems[:3])
    if problems:
        detail += (
            " (copy your instructions/ tree to teamtrack/harness/instructions/ before the A/B, "
            "and do not add or remove tree files after it)"
        )
    return "live-tree", 0.0 if problems else 1.0, detail


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


def _failing(records: list[Any], field: str) -> str:
    return f"{sum(1 for r in records if getattr(r, field) >= 1)}/{len(records)}"


def check_report_matches(ev: Evidence, report: Path) -> Check:
    """The report's command, runs per arm, R1 and R3 counts, and links come from the evidence."""
    if not report.is_file():
        return "live-report", 0.0, "ab-report.md is missing"
    sections = _sections(report.read_text(encoding="utf-8"))
    setup = sections.get("Setup", "")
    failures: list[str] = []
    command = re.search(r"uv run shipharness experiments[^`\n]*", setup)
    if not command or command.group(0).split() != ev.command.split():
        failures.append("the Setup command differs from the command in live/output.txt")
    runs = {len(ev.records[arm]) for arm in ARMS}
    stated = re.search(r"Runs per arm: (\d+)", setup)
    if not stated or {int(stated.group(1))} != runs:
        failures.append(f"Runs per arm must be {' and '.join(str(n) for n in sorted(runs))}")
    rows = [r for r in sections.get("Results", "").splitlines() if r.strip().startswith("|")]
    for measure, field in (("R1", "r1_new_violations"), ("R3", "r3_new_failures")):
        want = [_failing(ev.records[arm], field) for arm in ARMS]
        row = next((r for r in rows if r.strip("| ").startswith(measure)), "")
        cells = [c.strip() for c in row.strip().strip("|").split("|")][1:3]
        if cells != want:
            failures.append(f"the {measure} row must read {want[0]} (bare) and {want[1]} (harness)")
    links = sections.get("Links", "")
    urls = [str(ev.exports[arm].get("url") or "") for arm in ARMS]
    if not all(urls) or not all(u in links for u in urls):
        failures.append("Links must hold the two experiment URLs of the exports (the link field)")
    detail = "; ".join(failures)
    if failures:
        detail += " (ab_summary.py --exports <work>/live prints the values)"
    return _score("live-report", failures, 5)[:2] + (detail,)


def check_live(
    work: Path,
    *,
    allow_pending: bool = False,
    dataset: Path = DATASET,
) -> list[Check]:
    """The five live checks for a work folder: (name, score 0..1, detail when below 1)."""
    live = work / "live"
    pending = (
        live.is_dir()
        and not (live / "scores").exists()
        and any(PENDING.search(p.read_text(encoding="utf-8")) for p in live.glob("*.md"))
    )
    if pending:
        if allow_pending:
            return [(name, 1.0, "") for name in NAMES]
        detail = "live/ holds a pending marker, not a captured run; " + HOW
        return [(name, 0.0, detail) for name in NAMES]
    ev = Evidence(live)
    if ev.problems:
        shown = "; ".join(ev.problems[:4]) + ("; ..." if len(ev.problems) > 4 else "")
        detail = f"live evidence missing or malformed: {shown}"
        if "no live/ folder" not in shown:
            detail += f"; {HOW}"
        return [(name, 0.0, detail) for name in NAMES]
    return [
        ("live-files", 1.0, ""),
        check_command(ev, section_tasks(dataset)),
        check_caps(ev),
        check_tree_used(ev, work / "instructions"),
        check_report_matches(ev, work / "ab-report.md"),
    ]


# -- collecting -----------------------------------------------------------------------------------


def collect(batch: str, output: Path, work: Path, exports: Path, runs: Path) -> list[str]:
    """Copy the batch's evidence into <work>/live/. Returns problems that stop the copy."""
    if not output.is_file():
        return [f"--output {output} not found (save the command and its output there first)"]
    chosen: dict[str, Path] = {}
    for arm in ARMS:
        options = []
        for path in sorted((exports / "experiments").glob("*.json")):
            try:
                data = _read_json(path)
            except ValueError:
                continue
            if data.get("arm") == arm and data.get("metadata", {}).get("batch") == batch:
                options.append(path)
        if len(options) != 1:
            return [
                f"need one {arm} experiment with batch {batch} in {exports}; found {len(options)}"
            ]
        chosen[arm] = options[0]
    live = work / "live"
    for old in ("experiments", "scores", "runs"):  # a re-collect replaces, never mixes
        if (live / old).exists():
            shutil.rmtree(live / old)
    (live / "experiments").mkdir(parents=True)
    (live / "scores").mkdir()
    shutil.copyfile(output, live / "output.txt")
    for arm, path in chosen.items():
        shutil.copyfile(path, live / "experiments" / path.name)
        for run_id in _read_json(path).get("rows", []):
            score = exports / "scores" / f"{run_id}.json"
            if score.is_file():
                shutil.copyfile(score, live / "scores" / score.name)
            log = runs / str(run_id) / "events.jsonl"
            if arm == "harness" and log.is_file():
                (live / "runs" / str(run_id)).mkdir(parents=True)
                shutil.copyfile(log, live / "runs" / str(run_id) / "events.jsonl")
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--batch", required=True, help="the --batch label of the A/B command")
    parser.add_argument("--output", type=Path, required=True, help="the saved command output")
    parser.add_argument("--work", type=Path, default=STARTER)
    parser.add_argument("--exports", type=Path, default=Path("exports"))
    parser.add_argument("--runs", type=Path, default=Path(".shipharness/runs"))
    args = parser.parse_args(argv)
    problems = collect(args.batch, args.output, args.work, args.exports, args.runs)
    if problems:
        for problem in problems:
            print(f"x {problem}")
        return 2
    print(f"collected batch {args.batch} into {args.work / 'live'}")
    results = check_live(args.work)
    for name, score, detail in results:
        print(f"PASS {name}" if score >= 1 else f"FAIL {name}: {detail}")
    return 0 if results[0][1] >= 1 else 1


if __name__ == "__main__":
    sys.exit(main())
