// scope-auditor exercise, TypeScript starter.
//
// The report shape, the active-feature header, the drift bookkeeping, and
// the CLI all work. The in-scope rule does not: the naive draft treats a
// change to any *listed* feature as planned work, so drift into a queued
// feature passes as in scope. Fix audit() per SPEC.md. Run
// ../../verify.sh --stack=typescript until it exits 0.

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

interface Feature {
  id: string;
  status: string;
}

interface Change {
  step: number;
  file: string;
  feature: string;
}

export function audit(featureList: { features: Feature[] }, changes: Change[]): [object, number] {
  const features = featureList.features;
  const listed = new Set(features.map((feature) => feature.id));
  const active = features.filter((feature) => feature.status === "in-progress").map((f) => f.id);
  const results = [];
  const driftFeatures: string[] = [];
  for (const change of changes) {
    const featureId = change.feature;
    let inScope: boolean;
    let reason: string;
    // Naive draft: the feature list is the plan, so a change to any
    // listed feature is planned work and counts as in scope. That is the
    // overreach rationalization itself: the queue is scope for later
    // sessions, and only the active feature is scope for this one.
    // Exercise: in scope only when the feature is active; a queued
    // feature and an unknown feature are drift, each with its own reason
    // (SPEC.md, "The rule").
    if (listed.has(featureId)) {
      inScope = true;
      reason = "targets the active feature";
    } else {
      inScope = false;
      reason = `${featureId} is not in the feature list`;
    }
    if (!inScope && !driftFeatures.includes(featureId)) {
      driftFeatures.push(featureId);
    }
    results.push({
      step: change.step,
      file: change.file,
      feature: featureId,
      in_scope: inScope,
      reason,
    });
  }
  const driftCount = results.filter((result) => !result.in_scope).length;
  const report = {
    active,
    changes: results,
    drift: { count: driftCount, features: driftFeatures },
    clean: driftCount === 0,
  };
  return [report, driftCount === 0 ? 0 : 1];
}

function main(argv: readonly string[]): number {
  const featureListPath = argv[2];
  const changesPath = argv[3];
  if (!featureListPath || !changesPath || argv.length !== 4) {
    console.error("usage: main.ts <feature_list.json> <changes.json>");
    return 2;
  }
  let featureList: { features: Feature[] };
  let changes: Change[];
  try {
    featureList = JSON.parse(readFileSync(featureListPath, "utf8"));
    changes = JSON.parse(readFileSync(changesPath, "utf8")).changes;
  } catch (error) {
    console.error(`error: cannot read input: ${(error as Error).message}`);
    return 2;
  }
  const [report, code] = audit(featureList, changes);
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return code;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
