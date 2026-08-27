// ablation-report exercise, TypeScript starter.
//
// The aggregation plumbing works; the comparison logic does not. Your task:
// in compare(), fill in outcome_changed and signature per SPEC.md. Run
// ../../verify.sh --stack=typescript until it exits 0.

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

export function compare(_baseline: LoopReport, ablated: LoopReport): Record<string, unknown> {
  // Exercise: outcome_changed is whether the ablated outcome differs from
  // the baseline outcome; signature is the ablated run's first issue
  // string, or null when it has none.
  return {
    disabled: ablated.disabled,
    outcome: ablated.outcome,
    outcome_changed: false,
    issues: ablated.issues.length,
    signature: null,
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
