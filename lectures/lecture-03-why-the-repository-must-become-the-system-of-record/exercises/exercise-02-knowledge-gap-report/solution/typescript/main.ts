// knowledge-gap-report exercise, TypeScript solution.
//
// Computes the knowledge visibility gap from an inventory of project
// decisions: which live in the repository (location starts with "repo:")
// and which live somewhere an agent cannot see.

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const GAP_THRESHOLD = 0.1;

interface Entry {
  readonly id: string;
  readonly decision: string;
  readonly location: string;
  readonly critical: boolean;
}

export function inRepo(location: string): boolean {
  // A decision is visible to the agent only when its recorded location is
  // a repository path, marked by the exact prefix "repo:". A location that
  // merely mentions repositories (a Confluence page about repo guidelines,
  // a Slack channel named #repo-help) is still invisible.
  return location.startsWith("repo:");
}

export function gapReport(entries: readonly Entry[]): Record<string, unknown> {
  const outside = entries.filter((entry) => !inRepo(entry.location));
  const total = entries.length;
  const gap = total > 0 ? outside.length / total : 0;
  return {
    total,
    in_repo: total - outside.length,
    outside: outside.length,
    visibility_gap: gap,
    critical_outside: outside.filter((entry) => entry.critical).map((entry) => entry.id),
    verdict: gap <= GAP_THRESHOLD ? "acceptable" : "needs-externalization",
  };
}

export function parseInventory(text: string): Entry[] {
  const entries: Entry[] = [];
  const lines = text.split(/\r?\n/);
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (!line || !line.trim()) continue;
    let entry: Entry;
    try {
      entry = JSON.parse(line) as Entry;
    } catch (error) {
      throw new Error(`malformed inventory at line ${index + 1}: ${String(error)}`, {
        cause: error,
      });
    }
    for (const field of ["id", "decision", "location", "critical"] as const) {
      if (!(field in entry)) {
        throw new Error(`malformed inventory at line ${index + 1}: missing '${field}'`);
      }
    }
    entries.push(entry);
  }
  return entries;
}

function main(argv: readonly string[]): number {
  const path = argv[2];
  if (!path || argv.length !== 3) {
    console.error("usage: main.ts <inventory.jsonl>");
    return 2;
  }
  let text: string;
  try {
    text = readFileSync(path, "utf8");
  } catch (error) {
    console.error(`error: cannot read inventory: ${String(error)}`);
    return 2;
  }
  let entries: Entry[];
  try {
    entries = parseInventory(text);
  } catch (error) {
    console.error(`error: ${error instanceof Error ? error.message : String(error)}`);
    return 1;
  }
  process.stdout.write(JSON.stringify(gapReport(entries), null, 2) + "\n");
  return 0;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
