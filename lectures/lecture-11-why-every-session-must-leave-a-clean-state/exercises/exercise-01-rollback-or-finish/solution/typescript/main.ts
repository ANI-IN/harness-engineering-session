// rollback-or-finish: what the exit protocol owes each in-flight edit.
//
// A session reaches its end with a list of edits it made. For each one the
// exit protocol has three moves, and picking between them is the whole
// exercise: keep a verified edit, revert an unverified edit the session
// created, and declare an unverified edit to a file that existed before.
// Declaring what should have been reverted is what leaves a half applied
// change in the tree for the next session to trip over.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { basename, join } from "node:path";
import { pathToFileURL } from "node:url";

interface Check {
  id: string;
  kind: string;
  path: string;
  key?: string;
  prefix?: string;
}

interface Edit {
  path: string;
  check: string;
  created: boolean;
}

interface Ending {
  session: string;
  edits: Edit[];
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

// The check engine, unchanged from the lecture demo's contract.
function runCheck(files: Files, check: Check): [boolean, string] {
  const path = check.path;
  if (!files.has(path)) return [false, `${path} missing`];
  const lines = (files.get(path) as string).split(/\r?\n/);
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

// The exit protocol's three moves.
//
// A verified edit is finished. An unverified edit the session created can
// be reverted, and reverting restores the last consistent state exactly.
// An unverified edit to a file that already existed cannot be reverted
// without discarding state the session does not own, so it stays and the
// handoff must name it.
function decide(actual: string, created: boolean): string {
  if (actual === "pass") return "finish";
  return created ? "roll-back" : "declare";
}

export function review(root: string, ending: Ending) {
  const files = loadWorkspace(root);
  const config = JSON.parse(files.get("checks.json") as string) as { checks: Check[] };
  const byId = new Map(config.checks.map((check) => [check.id, check]));

  const edits = [];
  const summary = { declare: 0, finish: 0, roll_back: 0 };
  for (const edit of ending.edits) {
    const [passed, detail] = runCheck(files, byId.get(edit.check) as Check);
    const actual = passed ? "pass" : "fail";
    const decision = decide(actual, edit.created);
    summary[decision.replace("-", "_") as keyof typeof summary] += 1;
    edits.push({
      path: edit.path,
      check: edit.check,
      created: edit.created,
      actual,
      detail,
      decision,
    });
  }
  const owed = summary.declare + summary.roll_back;
  return {
    workspace: basename(root.replace(/\/+$/, "")),
    session: ending.session,
    edits,
    summary,
    verdict: owed === 0 ? "may-end" : "exit-protocol-owed",
  };
}

function main(argv: readonly string[]): number {
  const root = argv[2];
  const endingPath = argv[3];
  if (argv.length !== 4 || !root || !endingPath) {
    console.error("usage: main.ts <workspace-dir> <ending-file>");
    return 2;
  }
  if (!existsSync(root) || !statSync(root).isDirectory() || !existsSync(join(root, "checks.json"))) {
    console.error(`error: not a workspace (needs checks.json): ${root}`);
    return 2;
  }
  if (!existsSync(endingPath) || !statSync(endingPath).isFile()) {
    console.error(`error: no such ending file: ${endingPath}`);
    return 2;
  }
  const ending = JSON.parse(readFileSync(endingPath, "utf8")) as Ending;
  const report = review(root, ending);
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return report.verdict === "may-end" ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
