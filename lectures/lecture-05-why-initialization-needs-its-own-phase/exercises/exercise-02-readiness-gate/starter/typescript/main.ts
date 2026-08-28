// readiness-gate exercise, TypeScript starter.
//
// The counting works; the tiering does not. The naive draft treats every
// failed check as a blocker, so advice-only failures block the session
// and exit 1 where the SPEC requires ready-with-advice and exit 3. Fix
// gate() per SPEC.md. Run ../../verify.sh --stack=typescript until it
// exits 0.

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const EXIT_READY = 0;
const EXIT_BLOCKED = 1;
export const EXIT_ADVICE = 3;

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
  // Naive draft: severity exists so that advice does not block; treating
  // every failure as a blocker erases the tier. Exercise: blockers give
  // "blocked"/exit 1; advice-only gives "ready-with-advice"/exit 3;
  // otherwise "ready"/exit 0.
  if (blockersFailed.length > 0 || adviceFailed.length > 0) {
    verdict = "blocked";
    code = EXIT_BLOCKED;
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
