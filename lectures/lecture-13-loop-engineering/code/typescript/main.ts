// loop-runner: one goal, one maker, one independent checker, one clock.
//
// The runner repeats a round (the maker takes one step, the checker grades
// the whole goal) until its stopping condition fires or the loop's
// simulated clock cannot afford another round. `--stop-on` selects the one
// signal the stopping condition reads: `checker` reads the independent
// verdict over every criterion, `maker` reads the maker's own report about
// the step it just took. Nothing else differs between the two runs.
//
// The exit code is the goal's state when the loop stopped, re-evaluated
// from the workspace rather than taken from whatever signal ended the run:
// 0 when every criterion is met, 1 when the loop stopped with work
// remaining. So a run that stops on the maker's report exits 1 while
// reporting that the maker said it was finished.
//
// The clock is a step counter, not a wall clock: the maker's turn costs
// MAKER_TICKS and the checker's turn costs CHECKER_TICKS, and a round is
// only started when the remaining budget covers both. Nothing here reads
// real time, and the workspace is loaded once and edited in memory, so the
// committed fixture never changes and every run is idempotent. SPEC.md
// pins the check engine, the maker's step rule, the checker's verdict, the
// stopping condition, and the clock.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const MAKER_TICKS = 2;
const CHECKER_TICKS = 1;
const ROUND_TICKS = MAKER_TICKS + CHECKER_TICKS;

interface Check {
  kind: string;
  path: string;
  key?: string;
  prefix?: string;
}

interface Step {
  path: string;
  line: string;
}

interface Criterion {
  id: string;
  check: Check;
  step: Step;
}

interface Goal {
  loop: string;
  goal: string;
  budget_ticks: number;
  criteria: Criterion[];
}

interface CarriedRound {
  round: number;
  criterion: string | null;
  maker_reported: string;
  checker_verdict: string;
}

interface LoopState {
  loop: string;
  clock: number;
  status: string;
  rounds: CarriedRound[];
}

interface Graded {
  criterion: string;
  status: string;
  detail: string;
}

interface MakerTurn {
  criterion: string | null;
  action: string;
  reports_done: boolean;
  why: string;
}

interface CheckerTurn {
  verdict: string;
  met: string[];
  unmet: string[];
  checked: Graded[];
}

type Files = Map<string, string>;

// --------------------------------------------------------------------------
// The workspace: a path-to-text map loaded once and edited in memory.
// --------------------------------------------------------------------------

function loadWorkspace(root: string): Files {
  const files: Files = new Map();
  const walk = (dir: string, prefix: string): void => {
    for (const name of readdirSync(dir).sort()) {
      const full = join(dir, name);
      const relative = prefix ? `${prefix}/${name}` : name;
      if (statSync(full).isDirectory()) walk(full, relative);
      else files.set(relative, readFileSync(full, "utf8"));
    }
  };
  walk(root, "");
  return files;
}

// --------------------------------------------------------------------------
// The check engine: the deterministic stand-in for running the real command.
// --------------------------------------------------------------------------

function runCheck(files: Files, check: Check): [boolean, string] {
  const path = check.path;
  if (!files.has(path)) return [false, `${path} missing`];
  const lines = (files.get(path) as string).split(/\r?\n/);
  if (check.kind === "key-declared-once") {
    const key = check.key as string;
    const count = lines.filter((line) => line.startsWith(`${key}=`)).length;
    if (count === 1) return [true, `${path} declares ${key} once`];
    if (count === 0) return [false, `${path} has no ${key}= line`];
    return [false, `${path} declares ${key} ${count} times`];
  }
  if (check.kind === "file-has-line") {
    const prefix = check.prefix as string;
    if (lines.some((line) => line.startsWith(prefix))) {
      return [true, `${path} has a line starting with ${prefix}`];
    }
    return [false, `${path} has no line starting with ${prefix}`];
  }
  throw new Error(`unknown check kind: ${check.kind}`);
}

// Every criterion of the goal, checked against the workspace as it is.
function gradeGoal(files: Files, criteria: Criterion[]): Graded[] {
  return criteria.map((criterion) => {
    const [passed, detail] = runCheck(files, criterion.check);
    return { criterion: criterion.id, status: passed ? "pass" : "fail", detail };
  });
}

function withStatus(graded: Graded[], status: string): string[] {
  return graded.filter((row) => row.status === status).map((row) => row.criterion);
}

// --------------------------------------------------------------------------
// The maker: one step per round, chosen from the loop state's memory.
// --------------------------------------------------------------------------

function applyStep(files: Files, step: Step): string {
  const { path, line } = step;
  if (!files.has(path)) {
    files.set(path, line + "\n");
    return `created ${path} with ${line}`;
  }
  files.set(path, (files.get(path) as string) + line + "\n");
  return `appended ${line} to ${path}`;
}

// Take one step towards the goal, then report on that step alone. The step
// is the first unmet criterion this loop has not attempted before, which is
// why the loop state exists: without the record of what earlier rounds
// tried, the maker would take the same step forever.
function makerTurn(files: Files, criteria: Criterion[], attempted: (string | null)[]): MakerTurn {
  const unmet = withStatus(gradeGoal(files, criteria), "fail");
  const target = criteria.find(
    (criterion) => unmet.includes(criterion.id) && !attempted.includes(criterion.id),
  );
  if (target === undefined) {
    return {
      criterion: null,
      action: "no step taken: every unmet criterion has already been attempted once",
      reports_done: false,
      why: "the maker changed nothing this round, so it claims nothing",
    };
  }
  const action = applyStep(files, target.step);
  const [passed, detail] = runCheck(files, target.check);
  return {
    criterion: target.id,
    action,
    reports_done: passed,
    why: passed
      ? `${target.id} passes after the edit, and the maker reads the step ` +
        "it just finished as the job being finished"
      : `${target.id} still fails after the edit: ${detail}`,
  };
}

// --------------------------------------------------------------------------
// The checker: independent, and it grades the goal rather than the step.
// --------------------------------------------------------------------------

function checkerTurn(files: Files, criteria: Criterion[]): CheckerTurn {
  const graded = gradeGoal(files, criteria);
  const unmet = withStatus(graded, "fail");
  return {
    verdict: unmet.length > 0 ? "fail" : "pass",
    met: withStatus(graded, "pass"),
    unmet,
    checked: graded,
  };
}

// --------------------------------------------------------------------------
// The loop.
// --------------------------------------------------------------------------

export function runLoop(goal: Goal, state: LoopState, files: Files, stopOn: string) {
  const criteria = goal.criteria;
  const budget = goal.budget_ticks;
  let clock = state.clock;
  const carried: CarriedRound[] = state.rounds.map((entry) => ({ ...entry }));
  const rounds = [];
  let number = carried.length;
  let stop;

  for (;;) {
    number += 1;
    if (clock + ROUND_TICKS > budget) {
      stop = {
        round: number,
        clock,
        fired_on: "clock",
        reason:
          `round ${number} costs ${ROUND_TICKS} ticks and the ${budget} tick ` +
          `budget has ${budget - clock} left, so the loop cannot start it`,
      };
      break;
    }

    const maker = makerTurn(files, criteria, carried.map((entry) => entry.criterion));
    const checker = checkerTurn(files, criteria);
    clock += ROUND_TICKS;

    const passed = stopOn === "maker" ? maker.reports_done : checker.verdict === "pass";
    const signal = passed ? "pass" : "fail";
    const decision = passed ? "stop" : "continue";
    rounds.push({
      round: number,
      clock,
      maker,
      checker,
      stopping_condition: { reads: stopOn, signal, decision },
    });
    carried.push({
      round: number,
      criterion: maker.criterion,
      maker_reported: maker.reports_done ? "done" : "not-done",
      checker_verdict: checker.verdict,
    });
    if (decision === "stop") {
      stop = {
        round: number,
        clock,
        fired_on: stopOn,
        reason: `the stopping condition read the ${stopOn}'s signal as pass`,
      };
      break;
    }
  }

  // The verdict is re-graded from the workspace, not taken from the signal
  // that ended the run: the loop's own stopping condition is exactly what
  // is on trial here.
  const final = gradeGoal(files, criteria);
  const unmet = withStatus(final, "fail");
  let result: string;
  if (unmet.length === 0) result = "goal-reached";
  else if (stop.fired_on === "clock") result = "budget-exhausted";
  else result = "stopped-early";

  return {
    loop: goal.loop,
    goal: goal.goal,
    stop_on: stopOn,
    budget_ticks: budget,
    rounds,
    stop,
    loop_state: { loop: state.loop, clock, status: result, rounds: carried },
    unmet,
    result,
  };
}

const USAGE = "usage: main.ts <loop-dir> --stop-on=maker|checker";

function main(argv: readonly string[]): number {
  const target = argv[2];
  const flag = argv[3];
  if (argv.length !== 4 || !target || (flag !== "--stop-on=maker" && flag !== "--stop-on=checker")) {
    console.error(USAGE);
    return 2;
  }
  const goalPath = join(target, "goal.json");
  const statePath = join(target, "loop-state.json");
  if (!existsSync(goalPath) || !existsSync(statePath)) {
    console.error(`error: not a loop (needs goal.json and loop-state.json): ${target}`);
    return 2;
  }
  const goal = JSON.parse(readFileSync(goalPath, "utf8")) as Goal;
  const state = JSON.parse(readFileSync(statePath, "utf8")) as LoopState;
  const files = loadWorkspace(join(target, "workspace"));
  const report = runLoop(goal, state, files, flag.slice("--stop-on=".length));
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return report.result === "goal-reached" ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
