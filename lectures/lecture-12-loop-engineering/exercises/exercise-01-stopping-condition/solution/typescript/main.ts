// stopping-condition: where should this loop have stopped?
//
// A recorded loop trace holds, round by round, what the maker reported
// about its own step and what the checker independently reported about the
// whole goal. The loop that produced it had no stopping condition, so it
// ran to the end of the trace. This referee replays the trace and decides,
// at each round, whether a properly built loop stops there.
//
// Two rules end a loop, and they are read in this order: the clock cannot
// afford another round, or the stopping condition reads a pass. The signal
// the condition reads is the checker's verdict over every criterion,
// because the maker's report covers only the step the maker just took.

import { existsSync, readFileSync, statSync } from "node:fs";
import { pathToFileURL } from "node:url";

interface Round {
  round: number;
  maker: { criterion: string | null; reports_done: boolean };
  checker: { verdict: string; unmet: string[] };
}

interface Transcript {
  loop: string;
  budget_ticks: number;
  cost_per_round: number;
  rounds: Round[];
}

interface Stop {
  round: number;
  clock: number;
  decision: string;
  reason: string;
}

// The signal the stopping condition reads for one round. The checker grades
// every criterion of the goal and is not the party that did the work, so
// its verdict is the one that can end the loop.
function reachedTheGoal(record: Round): boolean {
  return record.checker.verdict === "pass";
}

export function referee(transcript: Transcript) {
  const budget = transcript.budget_ticks;
  const cost = transcript.cost_per_round;
  let clock = 0;
  const rows = [];
  let stop: Stop | null = null;
  let lastRan: Round | null = null;

  for (const record of transcript.rounds) {
    const number = record.round;
    if (stop !== null) {
      rows.push({ round: number, clock, decision: "not-run" });
      continue;
    }
    if (clock + cost > budget) {
      stop = {
        round: number,
        clock,
        decision: "stop-budget",
        reason:
          `round ${number} costs ${cost} ticks and the ${budget} tick ` +
          `budget has ${budget - clock} left`,
      };
      rows.push({ round: number, clock, decision: "stop-budget" });
      continue;
    }
    clock += cost;
    lastRan = record;
    const decision = reachedTheGoal(record) ? "stop-done" : "continue";
    rows.push({ round: number, clock, decision });
    if (decision === "stop-done") {
      stop = {
        round: number,
        clock,
        decision: "stop-done",
        reason: `the stopping condition read a pass at round ${number}`,
      };
    }
  }

  if (stop === null) {
    const last = transcript.rounds[transcript.rounds.length - 1];
    const number = last === undefined ? 0 : last.round;
    stop = {
      round: number,
      clock,
      decision: "trace-ended",
      reason: `the trace ends at round ${number} with the loop still running`,
    };
  }

  const unmet = lastRan === null ? [] : [...lastRan.checker.unmet];
  let verdict: string;
  if (stop.decision === "stop-budget") verdict = "budget-exhausted";
  else if (unmet.length === 0) verdict = "goal-reached";
  else verdict = "stopped-early";

  return {
    loop: transcript.loop,
    budget_ticks: budget,
    rounds: rows,
    stop,
    unmet_at_stop: unmet,
    verdict,
  };
}

function main(argv: readonly string[]): number {
  const target = argv[2];
  if (argv.length !== 3 || !target) {
    console.error("usage: main.ts <transcript-file>");
    return 2;
  }
  if (!existsSync(target) || !statSync(target).isFile()) {
    console.error(`error: no such transcript file: ${target}`);
    return 2;
  }
  const report = referee(JSON.parse(readFileSync(target, "utf8")) as Transcript);
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return report.verdict === "goal-reached" ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
