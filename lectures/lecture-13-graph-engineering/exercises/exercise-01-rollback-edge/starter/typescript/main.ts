// rollback-edge: the node a rollback edge leads to.
//
// The lecture's graph declares one rollback edge, and the node at the end
// of it replays the apply journal. This surface is that node on its own:
// given the workspace as it stands after a failed verification and the
// journal of what the run wrote, decide for each operation whether it can
// be reverted, revert the ones that can, and report the residue.
//
// The reverting rules below are complete and correct: an appended line may
// be removed only while it is still the last line of its file, and a
// created file may be removed only while it still holds exactly the lines
// the run wrote. What is not settled is the order the journal is replayed
// in. See README.md, "Your task", and SPEC.md, "Starter state".
//
// The workspace is read once and reverted in memory, so the committed
// fixtures never change.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { basename, join } from "node:path";
import { pathToFileURL } from "node:url";

interface Operation {
  op: string;
  path: string;
  line?: string;
  lines?: string[];
}

interface Journal {
  session: string;
  operations: Operation[];
}

interface Row {
  index: number;
  op: string;
  outcome: string;
  path: string;
  target: string;
  why: string;
}

type Files = Map<string, string>;

function loadWorkspace(root: string): Files {
  const files: Files = new Map();
  const collect = (dir: string, prefix: string): void => {
    for (const name of readdirSync(dir).sort()) {
      const full = join(dir, name);
      const relative = prefix ? `${prefix}/${name}` : name;
      if (statSync(full).isDirectory()) collect(full, relative);
      else files.set(relative, readFileSync(full, "utf8"));
    }
  };
  collect(root, "");
  return files;
}

// Non-empty lines, LF or CRLF alike (docs/conventions.md, semantic rules).
function linesOf(text: string): string[] {
  return text.split(/\r?\n/).filter((line) => line.length > 0);
}

function joinLines(lines: string[]): string {
  return lines.map((line) => `${line}\n`).join("");
}

function sameLines(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((line, index) => line === right[index]);
}

// Try to reverse one journalled write. Returns whether it was reverted, the
// target it names, and the sentence explaining the outcome.
function revert(files: Files, operation: Operation): [boolean, string, string] {
  const path = operation.path;
  const body = linesOf(files.get(path) ?? "");
  if (operation.op === "create") {
    if (sameLines(body, operation.lines as string[])) {
      files.delete(path);
      return [true, path, `removed ${path}, which still held only the lines this run wrote`];
    }
    return [
      false,
      path,
      `${path} no longer holds the lines this run created, so removing it ` +
        "would discard a later change",
    ];
  }
  const line = operation.line as string;
  if (body.length > 0 && body[body.length - 1] === line) {
    files.set(path, joinLines(body.slice(0, -1)));
    return [true, line, `removed the last line ${line} from ${path}`];
  }
  return [
    false,
    line,
    `${line} is no longer the last line of ${path}, so removing it would ` +
      "discard a later change",
  ];
}

// Replay the journal and report one row per operation, in journal order.
//
// The journal lists the writes in the order the run made them, so this
// walks it the same way, from the first write to the last.
function rollback(files: Files, journal: Journal): Row[] {
  const rows: Row[] = [];
  for (const [index, operation] of journal.operations.entries()) {
    const [reverted, target, why] = revert(files, operation);
    rows.push({
      index,
      op: operation.op,
      outcome: reverted ? "reverted" : "kept",
      path: operation.path,
      target,
      why,
    });
  }
  return rows;
}

function residueOf(rows: Row[]): string[] {
  const left: string[] = [];
  for (const row of rows) {
    if (row.outcome === "reverted") continue;
    if (row.op === "create") left.push(`${row.path} is still in the workspace`);
    else left.push(`${row.path} still carries ${row.target}`);
  }
  return left;
}

export function report(root: string, journal: Journal) {
  const files = loadWorkspace(root);
  const rows = rollback(files, journal);
  const residue = residueOf(rows);
  return {
    workspace: basename(root.replace(/\/+$/, "")),
    session: journal.session,
    operations: rows,
    residue,
    restored: residue.length === 0,
    verdict: residue.length === 0 ? "restored" : "residue-left",
  };
}

const USAGE = "usage: main.ts <workspace-dir> <journal-file>";

function main(argv: readonly string[]): number {
  const root = argv[2];
  const journalPath = argv[3];
  if (argv.length !== 4 || root === undefined || journalPath === undefined) {
    console.error(USAGE);
    return 2;
  }
  if (!existsSync(root) || !statSync(root).isDirectory()) {
    console.error(`error: not a workspace directory: ${root}`);
    return 2;
  }
  if (!existsSync(journalPath) || !statSync(journalPath).isFile()) {
    console.error(`error: no journal file at ${journalPath}`);
    return 2;
  }
  const journal = JSON.parse(readFileSync(journalPath, "utf8")) as Journal;
  const result = report(root, journal);
  process.stdout.write(JSON.stringify(result, null, 2) + "\n");
  return result.restored ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
