// ablation-report exercise, TypeScript solution.
//
// Aggregates the six minimal-harness-loop reports (baseline + five single
// ablations) into one controlled-variable comparison: what changed, per
// removed subsystem, against the all-enabled baseline.

import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const SUBSYSTEMS = ["instructions", "state", "environment", "tools", "feedback"] as const;

interface LoopReport {
  readonly disabled: string | null;
  readonly outcome: string;
  readonly issues: readonly string[];
}

function loadReport(reportsDir: string, name: string): LoopReport {
  return JSON.parse(readFileSync(join(reportsDir, name), "utf8")) as LoopReport;
}

export function compare(baseline: LoopReport, ablated: LoopReport): Record<string, unknown> {
  return {
    disabled: ablated.disabled,
    outcome: ablated.outcome,
    outcome_changed: ablated.outcome !== baseline.outcome,
    issues: ablated.issues.length,
    signature: ablated.issues[0] ?? null,
  };
}

export function buildReport(reportsDir: string): Record<string, unknown> {
  const baseline = loadReport(reportsDir, "full.json");
  const ablations = SUBSYSTEMS.map((name) =>
    compare(baseline, loadReport(reportsDir, `disable-${name}.json`)),
  );
  return {
    baseline: { outcome: baseline.outcome, issues: baseline.issues.length },
    ablations,
    all_degraded: ablations.every((entry) => entry.outcome_changed === true),
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
