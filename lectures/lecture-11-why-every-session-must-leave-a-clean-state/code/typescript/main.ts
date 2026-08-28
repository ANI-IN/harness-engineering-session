// session-ending: two sessions in sequence over one workspace, where the
// only thing that varies is how the first session ended.
//
// `resume` runs the first session (the same work steps under both exit
// disciplines), applies the chosen ending (`--exit=dirty` walks away,
// `--exit=clean` runs the exit protocol), then runs the second session
// against whatever it was left. The second session's protocol is identical
// in both runs, so every difference in its behaviour is caused by the
// ending it inherited: from the clean workspace it picks up the open
// feature and finishes it, from the dirty one it redoes finished work and
// turns a check that was green red. The exit code is the second session's
// outcome.
//
// `first` stops after the first session and grades its ending against five
// mechanically checkable items of the clean state checklist. That count is
// supporting evidence for the behavioural runs, never the demonstration.
//
// The workspace is read from disk once and edited in memory, so the
// committed fixture never changes and every run is idempotent. SPEC.md
// pins the check engine, both session scripts, the exit protocol, and the
// checklist items.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { basename, join } from "node:path";
import { pathToFileURL } from "node:url";

const BUILD_DATE = "2026-08-27";

// The implementation edit each feature needs: the file that carries the
// feature's behaviour, the header written when that file does not exist
// yet, and the declaration line the work adds.
const IMPLEMENTATION: Record<string, [string, string, string]> = {
  "csv-export": ["src/export.txt", "module=export", "writer=csv"],
  "pdf-export": ["src/pdf.txt", "module=pdf", "writer=pdf"],
};

const PROGRESS_PLACEHOLDER = "No feature has been verified in this workspace yet.";
const SESSION_HEADING = "## Session 001";

const SESSION_ENTRY = `## Session 002 (2026-08-27)

- Goal: finish csv-export, then open pdf-export.
- Done: csv-export, verified by check unit-csv.
- Not done: pdf-export; the draft module was rolled back, so the workspace
  holds no half applied change.
- Next: pdf-export.

`;

const HANDOFF = `# Session handoff

## Verified now

- \`check unit-csv\`: exit 0, src/export.txt declares writer once
- \`check wiring-csv\`: exit 0, config/app.conf sets export_dir

## Changed this session

- \`src/export.txt\`: the csv writer is implemented.
- \`config/app.conf\`: export_dir set to out/reports.
- \`feature_list.json\`: csv-export set to passing with evidence.

## Broken or unverified

Nothing. The pdf draft was rolled back, so pdf-export is not-started
rather than half applied.

## Next best step

- pdf-export: add a \`writer=pdf\` line to \`src/pdf.txt\`, then run
  \`check unit-pdf\`.

## Commands

- Verify everything: \`check unit-csv && check wiring-csv && check unit-pdf\`
`;

interface Check {
  id: string;
  feature: string;
  kind: string;
  path: string;
  key?: string;
  prefix?: string;
}

interface Config {
  task: string;
  checks: Check[];
}

interface Evidence {
  command: string;
  observed: string;
  date: string;
}

interface Feature {
  id: string;
  title: string;
  behavior: string;
  verification: string;
  status: string;
  evidence?: Evidence;
}

interface FeatureList {
  project: string;
  updated: string;
  features: Feature[];
}

interface CheckResult {
  id: string;
  feature: string;
  status: string;
  detail: string;
}

interface Event {
  step: number;
  action: string;
  outcome: string;
}

interface Item {
  item: string;
  status: string;
  detail: string;
}

type Files = Map<string, string>;

// --------------------------------------------------------------------------
// The workspace: a path-to-text map loaded once and edited in memory.
// --------------------------------------------------------------------------

function loadWorkspace(root: string): Files {
  const files: Files = new Map();
  const walk = (dir: string, prefix: string): void => {
    for (const name of readdirSync(dir).sort()) {
      const full = join(dir, name);
      const relative = prefix ? `${prefix}/${name}` : name;
      if (statSync(full).isDirectory()) walk(full, relative);
      else files.set(relative, readFileSync(full, "utf8"));
    }
  };
  walk(root, "");
  return files;
}

function linesOf(files: Files, path: string): string[] {
  return (files.get(path) as string).split(/\r?\n/);
}

function featureList(files: Files): FeatureList {
  return JSON.parse(files.get("feature_list.json") as string) as FeatureList;
}

function storeFeatureList(files: Files, data: FeatureList): void {
  files.set("feature_list.json", JSON.stringify(data, null, 2) + "\n");
}

function setStatus(files: Files, featureId: string, status: string, evidence?: Evidence): void {
  const data = featureList(files);
  for (const feature of data.features) {
    if (feature.id === featureId) {
      feature.status = status;
      if (evidence !== undefined) feature.evidence = evidence;
    }
  }
  storeFeatureList(files, data);
}

function beforeEquals(value: string): string {
  return value.split("=")[0] ?? value;
}

function beforeColon(value: string): string {
  return (value.split(":")[0] ?? value).trim();
}

// The ids named by `- <id>: <text>` bullets under one markdown heading. One
// parser serves all three artifact sections this unit reads: the progress
// log's verified features, and the handoff's broken checks and its next
// best step.
function sectionIds(files: Files, path: string, heading: string): string[] {
  const text = files.get(path);
  if (text === undefined) return [];
  const found: string[] = [];
  let inside = false;
  for (const line of text.split(/\r?\n/)) {
    if (line.startsWith("## ")) {
      inside = line.trim() === heading;
      continue;
    }
    if (inside && line.startsWith("- ") && line.includes(":")) {
      found.push(beforeColon(line.slice(2)));
    }
  }
  return found;
}

// --------------------------------------------------------------------------
// The check engine: the deterministic stand-in for running the real command.
// --------------------------------------------------------------------------

function runCheck(files: Files, check: Check): [boolean, string] {
  const path = check.path;
  if (!files.has(path)) return [false, `${path} missing`];
  const lines = linesOf(files, path);
  if (check.kind === "key-declared-once") {
    const key = check.key as string;
    const count = lines.filter((line) => line.startsWith(`${key}=`)).length;
    if (count === 1) return [true, `${path} declares ${key} once`];
    if (count === 0) return [false, `${path} has no ${key}= line`];
    return [false, `${path} declares ${key} ${count} times`];
  }
  if (check.kind === "file-has-line") {
    const prefix = check.prefix as string;
    if (lines.some((line) => line.startsWith(prefix))) {
      return [true, `${path} has a line starting with ${prefix}`];
    }
    return [false, `${path} has no line starting with ${prefix}`];
  }
  throw new Error(`unknown check kind: ${check.kind}`);
}

function runChecks(files: Files, config: Config): CheckResult[] {
  return config.checks.map((check) => {
    const [passed, detail] = runCheck(files, check);
    return { id: check.id, feature: check.feature, status: passed ? "pass" : "fail", detail };
  });
}

function summarize(results: CheckResult[]): string {
  return results.map((result) => `${result.id} ${result.status}`).join(", ");
}

// Feature ids whose every declared check passes right now.
function greenFeatures(results: CheckResult[]): string[] {
  const byFeature = new Map<string, string[]>();
  for (const result of results) {
    const seen = byFeature.get(result.feature) ?? [];
    seen.push(result.status);
    byFeature.set(result.feature, seen);
  }
  return [...byFeature.entries()]
    .filter(([, seen]) => seen.every((status) => status === "pass"))
    .map(([fid]) => fid)
    .sort();
}

// Apply a feature's implementation edit and report what the file now
// declares. A session that believes a feature is unstarted writes the
// declaration; whether one is already there is not something the edit
// consults.
function implement(files: Files, featureId: string): string {
  const [path, header, line] = IMPLEMENTATION[featureId] as [string, string, string];
  const created = !files.has(path);
  if (created) files.set(path, header + "\n");
  files.set(path, (files.get(path) as string) + line + "\n");
  const key = beforeEquals(line);
  const count = linesOf(files, path).filter((text) => text.startsWith(`${key}=`)).length;
  const times = count === 1 ? "once" : `${count} times`;
  const verb = created ? `created ${path} with ${line}` : `appended ${line} to ${path}`;
  return `${verb}; the file now declares ${key} ${times}`;
}

// Numbered actions with their observed outcomes: one session's log.
class Transcript {
  readonly events: Event[] = [];

  record(action: string, outcome: string): void {
    this.events.push({ step: this.events.length + 1, action, outcome });
  }
}

// --------------------------------------------------------------------------
// The first session: the same work, then one of two endings.
// --------------------------------------------------------------------------

function firstSession(files: Files, config: Config, discipline: string): Event[] {
  const log = new Transcript();

  log.record("implement the csv writer", implement(files, "csv-export"));

  files.set("config/app.conf", (files.get("config/app.conf") as string) + "export_dir=out/reports\n");
  log.record("wire the export directory", "config/app.conf now sets export_dir=out/reports");

  const byId = new Map(config.checks.map((check) => [check.id, check]));
  const [, detail] = runCheck(files, byId.get("unit-csv") as Check);
  log.record("run check unit-csv", `executed: pass (${detail})`);

  setStatus(files, "pdf-export", "in-progress");
  files.set("src/pdf.txt", "module=pdf\nstage=draft\n");
  log.record(
    "open pdf-export and draft its module",
    "feature_list.json sets pdf-export to in-progress; src/pdf.txt drafted " +
      "with no writer= line yet",
  );

  files.set("scratch/probe-pdf.txt", "page_size=a4\nprobe=manual\n");
  log.record("probe the pdf page size by hand", "scratch/probe-pdf.txt written");

  if (discipline === "dirty") {
    log.record(
      "end the session",
      "no exit protocol ran: feature_list.json still calls csv-export " +
        "in-progress, claude-progress.md has no entry for this session, " +
        "src/pdf.txt is left half applied, scratch/probe-pdf.txt is left in " +
        "the tree, and no session-handoff.md was written",
    );
  } else {
    cleanExit(files, config, log);
  }
  return log.events;
}

// The exit protocol: verify, roll back what is half applied, write the
// verified state into the machine-readable artifacts, clear the debris, and
// name the next best step.
function cleanExit(files: Files, config: Config, log: Transcript): void {
  const results = runChecks(files, config);
  log.record(
    "run the declared checks and record what they observed",
    `${summarize(results)} (${(results[2] as CheckResult).detail})`,
  );

  files.delete("src/pdf.txt");
  setStatus(files, "pdf-export", "not-started");
  log.record(
    "roll back the half applied pdf draft",
    "src/pdf.txt removed; feature_list.json returns pdf-export to " +
      "not-started, so no check is left failing on a feature in flight",
  );

  setStatus(files, "csv-export", "passing", {
    command: "check unit-csv",
    observed: "exit 0, src/export.txt declares writer once",
    date: BUILD_DATE,
  });
  const data = featureList(files);
  data.updated = BUILD_DATE;
  storeFeatureList(files, data);
  log.record(
    "write the verified status into feature_list.json",
    `csv-export set to passing with evidence: check unit-csv, exit 0, ${BUILD_DATE}`,
  );

  const verified = greenFeatures(runChecks(files, config));
  const byFeature = new Map(featureList(files).features.map((feature) => [feature.id, feature]));
  const bullets = verified
    .map((fid) => `- ${fid}: verified by ${(byFeature.get(fid) as Feature).verification}`)
    .join("\n");
  const progress = (files.get("claude-progress.md") as string).replace(
    PROGRESS_PLACEHOLDER,
    bullets,
  );
  files.set("claude-progress.md", progress.replace(SESSION_HEADING, SESSION_ENTRY + SESSION_HEADING));
  log.record(
    "record the session in claude-progress.md",
    `verified now lists ${verified.join(", ")}; a session 002 entry names ` +
      "what was done, what was not, and what is next",
  );

  files.delete("scratch/probe-pdf.txt");
  files.set("session-handoff.md", HANDOFF);
  log.record(
    "clear the scratch artifacts and write session-handoff.md",
    "scratch/probe-pdf.txt removed; session-handoff.md names pdf-export as " +
      "the next best step",
  );
}

// --------------------------------------------------------------------------
// The second session: one protocol, run against whichever ending it got.
// --------------------------------------------------------------------------

function secondSession(files: Files, config: Config): [Transcript, string, CheckResult[]] {
  const log = new Transcript();

  const nextSteps = sectionIds(files, "session-handoff.md", "## Next best step");
  const handoffStep = nextSteps[0] ?? null;
  log.record(
    "read session-handoff.md",
    handoffStep !== null
      ? `found; the next best step names ${handoffStep}`
      : "absent; the previous session wrote down no next best step",
  );

  const verified = sectionIds(files, "claude-progress.md", "## Verified now");
  log.record(
    "read the verified state in claude-progress.md",
    verified.length > 0
      ? `verified now lists ${verified.join(", ")}`
      : "verified now lists nothing; the log carries no entry for the " +
          "previous session, so its work is invisible from here",
  );

  const features = featureList(files).features;
  const inProgress = features
    .filter((feature) => feature.status === "in-progress")
    .map((feature) => feature.id);
  const statuses = features.map((feature) => `${feature.id} ${feature.status}`).join(", ");
  log.record(
    "read feature_list.json",
    statuses +
      (inProgress.length > 1
        ? `; ${inProgress.length} features in flight at once, which breaks WIP=1`
        : ""),
  );

  // Choose the feature. The handoff wins when it names one; otherwise WIP=1
  // points at the single in-progress feature, and a feature the progress log
  // records as verified is skipped.
  const candidates = inProgress.filter((fid) => !verified.includes(fid));
  let chosen: string;
  let why: string;
  if (handoffStep !== null) {
    chosen = handoffStep;
    why = "named by session-handoff.md";
  } else if (candidates.length > 0) {
    chosen = candidates[0] as string;
    why =
      inProgress.length > 1
        ? "no handoff, and no progress entry that would let it be skipped; " +
          `feature_list.json leaves ${inProgress.length} features in progress, ` +
          "so take the first"
        : "the single in-progress feature, per WIP=1";
  } else {
    chosen = (features[0] as Feature).id;
    why = "nothing in progress and nothing handed over; take the first feature declared";
  }
  log.record("choose the feature to work on", `${chosen}: ${why}`);

  log.record(`implement ${chosen}`, implement(files, chosen));

  const results = runChecks(files, config);
  log.record("run the declared checks", summarize(results));
  return [log, chosen, results];
}

// --------------------------------------------------------------------------
// The clean state checklist: supporting evidence, five mechanical items.
// --------------------------------------------------------------------------

function cleanState(files: Files, config: Config): Item[] {
  const features = new Map(featureList(files).features.map((feature) => [feature.id, feature]));
  const results = runChecks(files, config);
  const green = greenFeatures(results);
  const namedBroken = sectionIds(files, "session-handoff.md", "## Broken or unverified");
  const logged = sectionIds(files, "claude-progress.md", "## Verified now");
  const items: Item[] = [];
  const item = (name: string, ok: boolean, detail: string): void => {
    items.push({ item: name, status: ok ? "pass" : "fail", detail });
  };

  const unrecorded = results
    .filter(
      (result) =>
        result.status === "fail" &&
        (features.get(result.feature) as Feature).status !== "not-started" &&
        !namedBroken.includes(result.id),
    )
    .map((result) => result.id);
  item(
    "verification-recorded",
    unrecorded.length === 0,
    unrecorded.length > 0
      ? `${unrecorded.join(", ")} fails on a feature in flight and no ` +
          "session-handoff.md records the failure"
      : "every check on a feature in flight passes, and no failure is left unrecorded",
  );

  const wrong: string[] = [];
  for (const [fid, feature] of features) {
    if (feature.status === "passing" && !green.includes(fid)) {
      wrong.push(`${fid} is passing but a check on it fails`);
    }
    if (feature.status === "passing" && feature.evidence === undefined) {
      wrong.push(`${fid} is passing with no evidence recorded`);
    }
    if (green.includes(fid) && feature.status !== "passing") {
      wrong.push(`${fid} is ${feature.status} but every check on it passes`);
    }
  }
  item(
    "statuses-true",
    wrong.length === 0,
    wrong.length > 0
      ? wrong.join("; ")
      : "every feature status agrees with its checks, and every passing " +
          "status carries evidence",
  );

  const unlogged = green.filter((fid) => !logged.includes(fid));
  item(
    "progress-recorded",
    unlogged.length === 0,
    unlogged.length > 0
      ? `claude-progress.md does not record ${unlogged.join(", ")}, whose checks all pass`
      : "claude-progress.md records every feature whose checks all pass",
  );

  const stray = [...files.keys()].filter((path) => path.startsWith("scratch/")).sort();
  item(
    "no-stray-artifacts",
    stray.length === 0,
    stray.length > 0 ? `${stray.join(", ")} left in the workspace` : "no files under scratch/",
  );

  const nextSteps = sectionIds(files, "session-handoff.md", "## Next best step");
  const named = nextSteps[0];
  if (named === undefined) {
    item("next-step-written", false, "no session-handoff.md names a next best step");
  } else if (!features.has(named)) {
    item(
      "next-step-written",
      false,
      `session-handoff.md names ${named}, which is not a feature ` +
        "in feature_list.json",
    );
  } else if ((features.get(named) as Feature).status === "passing") {
    item(
      "next-step-written",
      false,
      `session-handoff.md names ${named}, which is already passing`,
    );
  } else {
    item(
      "next-step-written",
      true,
      `session-handoff.md names ${named}, which is ` +
        `${(features.get(named) as Feature).status}`,
    );
  }
  return items;
}

// --------------------------------------------------------------------------
// Surfaces.
// --------------------------------------------------------------------------

export function first(root: string, discipline: string) {
  const files = loadWorkspace(root);
  const config = JSON.parse(files.get("checks.json") as string) as Config;
  const events = firstSession(files, config, discipline);
  const items = cleanState(files, config);
  return {
    workspace: basename(root.replace(/\/+$/, "")),
    exit_discipline: discipline,
    task: config.task,
    events,
    clean_state: items,
    failed: items.filter((entry) => entry.status === "fail").length,
  };
}

export function resume(root: string, discipline: string) {
  const files = loadWorkspace(root);
  const config = JSON.parse(files.get("checks.json") as string) as Config;
  const events = firstSession(files, config, discipline);

  const handedOver = runChecks(files, config);
  const wasPass = new Map(handedOver.map((result) => [result.id, result.status === "pass"]));
  const wasGreen = greenFeatures(handedOver);

  const [log, chosen, results] = secondSession(files, config);
  const regressed = results
    .filter((result) => wasPass.get(result.id) === true && result.status === "fail")
    .map((result) => result.id);
  const completed = greenFeatures(results).filter((fid) => !wasGreen.includes(fid));
  const verdict = regressed.length === 0 && completed.length > 0 ? "resumed" : "derailed";
  log.record(
    "close the session",
    verdict === "resumed"
      ? `${completed.join(", ")} is finished and verified; nothing the previous ` +
          "session left green went red"
      : `${regressed.join(", ")} went from pass to fail; the work went into a ` +
          "feature that was already finished, and redoing it broke the check",
  );
  return {
    workspace: basename(root.replace(/\/+$/, "")),
    exit_discipline: discipline,
    first_session: { task: config.task, events },
    second_session: { chose: chosen, events: log.events, checks: results },
    outcome: { completed, regressed, result: verdict },
  };
}

const USAGE = "usage: main.ts first|resume <workspace-dir> --exit=clean|dirty";

function main(argv: readonly string[]): number {
  const command = argv[2];
  const target = argv[3];
  const flag = argv[4];
  if (argv.length !== 5 || !target || (command !== "first" && command !== "resume")) {
    console.error(USAGE);
    return 2;
  }
  if (flag !== "--exit=clean" && flag !== "--exit=dirty") {
    console.error(USAGE);
    return 2;
  }
  const discipline = flag.slice("--exit=".length);
  if (!existsSync(target) || !statSync(target).isDirectory() || !existsSync(join(target, "checks.json"))) {
    console.error(`error: not a workspace (needs checks.json): ${target}`);
    return 2;
  }
  if (command === "first") {
    const report = first(target, discipline);
    process.stdout.write(JSON.stringify(report, null, 2) + "\n");
    return report.failed === 0 ? 0 : 1;
  }
  const report = resume(target, discipline);
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return report.outcome.result === "resumed" ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
