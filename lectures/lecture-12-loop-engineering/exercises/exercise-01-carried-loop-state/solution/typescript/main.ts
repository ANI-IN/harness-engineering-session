// carried-loop-state: the memory that turns retries into a loop.
//
// A loop directory holds a goal, a workspace, and a loop state written by
// whatever ran the earlier rounds. This runner takes the next rounds. Each
// round reads the carried state to learn which criteria have already been
// attempted, attempts the first criterion the state does not name, and
// writes that attempt back into the state before the next round begins.
// Drop any one of those three moves and the runner is N independent
// retries: it re-attempts work the loop already did and spends its round
// budget on it.
//
// The workspace is loaded once and edited in memory and the loop state is
// carried in memory, so nothing under the loop directory is written and
// every run over a committed fixture is idempotent. Nothing here reads real
// time: the budget is a round count carried in the state, not a clock.
// SPEC.md pins the check engine, the step rule, the state schema, and the
// stop reasons.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

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
  max_rounds: number;
  criteria: Criterion[];
}

interface Attempt {
  round: number;
  criterion: string;
  outcome: string;
}

interface LoopState {
  loop: string;
  rounds_done: number;
  attempted: Attempt[];
}

interface Stop {
  after_round: number;
  reason: string;
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

// Every criterion of the goal that the workspace does not satisfy.
function unmetCriteria(files: Files, criteria: Criterion[]): string[] {
  return criteria.filter((c) => !runCheck(files, c.check)[0]).map((c) => c.id);
}

function applyStep(files: Files, step: Step): string {
  const { path, line } = step;
  if (!files.has(path)) {
    files.set(path, line + "\n");
    return `created ${path} with ${line}`;
  }
  files.set(path, (files.get(path) as string) + line + "\n");
  return `appended ${line} to ${path}`;
}

// --------------------------------------------------------------------------
// The carried state: read at the top of a round, written at the bottom.
// --------------------------------------------------------------------------

// The criteria this loop has already attempted, in the order it tried them.
// Every entry in `attempted` records a round that ran to completion, so all
// `rounds_done` of them count: an attempt that ended `unmet` was still an
// attempt, and re-taking its step is the repetition this memory exists to
// prevent.
function attemptedCriteria(state: LoopState): string[] {
  return state.attempted.map((entry) => entry.criterion);
}

// The first criterion in goal order that the carried state does not name.
function nextCriterion(criteria: Criterion[], attempted: string[]): Criterion | undefined {
  return criteria.find((criterion) => !attempted.includes(criterion.id));
}

// Write the round into the carried state, before the next round reads it.
function recordAttempt(state: LoopState, round: number, criterion: string, outcome: string): void {
  state.attempted.push({ round, criterion, outcome });
  state.rounds_done = round;
}

// --------------------------------------------------------------------------
// The loop.
// --------------------------------------------------------------------------

export function runLoop(goal: Goal, state: LoopState, files: Files) {
  const criteria = goal.criteria;
  const maxRounds = goal.max_rounds;
  const carried: LoopState = {
    loop: state.loop,
    rounds_done: state.rounds_done,
    attempted: state.attempted.map((entry) => ({ ...entry })),
  };
  const rounds = [];
  let endedOn: string;
  let stop: Stop;

  for (;;) {
    if (carried.rounds_done >= maxRounds) {
      endedOn = "budget";
      stop = {
        after_round: carried.rounds_done,
        reason:
          `the loop has run ${carried.rounds_done} of its ` +
          `${maxRounds} rounds, so it cannot start another`,
      };
      break;
    }

    const memory = attemptedCriteria(carried);
    const target = nextCriterion(criteria, memory);
    if (target === undefined) {
      endedOn = "steps";
      stop = {
        after_round: carried.rounds_done,
        reason:
          "the carried state names every criterion of the goal, " +
          "so there is no step left to take",
      };
      break;
    }

    const round = carried.rounds_done + 1;
    const action = applyStep(files, target.step);
    const [passed, detail] = runCheck(files, target.check);
    recordAttempt(carried, round, target.id, passed ? "met" : "unmet");
    const unmetAfter = unmetCriteria(files, criteria);
    rounds.push({
      round,
      memory_read: memory,
      chosen_criterion: target.id,
      step_taken: action,
      criterion_met_after: passed ? "met" : "unmet",
      detail,
      unmet_after: unmetAfter,
    });
    if (unmetAfter.length === 0) {
      endedOn = "goal";
      stop = {
        after_round: round,
        reason: `every criterion of the goal is met after round ${round}`,
      };
      break;
    }
  }

  const unmet = unmetCriteria(files, criteria);
  let verdict: string;
  if (unmet.length === 0) verdict = "goal-reached";
  else if (endedOn === "budget") verdict = "budget-exhausted";
  else verdict = "steps-exhausted";

  return {
    loop: goal.loop,
    goal: goal.goal,
    max_rounds: maxRounds,
    rounds,
    state_written: carried,
    stop,
    unmet,
    verdict,
  };
}

const USAGE = "usage: main.ts <loop-dir>";

function main(argv: readonly string[]): number {
  const target = argv[2];
  if (argv.length !== 3 || !target) {
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
  const report = runLoop(goal, state, files);
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return report.verdict === "goal-reached" ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
