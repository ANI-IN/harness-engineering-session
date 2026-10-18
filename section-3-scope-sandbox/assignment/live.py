"""Live step for assignment A3: one live A/B on F3, then your policy applied to what it recorded.

Usage (from the repository root; README "Step by step", step 8):
    uv run shipharness ab --section demo-3 --feature F3 --no-preview --purpose assignment \\
        2>&1 | tee ab-output.txt
    uv run python section-3-scope-sandbox/assignment/live.py collect --impl PATH \\
        --ab-output ab-output.txt --command \\
        "uv run shipharness ab --section demo-3 --feature F3 --no-preview --purpose assignment"
    uv run python section-3-scope-sandbox/assignment/live.py verify --impl PATH

collect copies the A/B's evidence into PATH/live/ (both ScoreRecords from exports/scores/, the
fields of ab.json the check needs, both arms' diff.patch) and writes verdict-<arm>.json: your
check_diff on the arm's diff (build phase) and on the files it changed in the test phase (test
phase), and your update_status on the arm's build-phase claim. When your status gate runs the
visible tests, they run in the agent sandbox image on a copy of the arm's final workspace, under
your policy(); each result is saved to PATH/live/<arm>/sandbox-log.json.

verify checks the evidence (ScoreRecord schema, ids, model, caps, both arms, F3, checkpoint_sha)
and re-runs your policy on the included files, replaying sandbox-log.json. It calls no model,
starts no container, and needs no keys. Exit code: 0 valid, 1 invalid, 2 no live/ folder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from shipharness.ab.demo import SECTION_STACKS
from shipharness.ab.score import ScoreRecord
from shipharness.config import Settings
from shipharness.sandbox import ExecResult, SandboxDenial

ARMS = ("bare", "harness")
SECTION = "demo-3"
FEATURE = "F3"
SCHEMA = "a3-live-verdict/1"


def _default(name: str) -> Any:
    """The class value of a setting (the code default in shipharness.config), not the local .env."""
    return Settings.model_fields[name].default


MODEL = _default("openai_model")  # gpt-6-luna
RUN_CAP = _default("max_run_cost_usd")  # MAX_RUN_COST_USD, per arm
REVIEW_CAP = _default("max_review_cost_usd")  # MAX_REVIEW_COST_USD, per review
COMMAND_CAP = _default("max_batch_cost_usd")  # MAX_BATCH_COST_USD, per command
HARNESS_LAYERS = sorted(SECTION_STACKS[SECTION])
EPS = 1e-6
# The feature is "F3" before 2026-10-18 and "Feature 3: <name>" since.
_AB_LINE = re.compile(r"^A/B (\S+) \((F\d+|Feature \d+: [^,]+), layers=", re.MULTILINE)
_COST_LINE = re.compile(r"^Cost: \$(\d+(?:\.\d+)?) \(this command: ([^;]*);", re.MULTILINE)
_SHA = re.compile(r"^[0-9a-f]{40}$")
_EVIDENCE_FILES = ("command.txt", "ab-output.txt", "ab-summary.json")


def _course_root(assignment: Path) -> Path:
    """The course repository root: the nearest folder above `assignment` with a pyproject.toml
    (found by that marker, not a fixed depth), else the folder that holds the section folder."""
    for folder in assignment.parents:
        if (folder / "pyproject.toml").is_file():
            return folder
    return assignment.parents[1]


REPO = _course_root(Path(__file__).resolve().parent)


def shown(path: Path) -> str:
    """The path relative to the repository root when it is inside it."""
    return path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path)


class LiveError(Exception):
    """A problem the learner fixes (missing run folder, file exists); printed without a trace."""


# -- sandboxes ------------------------------------------------------------------------------------


def _entry(command: str, result: ExecResult) -> dict[str, Any]:
    return {
        "command": command,
        "exit_code": result.exit_code,
        "output": result.output,
        "duration_ms": result.duration_ms,
        "timed_out": result.timed_out,
        "denied": result.denied.model_dump(mode="json") if result.denied else None,
    }


class RecordingSandbox:
    """Starts the inner sandbox on the first command and records every result."""

    def __init__(self, make_inner: Callable[[], Any]) -> None:
        self.make_inner = make_inner
        self.inner: Any = None
        self.log: list[dict[str, Any]] = []

    def start(self) -> str:
        return "recording"

    def exec(self, command: str, timeout_s: int) -> ExecResult:
        if self.inner is None:
            self.inner = self.make_inner()
            self.inner.start()
        result = self.inner.exec(command, timeout_s)
        self.log.append(_entry(command, result))
        return result

    def usage(self) -> dict[str, float]:
        return {"cpu_pct": 0.0, "mem_mb": 0.0, "mem_limit_mb": 0.0, "pids": 0}

    def stop(self) -> None:
        if self.inner is not None:
            self.inner.stop()


class ReplaySandbox:
    """Answers commands from a recorded log, in order; anything else gets a failed result."""

    def __init__(self, log: list[dict[str, Any]]) -> None:
        self.log = list(log)
        self.used = 0
        self.log_out: list[dict[str, Any]] = []

    def start(self) -> str:
        return "replay"

    def exec(self, command: str, timeout_s: int) -> ExecResult:
        if self.used < len(self.log) and self.log[self.used].get("command") == command:
            entry = self.log[self.used]
            self.used += 1
            denied = entry.get("denied")
            result = ExecResult(
                exit_code=int(entry["exit_code"]),
                output=str(entry["output"]),
                duration_ms=int(entry.get("duration_ms", 0)),
                timed_out=bool(entry.get("timed_out", False)),
                denied=SandboxDenial(**denied) if denied else None,
            )
        else:
            result = ExecResult(
                exit_code=1, output="replay: no recorded result for this command", duration_ms=0
            )
        self.log_out.append(_entry(command, result))
        return result

    def usage(self) -> dict[str, float]:
        return {"cpu_pct": 0.0, "mem_mb": 0.0, "mem_limit_mb": 0.0, "pids": 0}

    def stop(self) -> None:
        return None


def docker_sandbox(arm: str, workspace: Path) -> Callable[[], Any]:
    """The agent sandbox image (as `shipharness ab` starts it) on a copy of the arm's final
    workspace, so the run's own files never change. Your policy() decides what may run."""

    def make() -> Any:
        from a3scope.policy import policy

        from shipharness.sandbox import DockerSandbox

        if not workspace.is_dir():
            raise LiveError(
                f"the {arm} workspace {workspace} is gone; collect right after the A/B "
                "(workspaces live in the temp folder), or run the A/B again"
            )
        copy = Path(tempfile.mkdtemp(prefix=f"a3-live-{arm}-")) / "ws"
        shutil.copytree(workspace, copy, symlinks=True)
        settings = Settings()
        return DockerSandbox(
            policy(),
            settings.sandbox_image_agent,
            copy,
            None,
            f"a3-live-{arm}",
            arm,  # type: ignore[arg-type]
            runtime=settings.sandbox_runtime,
        )

    return make


# -- verdicts -------------------------------------------------------------------------------------


def _error(exc: BaseException) -> str:
    frames = traceback.extract_tb(exc.__traceback__)
    where = next((f for f in reversed(frames) if "a3scope" in f.filename), None)
    at = f" at {Path(where.filename).name}:{where.lineno}" if where else ""
    return f"{type(exc).__name__}: {exc}"[:240] + at


def _scope(policy: Any, phase: str, diff: bytes) -> dict[str, Any]:
    from a3scope.scope import check_diff

    try:
        verdict = check_diff(policy, phase, diff)
        refusals = [{"path": str(r.path), "code": str(r.code)} for r in verdict.refusals]
        return {"accepted": bool(verdict.accepted), "refusals": refusals}
    except Exception as exc:  # noqa: BLE001 - your code's error is part of the verdict
        return {"error": _error(exc)}


def _sections(diff: bytes) -> list[bytes]:
    """File sections of a git diff (each starts at a `diff --git` line)."""
    sections: list[list[bytes]] = []
    for line in diff.splitlines(keepends=True):
        if line.startswith(b"diff --git ") or not sections:
            sections.append([line])
        else:
            sections[-1].append(line)
    return [b"".join(s) for s in sections if s and s[0].startswith(b"diff --git ")]


def test_phase_diff(diff: bytes, files: list[str]) -> bytes:
    """The sections of `diff` that touch a file changed in the test phase. A section your
    parser cannot read is kept (fail closed)."""
    from a3scope.diffparse import parse_diff

    wanted = set(files)
    kept = []
    for section in _sections(diff):
        try:
            names = {p for c in parse_diff(section) for p in (c.old_path, c.new_path) if p}
        except Exception:  # noqa: BLE001
            names = wanted
        if names & wanted:
            kept.append(section)
    return b"".join(kept)


def _clock(captured_at: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(captured_at)
    except ValueError:
        stamp = datetime(1970, 1, 1, tzinfo=UTC)
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)


def _status(arm: dict[str, Any], feature_id: str, sandbox: Any, captured_at: str) -> dict[str, Any]:
    from a3scope.status import SessionEnd, update_status

    claim = arm["claims"].get("build")
    shas = arm["phase_shas"].get("build")
    end = SessionEnd(
        phase="build",
        last_claim={"phase": "build", "claim": claim, "summary": ""} if claim else None,
        verify_layer="verify" in arm["layers"],
        gate=None,
        head_commit=shas[1] if shas else "",
    )
    document = {"features": [{"id": feature_id, "passes": False}]}
    stamp = _clock(captured_at)
    try:
        decision = update_status(document, feature_id, end, sandbox, now=lambda: stamp)
        out: dict[str, Any] = {
            "kind": decision.kind,
            "message": decision.message,
            "evidence": decision.evidence,
        }
    except LiveError:
        raise  # the sandbox could not start: the learner fixes that, then collects again
    except Exception as exc:  # noqa: BLE001 - your code's error is part of the verdict
        out = {"error": _error(exc)}
    return out


def arm_verdict(
    live: Path, summary: dict[str, Any], arm_name: str, score: dict[str, Any], sandbox: Any
) -> dict[str, Any]:
    """Your policy on one arm's recorded diff, test-phase files, and build-phase claim."""
    from a3scope.scope import PhasePolicy

    arm = summary["arms"][arm_name]
    diff = (live / arm_name / "diff.patch").read_bytes()
    state_layer = "state" in arm["layers"]
    allowed = arm["allowed_paths"]
    policy = PhasePolicy(allowed_paths=allowed, state_layer=state_layer)
    try:
        test_diff = test_phase_diff(diff, arm["test_phase_files"])
        test = {"files": arm["test_phase_files"], **_scope(policy, "test", test_diff)}
    except Exception as exc:  # noqa: BLE001
        test = {"files": arm["test_phase_files"], "error": _error(exc)}
    status = _status(arm, summary["feature_id"], sandbox, score.get("captured_at", ""))
    log = getattr(sandbox, "log_out", None)
    if log is None:
        log = getattr(sandbox, "log", [])
    status["commands"] = [e["command"] for e in log]
    verdict = {
        "schema": SCHEMA,
        "ab_id": summary["ab_id"],
        "arm": arm_name,
        "run_id": arm["run_id"],
        "feature_id": summary["feature_id"],
        "diff": {
            "path": f"{arm_name}/diff.patch",
            "sha256": hashlib.sha256(diff).hexdigest(),
        },
        "policy": {"allowed_paths": allowed, "state_layer": state_layer},
        "scope": {"build": _scope(policy, "build", diff), "test": test},
        "status": status,
        "referee": {
            key: score.get(key)
            for key in ("status", "claim", "out_of_scope_files", "test_phase_source_edits")
        }
        | {"passed_primary": score.get("passed_primary")},
    }
    return json.loads(json.dumps(verdict))


# -- collect --------------------------------------------------------------------------------------


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ab_summary(ab_id: str, record: dict[str, Any]) -> dict[str, Any]:
    """The fields of ab.json the check needs (no ticket text, no claim summaries)."""
    arms = {}
    for name, arm in record["arms"].items():
        spec, result = arm["spec"], arm["result"]
        arms[name] = {
            "run_id": spec["run_id"],
            "model": spec["model"],
            "layers": sorted(spec["layers"]),
            "cost_limit_usd": spec["cost_limit_usd"],
            "allowed_paths": spec["allowed_paths"],
            "status": result["status"],
            "claim": result["claim"],
            "claims": result.get("claims", {}),
            "phase_shas": result["phase_shas"],
            "cost_usd": result["cost_usd"],
            "turns_total": result["turns_total"],
            "test_phase_files": arm.get("test_phase_files", []),
        }
    return {
        "source": f"ab.json of A/B {ab_id}",
        "ab_id": ab_id,
        "section": record.get("section"),
        "checkpoint_sha": record.get("checkpoint_sha"),
        "from_working_tree": record.get("from_working_tree"),
        "feature_id": record["task"]["feature_id"],
        "arms": arms,
    }


def collect(args: argparse.Namespace) -> int:
    impl = args.impl.resolve()
    out = (args.out or impl / "live").resolve()
    output = args.ab_output.read_text(encoding="utf-8", errors="replace")
    ids = _AB_LINE.findall(output)
    ab_id = args.ab or (ids[-1][0] if ids else "")
    if not ab_id:
        raise LiveError(f"no 'A/B <id> (...)' line in {args.ab_output}; pass --ab <id>")
    settings = Settings() if args.runs is None or args.exports is None else None
    runs = args.runs or settings.runs_dir  # type: ignore[union-attr]
    exports = args.exports or settings.exports_dir  # type: ignore[union-attr]
    ab_dir = Path(runs) / ab_id
    if not (ab_dir / "ab.json").is_file():
        raise LiveError(f"no ab.json in {ab_dir}")
    if out.exists() and any(out.iterdir()):
        if not args.force:
            raise LiveError(f"{out} already holds evidence; pass --force to replace it")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    summary = ab_summary(ab_id, _read_json(ab_dir / "ab.json"))
    _write_json(out / "ab-summary.json", summary)
    (out / "command.txt").write_text(args.command.strip() + "\n", encoding="utf-8")
    (out / "ab-output.txt").write_text(output, encoding="utf-8")
    scores: dict[str, dict[str, Any]] = {}
    for name, arm in summary["arms"].items():
        source = Path(exports) / "scores" / f"{arm['run_id']}.json"
        if not source.is_file():
            raise LiveError(f"no ScoreRecord for the {name} arm: {source}")
        (out / "scores").mkdir(exist_ok=True)
        shutil.copyfile(source, out / "scores" / source.name)
        scores[name] = _read_json(source)
        diff = ab_dir / name / "diff.patch"
        (out / name).mkdir(exist_ok=True)
        (out / name / "diff.patch").write_bytes(diff.read_bytes() if diff.is_file() else b"")

    sys.path.insert(0, str(impl))
    workspaces = Path(args.workspaces) if args.workspaces else _workspace_base()
    for name in summary["arms"]:
        if args.replay_logs is not None:
            log_file = args.replay_logs / f"{name}.json"
            sandbox: Any = ReplaySandbox(_read_json(log_file) if log_file.is_file() else [])
        else:
            sandbox = RecordingSandbox(docker_sandbox(name, workspaces / ab_id / name / "ws"))
        try:
            verdict = arm_verdict(out, summary, name, scores[name], sandbox)
        finally:
            sandbox.stop()
        log = sandbox.log_out if isinstance(sandbox, ReplaySandbox) else sandbox.log
        _write_json(out / name / "sandbox-log.json", log)
        _write_json(out / f"verdict-{name}.json", verdict)
        build, test = verdict["scope"]["build"], verdict["scope"]["test"]
        print(
            f"{name:<8} build scope: {_scope_text(build)}; test scope: {_scope_text(test)}; "
            f"status: {verdict['status'].get('kind', verdict['status'].get('error'))}"
        )
    print(f"Evidence written to {shown(out)}. Next: live.py verify --impl {shown(impl)}")
    return 0


def _scope_text(part: dict[str, Any]) -> str:
    if "error" in part:
        return f"error ({part['error'][:60]})"
    return "accepted" if part["accepted"] else f"{len(part['refusals'])} refused"


def _workspace_base() -> Path:
    from shipharness.ab.workspace import workspace_base

    return workspace_base()


# -- verify ---------------------------------------------------------------------------------------


def _command_problems(command: str) -> list[str]:
    tokens = command.split()
    if tokens[:2] == ["make", "demo-3"] and len(tokens) == 2:
        return []
    ok = (
        "shipharness" in tokens
        and "ab" in tokens
        and "--section" in tokens
        and tokens[tokens.index("--section") + 1 : tokens.index("--section") + 2] == [SECTION]
        and "--feature" in tokens
        and tokens[tokens.index("--feature") + 1 : tokens.index("--feature") + 2] == [FEATURE]
    )
    banned = [t for t in tokens if t.split("=")[0] in ("--replay", "--swap", "--layers", "--k")]
    banned += [t for t in tokens if t.split("=")[0] in ("--from-working-tree", "--example")]
    if ok and not banned:
        return []
    return [
        f"command.txt: the command must be `make demo-3` or `shipharness ab --section demo-3 "
        f"--feature F3` (optionally --no-preview and --purpose assignment), not {command!r}"
    ]


def _arm_problems(name: str, arm: dict[str, Any]) -> list[str]:
    problems = []
    if arm.get("model") != MODEL:
        problems.append(f"{name}: agent model {arm.get('model')!r}, the class model is {MODEL}")
    expected = HARNESS_LAYERS if name == "harness" else []
    if arm.get("layers") != expected:
        problems.append(f"{name}: layers {arm.get('layers')}, {SECTION} uses {expected}")
    limit = float(arm.get("cost_limit_usd", 0.0))
    if limit > RUN_CAP + EPS:
        problems.append(f"{name}: run cap ${limit:.2f} is above MAX_RUN_COST_USD ${RUN_CAP:.2f}")
    if float(arm.get("cost_usd", 0.0)) > min(limit, RUN_CAP) + EPS:
        problems.append(f"{name}: cost ${arm.get('cost_usd')} is over the run cap")
    if arm.get("status") == "ERROR" or int(arm.get("turns_total", 0)) < 1:
        problems.append(f"{name}: status {arm.get('status')} with no agent turns is not a live run")
    return problems


def _score_problems(
    live: Path, summary: dict[str, Any]
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    problems: list[str] = []
    by_arm: dict[str, dict[str, Any]] = {}
    files = sorted((live / "scores").glob("*.json")) if (live / "scores").is_dir() else []
    run_ids = {arm["run_id"]: name for name, arm in summary["arms"].items()}
    for path in files:
        try:
            record = ScoreRecord.model_validate(_read_json(path))
        except (ValidationError, ValueError) as exc:
            first = str(exc).splitlines()[0:3]
            problems.append(f"scores/{path.name} is not a valid ScoreRecord: {' '.join(first)}")
            continue
        name = run_ids.get(record.run_id)
        if record.run_id != path.stem or name is None:
            problems.append(
                f"scores/{path.name}: run_id {record.run_id!r} does not match the file name "
                "and a run id in ab-summary.json"
            )
            continue
        arm = summary["arms"][name]
        if record.arm != name:
            problems.append(f"scores/{path.name}: arm {record.arm}, ab-summary.json says {name}")
        if record.ab_id != summary["ab_id"]:
            problems.append(
                f"scores/{path.name}: ab_id {record.ab_id}, expected {summary['ab_id']}"
            )
        if record.feature_id != FEATURE:
            problems.append(f"scores/{path.name}: feature {record.feature_id}, expected {FEATURE}")
        if not record.checkpoint_sha or record.checkpoint_sha != summary.get("checkpoint_sha"):
            problems.append(
                f"scores/{path.name}: checkpoint_sha {record.checkpoint_sha!r} is missing or "
                "differs from ab-summary.json"
            )
        if record.recorded:
            problems.append(f"scores/{path.name}: recorded is true (a replay, not a live run)")
        if not record.sandboxed:
            problems.append(f"scores/{path.name}: sandboxed is false (the class runs in Docker)")
        if record.cost_usd > RUN_CAP + EPS or abs(record.cost_usd - arm["cost_usd"]) > EPS:
            problems.append(
                f"scores/{path.name}: cost ${record.cost_usd} is over the run cap "
                f"${RUN_CAP:.2f} or differs from ab-summary.json"
            )
        if record.review_cost_usd > REVIEW_CAP + EPS:
            problems.append(f"scores/{path.name}: review cost over the cap ${REVIEW_CAP:.2f}")
        if sorted(record.layers) != arm["layers"] or record.status != arm["status"]:
            problems.append(f"scores/{path.name}: layers or status differ from ab-summary.json")
        by_arm[name] = record.model_dump(mode="json")
    for name in ARMS:
        if name in summary["arms"] and name not in by_arm and not problems:
            problems.append(f"no valid score record for the {name} arm in scores/")
    return problems, by_arm


def evidence_problems(live: Path) -> tuple[list[str], dict[str, Any] | None, dict[str, Any]]:
    """(problems, ab summary, score records by arm) for a live/ folder."""
    missing = [n for n in _EVIDENCE_FILES if not (live / n).is_file()]
    missing += [f"{a}/diff.patch" for a in ARMS if not (live / a / "diff.patch").is_file()]
    if missing:
        return [f"missing {', '.join(missing)}"], None, {}
    try:
        summary = _read_json(live / "ab-summary.json")
        arms = summary["arms"]
    except (ValueError, KeyError, TypeError) as exc:
        return [f"ab-summary.json is not readable: {exc}"], None, {}
    problems = _command_problems((live / "command.txt").read_text(encoding="utf-8").strip())
    if summary.get("section") != SECTION:
        problems.append(f"ab-summary.json: section {summary.get('section')!r}, expected {SECTION}")
    if summary.get("feature_id") != FEATURE:
        problems.append(f"ab-summary.json: feature {summary.get('feature_id')!r}, expected F3")
    if not _SHA.match(str(summary.get("checkpoint_sha") or "")) or summary.get("from_working_tree"):
        problems.append("ab-summary.json: no pinned checkpoint_sha (an A/B from a checkpoint tag)")
    if sorted(arms) != sorted(ARMS):
        problems.append(f"ab-summary.json: arms {sorted(arms)}, expected both arms {list(ARMS)}")
        return problems, None, {}
    for name in ARMS:
        problems += _arm_problems(name, arms[name])
    if len({arms[a]["run_id"] for a in ARMS}) != len(ARMS):
        problems.append("ab-summary.json: both arms have the same run id")
    output = (live / "ab-output.txt").read_text(encoding="utf-8", errors="replace")
    if summary.get("ab_id") not in [ab for ab, _feature in _AB_LINE.findall(output)]:
        problems.append(f"ab-output.txt: no 'A/B {summary.get('ab_id')} (F3, ...' line")
    costs = _COST_LINE.findall(output)
    if not costs:
        problems.append("ab-output.txt: no 'Cost: $...' line")
        total = 0.0
    else:
        total_text, models = costs[-1]
        total = float(total_text)
        if total > COMMAND_CAP + EPS:
            problems.append(f"ab-output.txt: command cost ${total} is over ${COMMAND_CAP:.2f}")
        if MODEL not in models:
            problems.append(f"ab-output.txt: the cost line names no {MODEL} calls")
    score_problems, scores = _score_problems(live, summary)
    problems += score_problems
    if costs and len(scores) == len(ARMS):
        spent = sum(s["cost_usd"] + s["review_cost_usd"] for s in scores.values())
        if spent > total + 1e-5:
            problems.append(f"score records spend ${spent:.6f}, more than the cost line ${total}")
    return problems, summary, scores


def verdict_problems(
    live: Path, summary: dict[str, Any], scores: dict[str, dict[str, Any]]
) -> list[str]:
    problems = []
    for name in ARMS:
        path = live / f"verdict-{name}.json"
        log_path = live / name / "sandbox-log.json"
        if not path.is_file() or not log_path.is_file():
            problems.append(f"missing verdict-{name}.json or {name}/sandbox-log.json")
            continue
        try:
            given = _read_json(path)
            log = _read_json(log_path)
            if not isinstance(log, list):
                raise ValueError("not a list")
        except ValueError as exc:
            problems.append(f"verdict-{name}.json or {name}/sandbox-log.json: {exc}")
            continue
        replay = ReplaySandbox(log)
        again = arm_verdict(live, summary, name, scores[name], replay)
        if given.get("diff", {}).get("sha256") != again["diff"]["sha256"]:
            problems.append(f"verdict-{name}.json: diff sha256 differs from {name}/diff.patch")
        elif given != again:
            keys = sorted(k for k in again if given.get(k) != again.get(k))
            problems.append(
                f"verdict-{name}.json differs from your policy re-run on the included files "
                f"(fields: {', '.join(keys)})"
            )
        if replay.used < len(log):
            problems.append(
                f"{name}/sandbox-log.json holds {len(log) - replay.used} result(s) your status "
                "gate never asked for"
            )
    return problems


def verify_folder(impl: Path, live: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "live": shown(live),
        "present": live.is_dir(),
        "evidence_ok": False,
        "verdicts_ok": False,
        "evidence_problems": [],
        "verdict_problems": [],
    }
    if not live.is_dir():
        result["evidence_problems"] = [f"no live/ folder at {shown(live)}"]
        return result
    problems, summary, scores = evidence_problems(live)
    result["evidence_problems"] = problems
    result["evidence_ok"] = not problems
    if summary is None or len(scores) != len(ARMS):
        result["verdict_problems"] = ["verdicts not checked: the evidence is incomplete"]
        return result
    sys.path.insert(0, str(impl))
    result["verdict_problems"] = verdict_problems(live, summary, scores)
    result["verdicts_ok"] = not result["verdict_problems"]
    return result


def verify(args: argparse.Namespace) -> int:
    impl = args.impl.resolve()
    live = (args.live or impl / "live").resolve()
    result = verify_folder(impl, live)
    if args.json is not None:
        args.json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"A3 live evidence: {shown(live)}")
    for label, key, problems in (
        ("evidence", "evidence_ok", "evidence_problems"),
        ("verdicts", "verdicts_ok", "verdict_problems"),
    ):
        print(f"  {label:<9} {'ok' if result[key] else 'FAIL'}")
        for problem in result[problems]:
            print(f"    - {problem}")
    if not result["present"]:
        return 2
    return 0 if result["evidence_ok"] and result["verdicts_ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="action", required=True)
    c = sub.add_parser("collect", help="copy the A/B's evidence into live/ and write verdicts")
    c.add_argument("--impl", type=Path, required=True, help="folder holding a3scope/")
    c.add_argument("--ab-output", type=Path, required=True, help="the A/B's saved terminal output")
    c.add_argument("--command", required=True, help="the exact command you ran")
    c.add_argument("--ab", default=None, help="A/B id (default: the last one in --ab-output)")
    c.add_argument("--out", type=Path, default=None, help="default: <impl>/live")
    c.add_argument("--runs", type=Path, default=None, help="default: RUNS_DIR")
    c.add_argument("--exports", type=Path, default=None, help="default: EXPORTS_DIR")
    c.add_argument("--workspaces", type=Path, default=None, help="default: the arm workspaces")
    c.add_argument(
        "--replay-logs",
        type=Path,
        default=None,
        help="replay <dir>/<arm>.json sandbox results instead of starting a container",
    )
    c.add_argument("--force", action="store_true", help="replace an existing live/ folder")
    v = sub.add_parser("verify", help="check live/ and re-run your policy on it (offline)")
    v.add_argument("--impl", type=Path, required=True, help="folder holding a3scope/")
    v.add_argument("--live", type=Path, default=None, help="default: <impl>/live")
    v.add_argument("--json", type=Path, default=None, help="also write the result as JSON")
    args = parser.parse_args(argv)
    try:
        return collect(args) if args.action == "collect" else verify(args)
    except LiveError as exc:
        print(f"x {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
