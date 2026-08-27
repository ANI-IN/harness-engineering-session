// completion-gate exercise, TypeScript starter.
//
// The claim audit, the WIP check, the verdict precedence, and the CLI all
// work. The evidence rule does not: the naive draft accepts any recorded
// evidence entry as proof, so a typecheck filed as evidence, or a recorded
// failing run, backs a `passing` claim. Fix gate() per SPEC.md. Run
// ../../verify.sh --stack=typescript until it exits 0.

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const WIP_LIMIT = 1;

interface Evidence {
  command: string;
  observed: string;
  date: string;
}

interface Feature {
  id: string;
  status: string;
  verification: string;
  evidence?: Evidence;
}

export function gate(features: Feature[]): [object, number] {
  const claims = [];
  const unbacked: string[] = [];
  for (const feature of features) {
    if (feature.status !== "passing") {
      continue;
    }
    const evidence = feature.evidence ?? null;
    const command = feature.verification;
    let ok: boolean;
    let detail: string;
    // Naive draft: an evidence entry was recorded, so the claim is
    // backed, and the detail names the command the feature should have
    // run. Exercise: evidence must name this feature's own verification
    // command AND record a passing run (observed starts with "exit 0");
    // a different command and a failing run are each an unbacked claim
    // with its own detail (SPEC.md, "The evidence rule").
    if (evidence === null) {
      ok = false;
      detail = "no evidence recorded";
    } else {
      ok = true;
      detail = `verified: ${command} reported exit 0`;
    }
    claims.push({ id: feature.id, evidence_ok: ok, detail });
    if (!ok) {
      unbacked.push(feature.id);
    }
  }
  const inProgress = features.filter((f) => f.status === "in-progress").map((f) => f.id);
  let verdict: string;
  let code: number;
  if (inProgress.length > WIP_LIMIT) {
    verdict = "wip-exceeded";
    code = 1;
  } else if (unbacked.length > 0) {
    verdict = "unbacked-claims";
    code = 1;
  } else {
    verdict = "sound";
    code = 0;
  }
  const report = {
    claims,
    may_activate: verdict === "sound" && inProgress.length === 0,
    unbacked,
    verdict,
    wip: { in_progress: inProgress, limit: WIP_LIMIT },
  };
  return [report, code];
}

function main(argv: readonly string[]): number {
  const path = argv[2];
  if (!path || argv.length !== 3) {
    console.error("usage: main.ts <feature-list.json>");
    return 2;
  }
  let data: { features: Feature[] };
  try {
    data = JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    console.error(`error: cannot read feature list: ${(error as Error).message}`);
    return 2;
  }
  const [report, code] = gate(data.features);
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return code;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
