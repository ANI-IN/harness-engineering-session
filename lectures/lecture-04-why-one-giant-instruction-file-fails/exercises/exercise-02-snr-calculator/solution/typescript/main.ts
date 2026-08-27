// snr-calculator exercise, TypeScript solution.
//
// Computes per-task instruction signal-to-noise for one tree: relevant
// instruction lines (tag-matched) over loaded lines. Contract: ../../SPEC.md.

import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const RULE_RE = /^- \[([a-z]+)(!?)\] (.+)$/;

interface Task {
  readonly id: string;
  readonly topics: readonly string[];
}

function readLines(path: string): string[] {
  let lines = readFileSync(path, "utf8").split(/\r?\n/);
  if (lines.length > 0 && lines[lines.length - 1] === "") lines = lines.slice(0, -1);
  return lines;
}

export function relevantCount(lines: readonly string[], topics: readonly string[]): number {
  // An instruction line is relevant when its TAG names one of the task's
  // topics. Prose that mentions a topic word is context cost, not signal.
  let count = 0;
  for (const line of lines) {
    const match = line.match(RULE_RE);
    if (match && match[1] && topics.includes(match[1])) count += 1;
  }
  return count;
}

export function snrReport(tree: string, tasks: readonly Task[]): Record<string, unknown> {
  const lines = readLines(join(tree, "AGENTS.md"));
  const loaded = lines.length;
  const rows = [];
  let snrTotal = 0;
  for (const task of tasks) {
    const relevant = relevantCount(lines, task.topics);
    const snr = loaded > 0 ? relevant / loaded : 0;
    snrTotal += snr;
    rows.push({ id: task.id, loaded_lines: loaded, relevant_lines: relevant, snr });
  }
  return {
    tasks: rows,
    mean_snr: rows.length > 0 ? snrTotal / rows.length : 0,
  };
}

function main(argv: readonly string[]): number {
  const tree = argv[2];
  const tasksPath = argv[3];
  if (!tree || !tasksPath || argv.length !== 4) {
    console.error("usage: main.ts <tree-dir> <tasks.json>");
    return 2;
  }
  if (!existsSync(join(tree, "AGENTS.md"))) {
    console.error(`error: no AGENTS.md in ${tree}`);
    return 2;
  }
  let tasks: Task[];
  try {
    tasks = (JSON.parse(readFileSync(tasksPath, "utf8")) as { tasks: Task[] }).tasks;
  } catch (error) {
    console.error(`error: cannot read tasks: ${String(error)}`);
    return 2;
  }
  process.stdout.write(JSON.stringify(snrReport(tree, tasks), null, 2) + "\n");
  return 0;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
