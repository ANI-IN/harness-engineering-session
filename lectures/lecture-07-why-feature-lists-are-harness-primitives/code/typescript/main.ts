// scope-replay: the same scripted session under two tracking regimes.
//
// `replay` is the demo: a deterministic scripted session finishes "the rest
// of the project" in a workspace, taking its beliefs from whichever tracking
// artifact the workspace carries (a prose notes.md or a canonical
// feature_list.json). The session never sees project.json, the recorded
// ground truth the deterministic fake agent replays; the closing audit does,
// and grades the session's "done" claim by running every scope feature's
// real verification outcome. On the memo workspace the claim is false (exit
// 1); on the tracked workspace the same session ends verified (exit 0).
// `plan` is the supporting surface: it prints only what a fresh session can
// ground in the tracker, with no ground truth at all. SPEC.md pins the memo
// reading rule, the step scripts, and the audit templates.

import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const MEMO_LINE = /^- ([a-z][a-z0-9]*(?:-[a-z0-9]+)*): (.+)$/;
const REMAINING_WORDS = ["need", "todo"];

interface TruthEntry {
  id: string;
  built: boolean;
  hidden_defect: boolean;
}

interface ListEntry {
  id: string;
  status: string;
  verification: string;
}

interface Event {
  step: number;
  action: string;
  outcome: string;
}

function fileExists(workspace: string, name: string): boolean {
  const path = join(workspace, name);
  return existsSync(path) && statSync(path).isFile();
}

function parseMemo(text: string): Array<[string, string]> {
  const mentions: Array<[string, string]> = [];
  for (const line of text.split(/\r?\n/)) {
    const match = line.match(MEMO_LINE);
    if (match && match[1] && match[2]) {
      mentions.push([match[1], match[2].trim()]);
    }
  }
  return mentions;
}

function readsAsRemaining(prose: string): boolean {
  const lowered = prose.toLowerCase();
  return REMAINING_WORDS.some((word) => lowered.includes(word));
}

function findTracker(workspace: string): string | null {
  if (fileExists(workspace, "feature_list.json")) return "feature_list.json";
  if (fileExists(workspace, "notes.md")) return "notes.md";
  return null;
}

function basename(workspace: string): string {
  return workspace.replace(/\/+$/, "").split("/").pop() ?? workspace;
}

function replay(workspace: string, tracker: string): [Record<string, unknown>, number] {
  const project = JSON.parse(readFileSync(join(workspace, "project.json"), "utf8")) as {
    project: string;
    features: TruthEntry[];
  };
  const truth = new Map(project.features.map((feature) => [feature.id, { ...feature }]));
  const events: Event[] = [];
  let step = 0;
  let wasted = 0;
  const believed = new Map<string, string>();
  const reworked = new Set<string>();

  const spend = (action: string, outcome: string): void => {
    step += 1;
    events.push({ step, action, outcome });
  };

  if (tracker === "notes.md") {
    const mentions = parseMemo(readFileSync(join(workspace, "notes.md"), "utf8"));
    spend(
      "read notes.md",
      `${mentions.length} features mentioned; states are prose; no verification commands recorded`,
    );
    const planned: string[] = [];
    for (const [featureId, prose] of mentions) {
      if (readsAsRemaining(prose)) {
        spend(`interpret '${featureId}'`, `'${prose}' reads as remaining; planned`);
        planned.push(featureId);
      } else {
        spend(`interpret '${featureId}'`, `'${prose}' reads as done; skipped`);
      }
      believed.set(featureId, "done");
    }
    for (const featureId of planned) {
      const state = truth.get(featureId)!;
      const alreadyPassing = state.built && !state.hidden_defect;
      spend(
        `implement ${featureId}`,
        state.built
          ? "code written; the workspace already had this feature built"
          : "code written",
      );
      state.built = true;
      spend(
        `self-check ${featureId}`,
        "looks complete; the memo records no verification command to run",
      );
      spend("update notes.md", `${featureId} marked done in prose`);
      if (alreadyPassing) {
        reworked.add(featureId);
        wasted += 3;
      }
    }
    spend("declare done", "the memo shows nothing remaining");
  } else {
    const entries = (
      JSON.parse(readFileSync(join(workspace, "feature_list.json"), "utf8")) as {
        features: ListEntry[];
      }
    ).features;
    spend(
      "read feature_list.json",
      `${entries.length} features; every entry carries an explicit status and a verification command`,
    );
    for (const entry of entries) {
      const state = truth.get(entry.id)!;
      if (entry.status === "passing") {
        spend(
          `${entry.id}: status passing`,
          `evidence recorded (${entry.verification}); skipped without rework`,
        );
      } else {
        spend(
          `implement ${entry.id}`,
          entry.status === "not-started" ? "code written" : "remaining work written",
        );
        state.built = true;
        if (state.hidden_defect) {
          spend(`run ${entry.verification}`, "exit 1: a hidden defect surfaces inside the session");
          spend(`fix ${entry.id}`, "defect repaired");
          state.hidden_defect = false;
        }
        spend(`run ${entry.verification}`, "exit 0; status passing with evidence recorded");
      }
      believed.set(entry.id, "passing");
    }
    spend("declare done", "every feature passing; the claim carries evidence");
  }

  const audit: Array<Record<string, unknown>> = [];
  let verifiedCount = 0;
  for (const feature of project.features) {
    const state = truth.get(feature.id)!;
    const verified = state.built && !state.hidden_defect;
    let note: string;
    if (verified) {
      verifiedCount += 1;
      note = reworked.has(feature.id)
        ? "verification passes; the session rebuilt a feature that already passed"
        : "verification passes";
    } else if (state.built) {
      note = "verification fails: the code carries a defect no session run exposed";
    } else {
      note = "never attempted: absent from the tracker";
    }
    audit.push({
      id: feature.id,
      believed: believed.get(feature.id) ?? "untracked",
      verified,
      note,
    });
  }

  const honest = verifiedCount === project.features.length;
  const report = {
    workspace: basename(workspace),
    tracker,
    events,
    steps_spent: step,
    wasted_steps: wasted,
    claimed_done: true,
    features_required: project.features.length,
    features_verified: verifiedCount,
    audit,
    done_claim_honest: honest,
  };
  return [report, honest ? 0 : 1];
}

function plan(workspace: string, tracker: string): [Record<string, unknown>, number] {
  const entriesOut: Array<Record<string, unknown>> = [];
  const nextIds: string[] = [];
  if (tracker === "notes.md") {
    for (const [featureId, prose] of parseMemo(
      readFileSync(join(workspace, "notes.md"), "utf8"),
    )) {
      const remaining = readsAsRemaining(prose);
      entriesOut.push({
        id: featureId,
        state: remaining
          ? "remaining (interpreted from prose)"
          : "done (interpreted from prose)",
        verification: "none recorded",
        grounded: false,
      });
      if (remaining) nextIds.push(featureId);
    }
  } else {
    const entries = (
      JSON.parse(readFileSync(join(workspace, "feature_list.json"), "utf8")) as {
        features: ListEntry[];
      }
    ).features;
    for (const entry of entries) {
      entriesOut.push({
        id: entry.id,
        state: entry.status,
        verification: entry.verification,
        grounded: true,
      });
      if (entry.status !== "passing") nextIds.push(entry.id);
    }
  }
  const grounded =
    entriesOut.length > 0 && entriesOut.every((entry) => entry.grounded === true);
  const report = {
    workspace: basename(workspace),
    tracker,
    entries: entriesOut,
    next: nextIds,
    grounded,
  };
  return [report, grounded ? 0 : 1];
}

function main(argv: readonly string[]): number {
  const mode = argv[2];
  const workspace = argv[3];
  if (argv.length !== 4 || !workspace || (mode !== "replay" && mode !== "plan")) {
    console.error("usage: main.ts replay <workspace-dir> | main.ts plan <workspace-dir>");
    return 2;
  }
  if (!existsSync(workspace) || !statSync(workspace).isDirectory()) {
    console.error(`error: not a directory: ${workspace}`);
    return 2;
  }
  const tracker = findTracker(workspace);
  if (tracker === null) {
    console.error(`error: no tracker (feature_list.json or notes.md) in ${workspace}`);
    return 2;
  }
  let report: Record<string, unknown>;
  let code: number;
  if (mode === "replay") {
    if (!fileExists(workspace, "project.json")) {
      console.error(`error: project.json (recorded ground truth) missing in ${workspace}`);
      return 2;
    }
    [report, code] = replay(workspace, tracker);
  } else {
    [report, code] = plan(workspace, tracker);
  }
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return code;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
