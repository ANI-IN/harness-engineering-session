// readiness-gate exercise, TypeScript solution.
//
// Turns a set of readiness check results into a tiered verdict and exit
// code: blockers stop a session from starting; advice does not, but must
// stay visible. Contract: ../../SPEC.md.

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const EXIT_READY = 0;
const EXIT_BLOCKED = 1;
const EXIT_ADVICE = 3;

interface Check {
  readonly id: string;
  readonly severity: "blocker" | "advice";
  readonly passed: boolean;
}

export function gate(checks: readonly Check[]): [Record<string, unknown>, number] {
  const blockersFailed = checks
    .filter((c) => c.severity === "blocker" && !c.passed)
    .map((c) => c.id);
  const adviceFailed = checks
    .filter((c) => c.severity === "advice" && !c.passed)
    .map((c) => c.id);
  let verdict: string;
  let code: number;
  if (blockersFailed.length > 0) {
    verdict = "blocked";
    code = EXIT_BLOCKED;
  } else if (adviceFailed.length > 0) {
    verdict = "ready-with-advice";
    code = EXIT_ADVICE;
  } else {
    verdict = "ready";
    code = EXIT_READY;
  }
  return [
    { blockers_failed: blockersFailed, advice_failed: adviceFailed, verdict },
    code,
  ];
}

function main(argv: readonly string[]): number {
  const path = argv[2];
  if (!path || argv.length !== 3) {
    console.error("usage: main.ts <check-results.json>");
    return 2;
  }
  let data: { checks: Check[] };
  try {
    data = JSON.parse(readFileSync(path, "utf8")) as { checks: Check[] };
  } catch (error) {
    console.error(`error: cannot read results: ${String(error)}`);
    return 2;
  }
  const [report, code] = gate(data.checks);
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return code;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
