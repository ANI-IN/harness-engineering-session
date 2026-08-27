// scope-auditor exercise, TypeScript solution.
//
// Reads a feature list and a session's change log and classifies every
// change against the scope surface: in scope only when it targets the
// active (in-progress) feature; drift when it targets a queued feature or
// a feature the list does not know. The verdict lives in the exit code so
// a session-end gate can consume it. SPEC.md pins the rule and the strings.

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
  const activeSet = new Set(active);
  const results = [];
  const driftFeatures: string[] = [];
  for (const change of changes) {
    const featureId = change.feature;
    let inScope: boolean;
    let reason: string;
    if (activeSet.has(featureId)) {
      inScope = true;
      reason = "targets the active feature";
    } else if (listed.has(featureId)) {
      inScope = false;
      reason = `${featureId} is in the queue, not active`;
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
    console.error("usage: main.ts <feature-list.json> <changes.json>");
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
