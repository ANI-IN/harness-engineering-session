"""Grading criteria for one scenario run: migrations, redone work, and progress-file integrity.

The migration and redone-work measures reuse the S2 continuity check's own pieces:
`duplicate_tables` and `redone_pct` from `shipharness.checks.continuity`, and `count_heads` from
`shipharness.checks.r7_migrations`. The redone-lines measure is applied to every session, not
only session 2: lines added by any earlier session that a later session removes count as redone.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from a2_scenario.live_evidence import LIVE_POINTS
from a2_scenario.runner import PRODUCT_PATHS, SCENARIO_ENV, ScenarioRun
from shipharness.checks._proc import run_python, tail
from shipharness.checks.continuity import REDONE_THRESHOLD_PCT, duplicate_tables, redone_pct
from shipharness.checks.r7_migrations import count_heads
from shipharness.harness.state.templates import HANDOFF, PROGRESS, exec_plan_path

PROGRESS_SECTIONS = (
    "# Progress",
    "## Current feature",
    "## Done",
    "## In progress",
    "## Next",
    "## Session log",
)
_ENTRY = re.compile(
    r"^- Session (\d+) \((\w+)\): start (\w+), end (\w+), ended by (\w+)", re.MULTILINE
)
_SHA = re.compile(r"\b[0-9a-f]{7,40}\b")
_STEP_SUBJECT = re.compile(r"^(S\d+):")


@dataclass(frozen=True)
class Criterion:
    key: str
    points: int
    title: str
    hint: str


@dataclass(frozen=True)
class Outcome:
    key: str
    fraction: float  # share of the criterion's points earned in this scenario (0, 0.5, or 1)
    detail: str


CRITERIA: tuple[Criterion, ...] = (
    Criterion(
        "finished",
        13,
        "Feature finished across three forced stops",
        "three session_stop events, the last session ends with finish(done), the visible tests "
        "pass, and every step's files exist. Usually fails because a session redid earlier work "
        "and ran out of turns: fix the ledger and resume text (TODO 1, 2, 6).",
    ),
    Criterion(
        "one_head",
        9,
        "Migrations: exactly one Alembic head",
        "a session that does not see the current head in a `Migration heads: 1 (<rev>)` line "
        "writes its migration on the ticket's base revision (TODO 3, 6).",
    ),
    Criterion(
        "fresh_upgrade",
        9,
        "Migrations: `alembic upgrade head` works on an empty database",
        "two migrations that create the same table, or two heads, break a fresh upgrade.",
    ),
    Criterion(
        "no_duplicate_table",
        5,
        "Migrations: no table is created by two migrations",
        "the step that creates a table was done again: the next session did not see it as done "
        "(TODO 1, 2).",
    ),
    Criterion(
        "no_redone_lines",
        13,
        "Redone work: no session removes lines an earlier one added",
        "0% earns all points, under 30% (the continuity threshold) earns half. A step whose files "
        "were written but not committed needs a `written` line naming them (TODO 1).",
    ),
    Criterion(
        "steps_once",
        5,
        "Redone work: each step is committed exactly once",
        "a second `S<n>:` commit means a session did a step again.",
    ),
    Criterion(
        "progress_sections",
        3,
        "progress.md keeps its six sections in order: # Progress, Current feature, Done, "
        "In progress, Next, Session log",
        "restore missing sections, even when the agent rewrote the file (TODO 4).",
    ),
    Criterion(
        "session_log",
        8,
        "progress.md logs every session exactly once, in order",
        "one `- Session <n> ...` entry per session under `## Session log`; keep the entries when "
        "the agent rewrites the file (TODO 4).",
    ),
    Criterion(
        "history_consistent",
        4,
        "Session log entries match the run (commits, how each session ended)",
        "use the SessionResult's start_sha, end_sha, and ended_by; the format is "
        "`shipharness.harness.state.progress.session_entry` (TODO 4).",
    ),
    Criterion(
        "plan_completed",
        5,
        "Exec plan moved to docs/exec-plans/completed/, with an outcome",
        "move it when the last claim is done and git shows every step committed; replace "
        "'Not finished yet.' in Outcomes & Retrospective (TODO 7).",
    ),
    Criterion(
        "plan_ledger",
        5,
        "Exec plan Progress ticks every step with the commit that did it",
        "a `[x]` line per step id with a commit hash whose subject starts with `S<n>:`; derive it "
        "from git, never from what the agent wrote (TODO 1, 2).",
    ),
    Criterion(
        "plan_sessions",
        5,
        "Exec plan records every session and how it ended",
        "one line per session containing `Session <n>` and `ended by <reason>` (TODO 2).",
    ),
    Criterion(
        "handoff",
        4,
        "session-handoff.md: final summary, migration heads, agent notes kept",
        "`end of session <N>` for the last session, `Migration heads: 1 (`, and the "
        "`## Notes from the agent` section with the agent's notes as written (TODO 3).",
    ),
    Criterion(
        "clean_tree",
        2,
        "Every harness write is committed (clean working tree at the end)",
        "commit progress.md, session-handoff.md, and the exec plan at every stop and after the "
        "move (TODO 5, 7).",
    ),
)


def scenario_points() -> int:
    """Points of the scenario criteria (the test stand-in agent runs; reproducible)."""
    return sum(c.points for c in CRITERIA)


def total_points() -> int:
    """All points: the scenario criteria plus the live-run evidence criterion."""
    return scenario_points() + LIVE_POINTS


# -- helpers ---------------------------------------------------------------------------------


def _git(ws: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=ws, capture_output=True, text=True, check=False)
    return done.stdout if done.returncode == 0 else ""


def _read(ws: Path, rel: str) -> str | None:
    path = ws / rel
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None


def _section(text: str, heading: str) -> str:
    """Body of a `## ` section (up to the next `#`/`##` heading), or "" if it is missing."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == heading:
            body: list[str] = []
            for rest in lines[i + 1 :]:
                if rest.startswith("# ") or rest.startswith("## "):
                    break
                body.append(rest)
            return "\n".join(body)
    return ""


def _subject(ws: Path, sha: str) -> str:
    if not _git(ws, "rev-parse", "--verify", "-q", f"{sha}^{{commit}}"):
        return ""
    return _git(ws, "log", "-1", "--format=%s", sha).strip()


def _forced_stops(run: ScenarioRun) -> int:
    count = 0
    if run.events.exists():
        for line in run.events.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            count += event.get("run_id") == run.run_id and event.get("type") == "session_stop"
    return count


def _ok(key: str, passed: bool, detail: str) -> Outcome:
    return Outcome(key, 1.0 if passed else 0.0, detail)


# -- criteria ------------------------------------------------------------------------------------


def _finished(run: ScenarioRun) -> Outcome:
    ws, sessions = run.workspace, run.result.sessions
    problems = []
    stops, wanted = _forced_stops(run), len(run.scenario.budgets) - 1
    if stops != wanted:
        problems.append(f"{stops} forced stops (expected {wanted})")
    last = sessions[-1].ended_by if sessions else "none"
    if last != "claim_done":
        problems.append(f"last session ended by {last}, not claim_done")
    tests = run_python(["-m", "pytest", "tests/visible", "-q"], ws, dict(SCENARIO_ENV), timeout=300)
    if tests.returncode != 0:
        problems.append(f"visible tests fail: {tail(tests.stdout, 2)}")
    files = [str(p.relative_to(ws).as_posix()) for p in ws.rglob("*") if p.is_file()]
    for step in run.scenario.feature.steps:
        for slot in step.slots:
            if not any(slot.pattern().fullmatch(f) for f in files):
                problems.append(f"{step.id} file missing: {slot.path_for('<rev>')}")
    if run.result.status != "completed":
        problems.insert(0, f"run status {run.result.status}: {run.result.error}")
    detail = "; ".join(problems) or f"{stops} forced stops, finished in session {len(sessions)}"
    return _ok("finished", not problems, detail)


def _alembic(ws: Path, *args: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="a2-db-") as tmp:
        env = {
            **SCENARIO_ENV,
            "TEAMTRACK_DATABASE_URL": f"sqlite:///{Path(tmp).as_posix()}/fresh.db",
        }
        return run_python(["-m", "alembic", *args], ws, env, timeout=120)


def _migrations(run: ScenarioRun) -> list[Outcome]:
    ws = run.workspace
    heads = _alembic(ws, "heads")
    n = count_heads(heads.stdout) if heads.returncode == 0 else 0
    head_detail = f"{n} heads: {tail(heads.stdout + heads.stderr, 3)}"
    upgrade = _alembic(ws, "upgrade", "head")
    up_detail = (
        "fresh upgrade works"
        if upgrade.returncode == 0
        else tail(upgrade.stdout + upgrade.stderr, 2) or f"exit {upgrade.returncode}"
    )
    dupes = duplicate_tables(ws / "migrations" / "versions")
    dup_detail = "; ".join(f"{t} created by {', '.join(f)}" for t, f in dupes.items())
    return [
        _ok("one_head", n == 1, head_detail),
        _ok("fresh_upgrade", upgrade.returncode == 0, up_detail),
        _ok("no_duplicate_table", not dupes, dup_detail or "each table created once"),
    ]


def redone_by_session(run: ScenarioRun) -> dict[int, float]:
    """For each session after the first: % of lines added by earlier sessions that it removed.

    Session j's work is the change from the stop of session j-1 to its own stop, so anything the
    state layer changes in product files between sessions also counts."""
    ws, stops = run.workspace, run.stop_trees
    if not run.start_tree or not stops:
        return {}
    marks = [run.start_tree] + [stops[i] for i in sorted(stops)]
    out: dict[int, float] = {}
    for j in range(2, len(marks)):
        earlier = _git(ws, "diff", "--no-color", marks[0], marks[j - 1], "--", *PRODUCT_PATHS)
        during = _git(ws, "diff", "--no-color", marks[j - 1], marks[j], "--", *PRODUCT_PATHS)
        out[sorted(stops)[j - 1]] = redone_pct(earlier, during)
    return out


def _redone(run: ScenarioRun) -> list[Outcome]:
    ws = run.workspace
    by_session = redone_by_session(run)
    worst = max(by_session.values(), default=0.0)
    fraction = 1.0 if worst == 0 else (0.5 if worst < REDONE_THRESHOLD_PCT else 0.0)
    shown = ", ".join(f"session {k}: {v}%" for k, v in by_session.items()) or "no sessions"
    subjects = _git(ws, "log", "--format=%s").splitlines()
    counts = Counter(m.group(1) for s in subjects if (m := _STEP_SUBJECT.match(s)))
    wrong = [
        f"{step.id} x{counts.get(step.id, 0)}"
        for step in run.scenario.feature.steps
        if counts.get(step.id, 0) != 1
    ]
    return [
        Outcome("no_redone_lines", fraction, f"redone lines {shown}"),
        _ok("steps_once", not wrong, "commits per step: " + (", ".join(wrong) or "one each")),
    ]


def _progress(run: ScenarioRun) -> list[Outcome]:
    text = _read(run.workspace, PROGRESS) or ""
    lines = [line.strip() for line in text.splitlines()]
    positions = [lines.index(h) if h in lines else -1 for h in PROGRESS_SECTIONS]
    last_heading = max((i for i, line in enumerate(lines) if line.startswith("## ")), default=-1)
    ordered = (
        all(p >= 0 for p in positions)
        and positions == sorted(positions)
        and all(lines.count(h) == 1 for h in PROGRESS_SECTIONS)
        and positions[-1] == last_heading
    )
    missing = [h for h, p in zip(PROGRESS_SECTIONS, positions, strict=True) if p < 0]
    section_detail = "sections in order" if ordered else f"missing or out of order: {missing}"
    log = text.split("## Session log", 1)[1] if "## Session log" in text else ""
    entries = list(_ENTRY.finditer(log))
    indices = [int(m.group(1)) for m in re.finditer(r"^- Session (\d+)\b", log, re.MULTILINE)]
    sessions = run.result.sessions
    wanted = list(range(1, len(sessions) + 1))
    problems = []
    for result in sessions:
        match = next((m for m in entries if int(m.group(1)) == result.index), None)
        expect = (result.start_sha[:7] or "none", result.end_sha[:7] or "none", result.ended_by)
        got = (match.group(3), match.group(4), match.group(5)) if match else None
        if got != expect:
            problems.append(f"session {result.index}: {got} != {expect}")
    return [
        _ok("progress_sections", ordered, section_detail),
        _ok("session_log", indices == wanted, f"entries {indices}, sessions {wanted}"),
        _ok(
            "history_consistent",
            bool(sessions) and not problems,
            "; ".join(problems) or "every entry matches",
        ),
    ]


def _plan(run: ScenarioRun) -> list[Outcome]:
    ws, feature = run.workspace, run.scenario.feature
    active, completed = (
        exec_plan_path(feature.id, "active"),
        exec_plan_path(feature.id, "completed"),
    )
    done_text, active_text = _read(ws, completed), _read(ws, active)
    outcome_body = _section(done_text or "", "## Outcomes & Retrospective")
    moved = done_text is not None and active_text is None
    has_outcome = bool(outcome_body.strip()) and "Not finished yet" not in outcome_body
    plan_detail = (
        "moved, outcome recorded"
        if moved and has_outcome
        else f"completed={done_text is not None}, active={active_text is not None}, "
        f"outcome={'yes' if has_outcome else 'no'}"
    )
    text = done_text or active_text or ""
    progress = _section(text, "## Progress")
    missing = []
    for step in feature.steps:
        ticked = [
            line
            for line in progress.splitlines()
            if re.search(r"\[[xX]\]", line) and re.search(rf"\b{step.id}\b", line)
        ]
        proven = any(
            _subject(ws, sha).startswith(f"{step.id}:")
            for line in ticked
            for sha in _SHA.findall(line)
        )
        if not proven:
            missing.append(step.id)
    gaps = [
        f"session {r.index}"
        for r in run.result.sessions
        if not re.search(rf"\bSession {r.index}\b.*\bended by {r.ended_by}\b", text)
    ]
    return [
        _ok("plan_completed", moved and has_outcome, plan_detail),
        _ok(
            "plan_ledger",
            not missing,
            "every step ticked with its commit"
            if not missing
            else f"no [x] line with a matching commit for {missing}",
        ),
        _ok(
            "plan_sessions",
            bool(run.result.sessions) and not gaps,
            "every session recorded" if not gaps else f"missing: {gaps}",
        ),
    ]


def _handoff(run: ScenarioRun) -> Outcome:
    text = _read(run.workspace, HANDOFF)
    if text is None:
        return _ok("handoff", False, "session-handoff.md missing")
    last = len(run.result.sessions)
    problems = []
    if not re.search(rf"\bend of session {last}\b", text):
        problems.append(f"no 'end of session {last}'")
    if "Migration heads: 1 (" not in text:
        problems.append("no 'Migration heads: 1 ('")
    if "## Notes from the agent" not in text:
        problems.append("no '## Notes from the agent' section")
    for session, kind in run.scenario.behaviours.items():
        if kind == "note" and f"literal-agent-note-{session}" not in text:
            problems.append(f"the agent's note from session {session} was lost")
    return _ok("handoff", not problems, "; ".join(problems) or "complete")


def _clean(run: ScenarioRun) -> Outcome:
    status = _git(run.workspace, "status", "--porcelain", "-uall")
    shown = ", ".join(line[3:] for line in status.splitlines()[:5] if line.strip())
    status = status.strip()
    return _ok("clean_tree", not status, f"uncommitted: {shown}" if status else "clean")


def evaluate(run: ScenarioRun) -> list[Outcome]:
    """One outcome per criterion, in CRITERIA order."""
    found = [
        _finished(run),
        *_migrations(run),
        *_redone(run),
        *_progress(run),
        *_plan(run),
        _handoff(run),
        _clean(run),
    ]
    by_key = {o.key: o for o in found}
    return [by_key[c.key] for c in CRITERIA]
