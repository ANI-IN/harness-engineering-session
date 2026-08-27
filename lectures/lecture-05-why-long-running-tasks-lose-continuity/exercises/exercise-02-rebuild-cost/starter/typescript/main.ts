// rebuild-cost exercise, TypeScript starter.
//
// The report plumbing works; the savings orientation does not. The naive
// draft subtracts without-handoff from with-handoff for every metric, which
// flips the sign of every saving and makes the handoff look like a cost.
// Fix savings() per SPEC.md: positive must always mean the handoff mode
// did better. Run ../../verify.sh --stack=typescript until it exits 0.

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
  // Naive draft: one subtraction direction for every metric. Costs and
  // completions point opposite ways, so this flips the sign of every
  // saving. Exercise: orient each metric so positive always means the
  // handoff mode did better.
  return {
    reacquisition_lines: withTotals.reacquisition_lines - withoutTotals.reacquisition_lines,
    features_completed: withoutTotals.features_completed - withTotals.features_completed,
    rework_sessions: withTotals.rework_sessions - withoutTotals.rework_sessions,
    drift_events: withTotals.drift_events - withoutTotals.drift_events,
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
