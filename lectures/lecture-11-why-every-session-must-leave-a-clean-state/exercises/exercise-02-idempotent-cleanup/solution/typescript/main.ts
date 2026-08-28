// idempotent-cleanup: the exit protocol, safe to run again.
//
// A session's exit protocol gets interrupted: the machine dies, the run is
// cancelled, a retry re-enters it. Whatever ran already must not run twice,
// so every step reconciles the artifact towards the state it wants instead
// of performing an action. Each step reports whether it changed anything,
// and a pass in which nothing changed is `already-clean`.
//
// The workspace is read from disk once and edited in memory, so the
// committed fixture never changes and repeated runs are reproducible.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { basename, join } from "node:path";
import { pathToFileURL } from "node:url";

const SESSION_HEADING_PREFIX = "## Session ";

interface Session {
  session: string;
  date: string;
  verified: string[];
  next_step: string;
}

interface Feature {
  id: string;
  title: string;
  behavior: string;
  verification: string;
  status: string;
  evidence?: { command: string; observed: string; date: string };
}

interface FeatureList {
  project: string;
  updated: string;
  features: Feature[];
}

type Files = Map<string, string>;

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

function beforeColon(value: string): string {
  return (value.split(":")[0] ?? value).trim();
}

// The ids named by `- <id>: <text>` bullets under one markdown heading.
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

function progressEntry(session: Session): string {
  return (
    `## Session ${session.session} (${session.date})\n\n` +
    `- Verified: ${session.verified.join(", ")}.\n` +
    `- Next: ${session.next_step}\n\n`
  );
}

function featuresById(files: Files): Map<string, Feature> {
  const data = JSON.parse(files.get("feature_list.json") as string) as FeatureList;
  return new Map(data.features.map((feature) => [feature.id, feature]));
}

function handoffText(session: Session, features: Map<string, Feature>): string {
  const verified = session.verified
    .map((fid) => `- ${fid}: verified by ${(features.get(fid) as Feature).verification}`)
    .join("\n");
  return (
    "# Session handoff\n\n" +
    `## Verified now\n\n${verified}\n\n` +
    `## Next best step\n\n- ${session.next_step}\n`
  );
}

// Ensure claude-progress.md carries this session's entry, exactly once.
//
// The log is append-only by nature, which is what makes this the step that
// has to reconcile rather than append: the entry for a session that is
// already recorded is already there.
function recordProgress(files: Files, session: Session): [boolean, string] {
  const marker = `## Session ${session.session}`;
  const text = files.get("claude-progress.md") as string;
  if (text.split(/\r?\n/).some((line) => line.startsWith(marker))) {
    return [false, `claude-progress.md already records session ${session.session}`];
  }
  const index = text.indexOf(SESSION_HEADING_PREFIX);
  files.set("claude-progress.md", text.slice(0, index) + progressEntry(session) + text.slice(index));
  return [true, `added a session ${session.session} entry to claude-progress.md`];
}

function setStatuses(files: Files, session: Session): [boolean, string] {
  const data = JSON.parse(files.get("feature_list.json") as string) as FeatureList;
  const changed: string[] = [];
  for (const feature of data.features) {
    if (!session.verified.includes(feature.id)) continue;
    if (feature.status === "passing" && feature.evidence !== undefined) continue;
    feature.status = "passing";
    feature.evidence = {
      command: feature.verification,
      observed: "exit 0",
      date: session.date,
    };
    changed.push(feature.id);
  }
  if (changed.length === 0) {
    return [false, `${session.verified.join(", ")} already passing with evidence`];
  }
  files.set("feature_list.json", JSON.stringify(data, null, 2) + "\n");
  return [true, `set ${changed.join(", ")} to passing with evidence`];
}

function clearScratch(files: Files, _session: Session): [boolean, string] {
  const stray = [...files.keys()].filter((path) => path.startsWith("scratch/")).sort();
  if (stray.length === 0) return [false, "no files under scratch/"];
  for (const path of stray) files.delete(path);
  return [true, `removed ${stray.join(", ")}`];
}

function writeHandoff(files: Files, session: Session): [boolean, string] {
  const wanted = beforeColon(session.next_step);
  const named = sectionIds(files, "session-handoff.md", "## Next best step");
  if (named.length > 0 && named[0] === wanted) {
    return [false, `session-handoff.md already names ${wanted}`];
  }
  files.set("session-handoff.md", handoffText(session, featuresById(files)));
  return [true, `wrote session-handoff.md naming ${wanted}`];
}

const STEPS: [string, (files: Files, session: Session) => [boolean, string]][] = [
  ["record-progress", recordProgress],
  ["set-statuses", setStatuses],
  ["clear-scratch", clearScratch],
  ["write-handoff", writeHandoff],
];

export function cleanup(root: string, passes: number) {
  const files = loadWorkspace(root);
  const session = JSON.parse(files.get("session.json") as string) as Session;
  const reports = [];
  for (let number = 1; number <= passes; number += 1) {
    const steps = [];
    let changedAny = false;
    for (const [stepId, step] of STEPS) {
      const [changed, outcome] = step(files, session);
      changedAny = changedAny || changed;
      steps.push({ id: stepId, outcome });
    }
    reports.push({
      pass: number,
      steps,
      verdict: changedAny ? "changed" : "already-clean",
    });
  }

  const marker = `## Session ${session.session}`;
  const entries = (files.get("claude-progress.md") as string)
    .split(/\r?\n/)
    .filter((line) => line.startsWith(marker)).length;
  const named = sectionIds(files, "session-handoff.md", "## Next best step");
  return {
    workspace: basename(root.replace(/\/+$/, "")),
    session: session.session,
    passes: reports,
    summary: {
      handoff_next_step: named.length > 0 ? named[0] : null,
      passing: [...featuresById(files).values()]
        .filter((feature) => feature.status === "passing")
        .map((feature) => feature.id)
        .sort(),
      progress_entries: entries,
      scratch_files: [...files.keys()].filter((path) => path.startsWith("scratch/")).length,
    },
  };
}

const USAGE = "usage: main.ts <workspace-dir> --passes=<1-5>";

function main(argv: readonly string[]): number {
  const root = argv[2];
  const flag = argv[3];
  if (argv.length !== 4 || !root || !flag || !flag.startsWith("--passes=")) {
    console.error(USAGE);
    return 2;
  }
  const value = flag.slice("--passes=".length);
  if (!/^[0-9]+$/.test(value) || Number(value) < 1 || Number(value) > 5) {
    console.error(USAGE);
    return 2;
  }
  if (!existsSync(root) || !statSync(root).isDirectory() || !existsSync(join(root, "session.json"))) {
    console.error(`error: not a workspace (needs session.json): ${root}`);
    return 2;
  }
  process.stdout.write(JSON.stringify(cleanup(root, Number(value)), null, 2) + "\n");
  return 0;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
