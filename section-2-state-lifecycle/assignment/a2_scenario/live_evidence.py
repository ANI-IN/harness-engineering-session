"""The required live step (SPEC.md, "Evidence to hand in"): the four-session task, the evidence
files the live wrapper writes, and the checks the grader applies to them.

The live step is the only part of A2 that uses the course model. The scenarios use the test
stand-in agent (literal_agent.py), which is not a model. The checks here read files only: they
never call a model and never need keys. They check structure, the model name, four build sessions
and three forced stops, costs against the course caps, and that the run used the submitted layer;
they score nothing else from what the model did.

Evidence folder: `<submission>/live/`
    task.jsonl     the task the run used (F2-canonical with a four-session budget)
    command.txt    the commands: the wrapper as run, and the shipharness command it ran
    output.txt     everything the shipharness command printed, ending with its `Cost: $...` line
    summary.json   the run summary: ids, model, sessions and forced stops per arm, the layer
    scores/        the ScoreRecord files the referee wrote to exports/scores/<run_id>.json
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from shipharness.ab.score import ScoreRecord
from shipharness.config import Settings
from shipharness.config.prices import REPO_ROOT

FEATURES_FILE = REPO_ROOT / "platform" / "datasets" / "teamtrack-features-v1.jsonl"
SOURCE_EXAMPLE = "F2-canonical"
LIVE_EXAMPLE_ID = "F2-a2-four-sessions"
LIVE_VARIANT = "a2-four-sessions"
# The 50 build turns of every F2 line in the dataset, split over four sessions.
LIVE_BUDGETS = (10, 10, 10, 20)
FORCED_STOPS = len(LIVE_BUDGETS) - 1
# How sessions 1 to 3 of the harness arm may end. The turn budget forces the stop. An agent's own
# finish(claim="not_done") also counts, but only when the harness stop step ran for that session:
# the handoff and progress written and committed (owner decision, 2026-10-18).
FORCED_END = "turn_budget"
AGENT_END = "claim_not_done"
HANDOFF_FILE = "session-handoff.md"
PROGRESS_FILE = "progress.md"
LIVE_LAYERS = "instructions,state"
LAYER_CLASS = "ResumableStateLayer"
# Class defaults, read from the settings class (no .env is read here).
LIVE_MODEL: str = Settings.model_fields["openai_model"].default
RUN_CAP_USD: float = Settings.model_fields["max_run_cost_usd"].default
COMMAND_CAP_USD: float = Settings.model_fields["max_batch_cost_usd"].default

LIVE_KEY = "live_run"
LIVE_POINTS = 10
LIVE_TITLE = "Live run: gpt-6-luna, four sessions, three forced stops, evidence valid"

EVIDENCE_DIR = "live"
TASK_FILE = "task.jsonl"
COMMAND_FILE = "command.txt"
OUTPUT_FILE = "output.txt"
SUMMARY_FILE = "summary.json"
SCORES_DIR = "scores"
PACKAGE = "a2_state"

_TWO = "This task runs over two sessions."
_FOUR = "This task runs over four sessions."
_AB_LINE = re.compile(r"^A/B (\S+) \(", re.MULTILINE)
_COST_LINE = re.compile(r"^Cost: \$(\d+(?:\.\d+)?) \(this command: ([^;]*);", re.MULTILINE)
_SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".shipharness", "exports"}


# -- the task -----------------------------------------------------------------------------------


def load_example(dataset: Path, example_id: str) -> dict[str, Any]:
    for line in dataset.read_text(encoding="utf-8").splitlines():
        if line.strip():
            data = json.loads(line)
            if data.get("metadata", {}).get("example_id") == example_id:
                return data
    raise KeyError(f"{example_id} not found in {dataset.name}")


def derive_task_line(source: dict[str, Any]) -> dict[str, Any]:
    """The source line with four build sessions; ticket, hidden tests, and mutants unchanged
    except the sentence that states the number of sessions."""
    line = json.loads(json.dumps(source))
    inputs = line["inputs"]
    ticket = inputs["ticket_text"]
    inputs["ticket_text"] = (
        ticket.replace(_TWO, _FOUR) if _TWO in ticket else f"{ticket.rstrip()}\n{_FOUR}\n"
    )
    inputs["session_budget"] = list(LIVE_BUDGETS)
    inputs["variant"] = LIVE_VARIANT
    line.setdefault("metadata", {})["example_id"] = LIVE_EXAMPLE_ID
    return line


def write_task(evidence: Path, dataset: Path = FEATURES_FILE) -> Path:
    evidence.mkdir(parents=True, exist_ok=True)
    path = evidence / TASK_FILE
    line = derive_task_line(load_example(dataset, SOURCE_EXAMPLE))
    path.write_text(json.dumps(line, sort_keys=True) + "\n", encoding="utf-8")
    return path


def inner_command(task_path: str) -> list[str]:
    """The shipharness command of the live step (an A/B: both arms, judged by the referee)."""
    return [
        "ab",
        "--dataset",
        task_path,
        "--example",
        LIVE_EXAMPLE_ID,
        "--layers",
        LIVE_LAYERS,
        "--no-reviewer",
        "--purpose",
        "assignment",
    ]


# -- writing the evidence -----------------------------------------------------------------------


def layer_digest(impl: Path) -> str:
    """sha256 over the paths and bytes of every .py file in `<impl>/a2_state/`."""
    root = Path(impl) / PACKAGE
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def ab_id_from_output(output: str) -> str | None:
    match = _AB_LINE.search(output)
    return match.group(1) if match else None


def _stops(events: Path, run_id: str) -> list[dict[str, Any]]:
    """The session_stop events of `run_id`, each with what the harness stop step left: the
    handoff path, the paths of the state layer's session_stop decision for that session, the
    commit the session ended on, and the commit the next session started from (they differ when
    the stop step committed the handoff and progress)."""
    stops: list[dict[str, Any]] = []
    if not events.is_file():
        return stops
    written: dict[Any, list[str]] = {}
    resumes: dict[Any, Any] = {}
    for line in events.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("run_id") != run_id:
            continue
        kind, data = event.get("type"), event.get("data", {})
        if kind == "harness_decision" and data.get("kind") == "session_stop":
            index = (data.get("data") or {}).get("session_index")
            written.setdefault(index, []).extend(str(p) for p in data.get("paths") or [])
        elif kind == "session_resume":
            resumes[data.get("session_index")] = data.get("start_sha")
        elif kind == "session_stop":
            stops.append(
                {
                    "session_index": data.get("session_index"),
                    "ended_by": data.get("ended_by"),
                    "handoff_path": data.get("handoff_path"),
                    "end_sha": data.get("end_sha"),
                }
            )
    for stop in stops:
        index = stop["session_index"]
        stop["state_paths"] = sorted(set(written.get(index, [])))
        stop["resume_sha"] = resumes.get(index + 1) if isinstance(index, int) else None
    return stops


def build_summary(ab_dir: Path, *, layer: str, digest: str, impl: str) -> dict[str, Any]:
    """The run summary from the A/B's ab.json and events.jsonl (runs/<ab_id>/)."""
    ab = json.loads((ab_dir / "ab.json").read_text(encoding="utf-8"))
    arms: dict[str, Any] = {}
    for arm, run in ab["arms"].items():
        spec, result = run["spec"], run["result"]
        arms[arm] = {
            "run_id": spec["run_id"],
            "model": spec.get("model"),
            "layers": spec.get("layers", []),
            "session_budget": spec.get("session_budget", []),
            "status": result.get("status"),
            "claim": result.get("claim"),
            "cost_usd": result.get("cost_usd"),
            "turns_total": result.get("turns_total"),
            "sessions": [
                {k: s.get(k) for k in ("index", "phase", "turns", "ended_by")}
                for s in result.get("sessions", [])
            ],
            "session_stops": _stops(ab_dir / "events.jsonl", spec["run_id"]),
        }
    return {
        "kind": "a2-live-run",
        "ab_id": ab_dir.name,
        "example_id": LIVE_EXAMPLE_ID,
        "checkpoint_sha": ab.get("checkpoint_sha"),
        "layer": {"class": layer, "impl": impl, "a2_state_sha256": digest},
        "arms": arms,
    }


def collect_evidence(
    impl: Path,
    *,
    ab_dir: Path,
    scores_dir: Path,
    output: str,
    command: list[str],
    layer: str,
) -> Path:
    """Write summary.json, command.txt, output.txt, and copy the score records into
    `<impl>/live/` (task.jsonl is written before the run)."""
    evidence = Path(impl) / EVIDENCE_DIR
    evidence.mkdir(parents=True, exist_ok=True)
    summary = build_summary(ab_dir, layer=layer, digest=layer_digest(impl), impl=Path(impl).name)
    (evidence / SUMMARY_FILE).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (evidence / COMMAND_FILE).write_text("\n".join(command) + "\n", encoding="utf-8")
    (evidence / OUTPUT_FILE).write_text(output, encoding="utf-8")
    scores = evidence / SCORES_DIR
    scores.mkdir(exist_ok=True)
    for arm in summary["arms"].values():
        source = scores_dir / f"{arm['run_id']}.json"
        if source.is_file():
            shutil.copyfile(source, scores / source.name)
    return evidence


# -- finding and checking the evidence ----------------------------------------------------------


def find_submission(path: Path) -> Path:
    """The folder that holds `a2_state/`: `path` itself, or the one folder below it that has
    `a2_state/layer.py` (preferring folders with live evidence), for a cloned repository."""
    path = Path(path)
    if (path / PACKAGE / "layer.py").is_file():
        return path
    found = [
        p.parent.parent
        for p in sorted(path.rglob(f"{PACKAGE}/layer.py"))
        if not _SKIP_DIRS.intersection(p.relative_to(path).parts)
    ]
    with_live = [p for p in found if (p / EVIDENCE_DIR / SUMMARY_FILE).is_file()]
    candidates = with_live or found
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise FileNotFoundError(f"no {PACKAGE}/layer.py under {path.name} (use --impl <folder>)")
    names = ", ".join(p.relative_to(path).as_posix() for p in candidates)
    raise FileNotFoundError(f"{len(candidates)} folders hold {PACKAGE}/ ({names}): pass one")


def _load_json(path: Path, problems: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        problems.append(f"{EVIDENCE_DIR}/{path.name}: not readable JSON ({type(exc).__name__})")
        return None


def _check_task(evidence: Path, problems: list[str]) -> None:
    lines = [ln for ln in (evidence / TASK_FILE).read_text(encoding="utf-8").splitlines() if ln]
    try:
        task = json.loads(lines[0]) if len(lines) == 1 else None
    except ValueError:
        task = None
    if task is None:
        problems.append(f"{EVIDENCE_DIR}/{TASK_FILE}: expected one JSON line")
        return
    inputs = task.get("inputs", {})
    if inputs.get("feature_id") != "F2" or list(inputs.get("session_budget", [])) != list(
        LIVE_BUDGETS
    ):
        problems.append(
            f"{EVIDENCE_DIR}/{TASK_FILE}: expected F2 with session_budget {list(LIVE_BUDGETS)}"
        )
    if task.get("metadata", {}).get("example_id") != LIVE_EXAMPLE_ID:
        problems.append(f"{EVIDENCE_DIR}/{TASK_FILE}: example id is not {LIVE_EXAMPLE_ID}")


def _check_command(evidence: Path, problems: list[str]) -> None:
    text = (evidence / COMMAND_FILE).read_text(encoding="utf-8")
    needed = ["run_live.py", "--forced-stops", "ab --dataset", f"--example {LIVE_EXAMPLE_ID}"]
    needed.append(f"--layers {LIVE_LAYERS}")
    missing = [n for n in needed if n not in text]
    if missing:
        problems.append(f"{EVIDENCE_DIR}/{COMMAND_FILE}: missing {', '.join(missing)}")


def _check_output(evidence: Path, ab_id: str, problems: list[str]) -> None:
    text = (evidence / OUTPUT_FILE).read_text(encoding="utf-8")
    if ab_id_from_output(text) != ab_id:
        problems.append(f"{EVIDENCE_DIR}/{OUTPUT_FILE}: no `A/B {ab_id}` line")
    if not re.search(rf"^state layer: \S+\.{LAYER_CLASS} from ", text, re.MULTILINE):
        problems.append(f"{EVIDENCE_DIR}/{OUTPUT_FILE}: no `state layer: ...{LAYER_CLASS}` line")
    costs = _COST_LINE.findall(text)
    if not costs:
        problems.append(f"{EVIDENCE_DIR}/{OUTPUT_FILE}: no `Cost: $...` line")
        return
    total, models = costs[-1]
    if float(total) > COMMAND_CAP_USD + 1e-9:
        problems.append(f"cost ${float(total):.6f} is over the per-command cap ${COMMAND_CAP_USD}")
    if LIVE_MODEL not in models:
        problems.append(f"the cost line names no {LIVE_MODEL} calls ({models.strip()})")


def _check_records(
    evidence: Path, summary: dict[str, Any], problems: list[str]
) -> dict[str, ScoreRecord]:
    records: dict[str, ScoreRecord] = {}
    scores = evidence / SCORES_DIR
    files = sorted(scores.glob("*.json")) if scores.is_dir() else []
    for path in files:
        data = _load_json(path, problems)
        try:
            record = ScoreRecord(**data) if isinstance(data, dict) else None
        except ValidationError as exc:
            problems.append(f"scores/{path.name}: not a ScoreRecord ({exc.error_count()} errors)")
            continue
        if record is None:
            continue
        if path.stem != record.run_id:
            problems.append(f"scores/{path.name}: file name is not its run id {record.run_id}")
        records[record.arm] = record
    if set(records) != {"bare", "harness"}:
        problems.append(f"scores/: expected one ScoreRecord per arm, found {sorted(records)}")
    for arm, record in records.items():
        where = f"scores/{record.run_id}.json"
        expected = summary.get("arms", {}).get(arm, {}).get("run_id")
        if record.run_id != expected:
            problems.append(f"{where}: run id differs from the summary's {arm} run id {expected}")
        if record.ab_id != summary.get("ab_id"):
            problems.append(f"{where}: ab id {record.ab_id} differs from {summary.get('ab_id')}")
        if record.feature_id != "F2" or record.variant != LIVE_VARIANT:
            problems.append(f"{where}: not the live task (F2, variant {LIVE_VARIANT})")
        if record.recorded:
            problems.append(f"{where}: recorded is true (a replay, not a live run)")
        if not record.sandboxed:
            problems.append(f"{where}: sandboxed is false (the live step runs in the sandbox)")
        if not record.checkpoint_sha:
            problems.append(f"{where}: no checkpoint_sha (run from a checkpoint tag)")
        if record.cost_usd > RUN_CAP_USD + 1e-9:
            problems.append(f"{where}: cost ${record.cost_usd} is over the run cap ${RUN_CAP_USD}")
    harness = records.get("harness")
    if harness is not None and "state" not in harness.layers:
        problems.append("the harness arm's score record does not list the state layer")
    return records


def _stop_step_ran(stop: dict[str, Any] | None) -> bool:
    """True when the harness stop step ran for a session: its session_stop names a handoff, the
    state layer wrote the handoff and progress.md for it, and the next session started from a
    new commit (the stop step's commit)."""
    if not stop or not stop.get("handoff_path"):
        return False
    written = set(stop.get("state_paths") or [])
    end, resume = stop.get("end_sha"), stop.get("resume_sha")
    return {HANDOFF_FILE, PROGRESS_FILE} <= written and bool(end and resume) and end != resume


def _check_summary(submission: Path, summary: dict[str, Any], problems: list[str]) -> None:
    layer = summary.get("layer", {})
    if not str(layer.get("class", "")).endswith(f".{LAYER_CLASS}"):
        problems.append(f"summary: the layer is not a {LAYER_CLASS}")
    if layer.get("a2_state_sha256") != layer_digest(submission):
        problems.append(
            f"summary: the run's layer differs from the submitted {PACKAGE}/ "
            "(run the live step again after your last change to the layer)"
        )
    arms = summary.get("arms", {})
    for arm in ("bare", "harness"):
        info = arms.get(arm)
        if not isinstance(info, dict):
            problems.append(f"summary: no {arm} arm")
            continue
        if info.get("model") != LIVE_MODEL:
            problems.append(f"summary: {arm} arm ran model {info.get('model')}, not {LIVE_MODEL}")
        if list(info.get("session_budget", [])) != list(LIVE_BUDGETS):
            problems.append(f"summary: {arm} arm session_budget is not {list(LIVE_BUDGETS)}")
    harness = arms.get("harness", {}) if isinstance(arms.get("harness"), dict) else {}
    build = [s for s in harness.get("sessions", []) if s.get("phase") == "build"]
    ends = [s.get("ended_by") for s in build]
    by_index = {s.get("session_index"): s for s in harness.get("session_stops", [])}
    forced = [
        end == FORCED_END or (end == AGENT_END and _stop_step_ran(by_index.get(i)))
        for i, end in enumerate(ends[:FORCED_STOPS], start=1)
    ]
    if len(build) != len(LIVE_BUDGETS) or not all(forced):
        problems.append(
            f"summary: the harness arm needs {len(LIVE_BUDGETS)} build sessions, the first "
            f"{FORCED_STOPS} ended by {FORCED_END}, or by {AGENT_END} with the harness stop step "
            f"run (found {len(build)}: {ends})"
        )
    for i, end in enumerate(ends[:FORCED_STOPS], start=1):
        if end == AGENT_END and not _stop_step_ran(by_index.get(i)):
            problems.append(
                f"summary: session {i} ended by {AGENT_END}, but the run log shows no harness "
                f"stop step for it (a session_stop with a handoff, {HANDOFF_FILE} and "
                f"{PROGRESS_FILE} written, and a commit before session {i + 1})"
            )
    stops = [s.get("session_index") for s in harness.get("session_stops", [])]
    if stops != list(range(1, FORCED_STOPS + 1)):
        problems.append(
            f"summary: the harness arm needs {FORCED_STOPS} session_stop events "
            f"(sessions 1-{FORCED_STOPS}), found {stops}"
        )


def validate(submission: Path) -> list[str]:
    """Problems with `<submission>/live/`; an empty list means the evidence is valid."""
    evidence = Path(submission) / EVIDENCE_DIR
    if not evidence.is_dir():
        return [
            f"{EVIDENCE_DIR}/ not found in the submission: run the live step "
            "(live/run_live.py --impl <folder> --forced-stops)"
        ]
    problems: list[str] = []
    needed = [TASK_FILE, COMMAND_FILE, OUTPUT_FILE, SUMMARY_FILE]
    missing = [n for n in needed if not (evidence / n).is_file()]
    if not (evidence / SCORES_DIR).is_dir():
        missing.append(f"{SCORES_DIR}/")
    if missing:
        return [f"{EVIDENCE_DIR}/: missing {', '.join(missing)}"]
    summary = _load_json(evidence / SUMMARY_FILE, problems)
    if not isinstance(summary, dict):
        return problems or [f"{EVIDENCE_DIR}/{SUMMARY_FILE}: not a JSON object"]
    _check_task(evidence, problems)
    _check_command(evidence, problems)
    _check_output(evidence, str(summary.get("ab_id")), problems)
    _check_summary(Path(submission), summary, problems)
    _check_records(evidence, summary, problems)
    return problems


def describe(submission: Path) -> str:
    """One line about valid evidence: the A/B id, the harness run, its sessions, and the cost."""
    evidence = Path(submission) / EVIDENCE_DIR
    summary = json.loads((evidence / SUMMARY_FILE).read_text(encoding="utf-8"))
    harness = summary["arms"]["harness"]
    costs = _COST_LINE.findall((evidence / OUTPUT_FILE).read_text(encoding="utf-8"))
    cost = f"${float(costs[-1][0]):.6f}" if costs else "?"
    return (
        f"A/B {summary['ab_id']}, harness run {harness['run_id']} ({harness['model']}): "
        f"{len(harness['session_stops'])} forced stops, status {harness['status']}, "
        f"claim {harness['claim']}; command cost {cost}"
    )
