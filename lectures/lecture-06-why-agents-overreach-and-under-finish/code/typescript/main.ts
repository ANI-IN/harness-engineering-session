// scope-run: a scripted worker meets a task boundary, or does not.
//
// The demo is behavioral. A deterministic worker replays the same session
// script (a fake agent's recorded stream of "the next thing I want to do":
// steps on the assigned feature interleaved with tangents it noticed along
// the way) against two workspaces that differ by one line, the WIP limit
// in AGENTS.md. Without the boundary the worker acts on every impulse:
// five features end the session in flight and the step budget runs out
// before the assigned feature's verification ever runs (exit 1). With the
// boundary the same tangent impulses are parked into a queue for zero
// steps, the assigned feature finishes verified with budget to spare
// (exit 0), and the parked queue records the scope the session refused to
// spend. Every rule and every step cost is pinned in SPEC.md.

import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const DEFAULT_BUDGET = 12;
const WIP_RULE = /^- WIP limit: (\d+)$/m;

interface Feature {
  id: string;
  status: string;
  verification: string;
}

interface Impulse {
  feature: string;
  kind: "step" | "verify";
  action: string | null;
  noticed: string | null;
}

interface Event {
  step: number;
  feature: string;
  action: string;
  outcome: string;
}

interface Parked {
  feature: string;
  action: string | null;
  noticed: string | null;
  noticed_at_step: number;
  times_provoked: number;
}

function isFile(path: string): boolean {
  return existsSync(path) && statSync(path).isFile();
}

// The feature list (scope surface) and the boundary, if AGENTS.md draws one.
function loadScopeSurface(workspace: string): { features: Feature[]; wipLimit: number | null } {
  const featureList = JSON.parse(readFileSync(join(workspace, "feature_list.json"), "utf8"));
  const rules = readFileSync(join(workspace, "AGENTS.md"), "utf8");
  const match = WIP_RULE.exec(rules);
  return {
    features: featureList.features as Feature[],
    wipLimit: match && match[1] ? Number.parseInt(match[1], 10) : null,
  };
}

function basename(path: string): string {
  return path.replace(/\/+$/, "").split("/").pop() ?? path;
}

// The scripted session (SPEC.md, "The run"). Behavior derives from the
// workspace files and the script; nothing else is consulted.
export function run(workspace: string, script: { impulses: Impulse[] }, budget: number) {
  const { features, wipLimit } = loadScopeSurface(workspace);
  const status = new Map(features.map((feature) => [feature.id, feature.status]));
  const verification = new Map(features.map((feature) => [feature.id, feature.verification]));
  const assigned = features.find((feature) => feature.status === "in-progress")?.id ?? "";
  const stepsOn = new Map(features.map((feature) => [feature.id, 0]));
  const events: Event[] = [];
  const parked: Parked[] = [];
  const parkedByFeature = new Map<string, Parked>();
  let stepsSpent = 0;

  const inFlight = (): number =>
    [...status.values()].filter((state) => state === "in-progress").length;

  for (const impulse of script.impulses) {
    if (stepsSpent >= budget) {
      break;
    }
    const target = impulse.feature;
    let newlyActivated = false;
    if (status.get(target) !== "in-progress") {
      if (wipLimit !== null && inFlight() >= wipLimit) {
        const entry = parkedByFeature.get(target);
        if (entry === undefined) {
          const fresh: Parked = {
            feature: target,
            action: impulse.action,
            noticed: impulse.noticed,
            noticed_at_step: stepsSpent,
            times_provoked: 1,
          };
          parkedByFeature.set(target, fresh);
          parked.push(fresh);
        } else {
          entry.times_provoked += 1;
        }
        continue;
      }
      status.set(target, "in-progress");
      newlyActivated = true;
    }

    stepsSpent += 1;
    stepsOn.set(target, (stepsOn.get(target) ?? 0) + 1);
    let action: string;
    let outcome: string;
    if (impulse.kind === "verify") {
      status.set(target, "passing");
      action = `run the verification command (${verification.get(target) ?? ""})`;
      outcome = `pass: ${target} moves to passing with evidence`;
    } else if (target === assigned) {
      action = impulse.action ?? "";
      outcome = `progress on the assigned feature (step ${stepsOn.get(target) ?? 0})`;
    } else {
      action = impulse.action ?? "";
      outcome = newlyActivated
        ? `scope crossed: ${inFlight()} features in flight`
        : "the tangent deepens; the assigned feature waits";
    }
    events.push({ step: stepsSpent, feature: target, action, outcome });
  }

  const stepsOnAssigned = stepsOn.get(assigned) ?? 0;
  return {
    workspace: basename(workspace),
    wip_limit: wipLimit,
    assigned,
    budget,
    events,
    parked,
    steps_spent: stepsSpent,
    steps_on_assigned: stepsOnAssigned,
    steps_on_tangents: stepsSpent - stepsOnAssigned,
    features_started: features.filter((feature) => (stepsOn.get(feature.id) ?? 0) > 0).length,
    features_passing: features.filter((feature) => status.get(feature.id) === "passing").length,
    in_progress_at_end: features
      .filter((feature) => status.get(feature.id) === "in-progress")
      .map((feature) => feature.id),
    assigned_verified: status.get(assigned) === "passing",
  };
}

const USAGE = "usage: main.ts <workspace-dir> <session-script.json> [--budget N]";

function parseArgs(argv: readonly string[]): { workspace: string; script: string; budget: number } | null {
  const positional: string[] = [];
  let budget = DEFAULT_BUDGET;
  let index = 2;
  while (index < argv.length) {
    const arg = argv[index] ?? "";
    if (arg === "--budget") {
      const value = argv[index + 1];
      if (value === undefined || !/^\d+$/.test(value)) {
        return null;
      }
      budget = Number.parseInt(value, 10);
      index += 2;
      continue;
    }
    if (arg.startsWith("-")) {
      return null;
    }
    positional.push(arg);
    index += 1;
  }
  if (positional.length !== 2 || budget < 1) {
    return null;
  }
  return { workspace: positional[0] as string, script: positional[1] as string, budget };
}

function main(argv: readonly string[]): number {
  const parsed = parseArgs(argv);
  if (parsed === null) {
    console.error(USAGE);
    return 2;
  }
  const { workspace, script: scriptPath, budget } = parsed;
  if (!existsSync(workspace) || !statSync(workspace).isDirectory()) {
    console.error(`error: not a directory: ${workspace}`);
    return 2;
  }
  for (const required of ["feature_list.json", "AGENTS.md"]) {
    if (!isFile(join(workspace, required))) {
      console.error(`error: workspace lacks ${required}: ${workspace}`);
      return 2;
    }
  }
  if (!isFile(scriptPath)) {
    console.error(`error: not a file: ${scriptPath}`);
    return 2;
  }
  const script = JSON.parse(readFileSync(scriptPath, "utf8")) as { impulses: Impulse[] };
  const { features } = loadScopeSurface(workspace);
  const active = features.filter((feature) => feature.status === "in-progress");
  if (active.length !== 1) {
    console.error(`error: expected exactly one in-progress feature, found ${active.length}`);
    return 2;
  }
  const report = run(workspace, script, budget);
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return report.assigned_verified ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
