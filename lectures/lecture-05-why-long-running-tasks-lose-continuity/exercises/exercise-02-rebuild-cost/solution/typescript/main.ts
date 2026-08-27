// rebuild-cost exercise, TypeScript solution.
//
// Compares the simulator's two committed runs and computes what the handoff
// artifacts buy: savings are oriented so a positive number always means the
// handoff mode did better. Contract: ../../SPEC.md.

import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

interface Totals {
  readonly reacquisition_lines: number;
  readonly features_completed: number;
  readonly rework_sessions: number;
  readonly drift_events: number;
}

export function savings(withTotals: Totals, withoutTotals: Totals): Totals {
  // Costs (reacquisition, rework, drift) save when WITHOUT exceeds WITH;
  // completions save when WITH exceeds WITHOUT. Orienting each metric keeps
  // "positive = handoff wins" true for all of them.
  return {
    reacquisition_lines: withoutTotals.reacquisition_lines - withTotals.reacquisition_lines,
    features_completed: withTotals.features_completed - withoutTotals.features_completed,
    rework_sessions: withoutTotals.rework_sessions - withTotals.rework_sessions,
    drift_events: withoutTotals.drift_events - withTotals.drift_events,
  };
}

export function buildReport(reportsDir: string): Record<string, unknown> {
  const withReport = JSON.parse(
    readFileSync(join(reportsDir, "with-handoff.json"), "utf8"),
  ) as { totals: Totals };
  const withoutReport = JSON.parse(
    readFileSync(join(reportsDir, "no-handoff.json"), "utf8"),
  ) as { totals: Totals };
  return {
    with_handoff: withReport.totals,
    without_handoff: withoutReport.totals,
    savings: savings(withReport.totals, withoutReport.totals),
  };
}

function main(argv: readonly string[]): number {
  const reportsDir = argv[2];
  if (!reportsDir || argv.length !== 3) {
    console.error("usage: main.ts <reports-dir>");
    return 2;
  }
  if (!existsSync(reportsDir) || !statSync(reportsDir).isDirectory()) {
    console.error(`error: not a directory: ${reportsDir}`);
    return 2;
  }
  process.stdout.write(JSON.stringify(buildReport(reportsDir), null, 2) + "\n");
  return 0;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
