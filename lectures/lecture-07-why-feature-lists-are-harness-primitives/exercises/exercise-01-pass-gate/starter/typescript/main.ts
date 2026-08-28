// pass-gate exercise, TypeScript starter.
//
// The state machine works: legal edges, WIP=1 on entry to in-progress,
// passing is final. The road into passing does not: the naive draft lets any
// recorded evidence through, without asking what was run or what it showed,
// so an agent that ran `echo done` gets the same verdict as one that ran the
// feature's verification command. Fix the passing branch of decide() per
// SPEC.md. Run ../../verify.sh --stack=typescript until it exits 0.

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const EXIT_ALLOWED = 0;
const EXIT_REFUSED = 1;
const EXIT_USAGE = 2;

interface Feature {
  id: string;
  status: string;
  verification: string;
}

interface Evidence {
  command: string;
  observed: string;
  date: string;
}

interface Request {
  feature: string;
  to: string;
  evidence?: Evidence;
}

interface Verdict {
  feature: string;
  from: string;
  to: string;
  decision: string;
  reason: string;
}

export function decide(features: Feature[], request: Request): [Verdict, number] {
  const feature = features.find((candidate) => candidate.id === request.feature)!;
  const featureId = feature.id;
  const current = feature.status;
  const target = request.to;

  const verdict = (decision: string, reason: string): [Verdict, number] => [
    { feature: featureId, from: current, to: target, decision, reason },
    decision === "allowed" ? EXIT_ALLOWED : EXIT_REFUSED,
  ];

  if (current === "passing") {
    return verdict("refused", `passing is final: ${featureId} cannot leave passing`);
  }
  if (target === "in-progress" && (current === "not-started" || current === "blocked")) {
    const active = features
      .filter((candidate) => candidate.status === "in-progress" && candidate.id !== featureId)
      .map((candidate) => candidate.id);
    if (active.length > 0) {
      return verdict("refused", `WIP limit: ${active[0]} is already in-progress`);
    }
    return verdict("allowed", "WIP=1 holds: no other feature in-progress");
  }
  if (target === "blocked" && current === "in-progress") {
    return verdict("allowed", "blocked is reachable from in-progress");
  }
  if (target === "passing" && current === "in-progress") {
    const evidence = request.evidence;
    if (!evidence) {
      return verdict("refused", "no evidence recorded; passing requires evidence");
    }
    // Naive draft: evidence is present, so the claim goes through. The gate
    // never asks whether the evidence's command is this feature's
    // verification command, or whether the observed result was a pass.
    return verdict("allowed", "evidence recorded");
  }
  return verdict("refused", `illegal transition: ${current} -> ${target}`);
}

function main(argv: readonly string[]): number {
  const listPath = argv[2];
  const requestPath = argv[3];
  if (argv.length !== 4 || !listPath || !requestPath) {
    console.error("usage: main.ts <feature_list.json> <request.json>");
    return EXIT_USAGE;
  }
  let features: Feature[];
  let request: Request;
  try {
    features = (JSON.parse(readFileSync(listPath, "utf8")) as { features: Feature[] }).features;
    request = JSON.parse(readFileSync(requestPath, "utf8")) as Request;
  } catch (error) {
    console.error(`error: cannot read input: ${String(error)}`);
    return EXIT_USAGE;
  }
  if (!features.some((feature) => feature.id === request.feature)) {
    console.error(`error: unknown feature '${request.feature}'`);
    return EXIT_USAGE;
  }
  const [report, code] = decide(features, request);
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return code;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
