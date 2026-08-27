// router-validator exercise, TypeScript solution.
//
// Validates a router-style instruction tree against four structural checks:
// short entry, resolvable routes, hard constraints only in the entry, and
// no rule text duplicated across files. Contract: ../../SPEC.md.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const ENTRY_MAX_LINES = 20;
const RULE_RE = /^- \[([a-z]+)(!?)\] (.+)$/;
const ROUTE_RE = /^- (docs\/[a-z-]+\.md)\b/;

interface Violation {
  readonly file: string;
  readonly line: number;
  readonly detail: string;
}

function readLines(path: string): string[] {
  let lines = readFileSync(path, "utf8").split(/\r?\n/);
  if (lines.length > 0 && lines[lines.length - 1] === "") lines = lines.slice(0, -1);
  return lines;
}

function treeFiles(tree: string): [string, string[]][] {
  const files: [string, string[]][] = [["AGENTS.md", readLines(join(tree, "AGENTS.md"))]];
  const docsDir = join(tree, "docs");
  if (existsSync(docsDir) && statSync(docsDir).isDirectory()) {
    for (const doc of readdirSync(docsDir).filter((f) => f.endsWith(".md")).sort()) {
      files.push([`docs/${doc}`, readLines(join(docsDir, doc))]);
    }
  }
  return files;
}

function checkEntryLength(tree: string): Violation[] {
  const lines = readLines(join(tree, "AGENTS.md"));
  if (lines.length > ENTRY_MAX_LINES) {
    return [{
      file: "AGENTS.md", line: lines.length,
      detail: `entry file is ${lines.length} lines; the router limit is ${ENTRY_MAX_LINES}`,
    }];
  }
  return [];
}

function checkRoutesResolve(tree: string): Violation[] {
  const violations: Violation[] = [];
  readLines(join(tree, "AGENTS.md")).forEach((line, index) => {
    const match = line.match(ROUTE_RE);
    if (match && match[1] && !existsSync(join(tree, match[1]))) {
      violations.push({
        file: "AGENTS.md", line: index + 1,
        detail: `route target does not exist: ${match[1]}`,
      });
    }
  });
  return violations;
}

function checkHardInEntry(tree: string): Violation[] {
  const violations: Violation[] = [];
  for (const [name, lines] of treeFiles(tree)) {
    if (name === "AGENTS.md") continue;
    lines.forEach((line, index) => {
      const match = line.match(RULE_RE);
      if (match && match[2] === "!" && match[3]) {
        violations.push({
          file: name, line: index + 1,
          detail: `hard constraint outside the entry file: ${match[3]}`,
        });
      }
    });
  }
  return violations;
}

function checkNoDuplicates(tree: string): Violation[] {
  const seen = new Map<string, string>();
  const violations: Violation[] = [];
  for (const [name, lines] of treeFiles(tree)) {
    lines.forEach((line, index) => {
      const match = line.match(RULE_RE);
      if (!match || !match[3]) return;
      const text = match[3];
      const earlier = seen.get(text);
      if (earlier) {
        violations.push({
          file: name, line: index + 1,
          detail: `rule text duplicated (also in ${earlier}): ${text}`,
        });
      } else {
        seen.set(text, name);
      }
    });
  }
  return violations;
}

const CHECKS: [string, (tree: string) => Violation[]][] = [
  ["entry-length", checkEntryLength],
  ["routes-resolve", checkRoutesResolve],
  ["hard-in-entry", checkHardInEntry],
  ["no-duplicates", checkNoDuplicates],
];

export function validate(tree: string): Record<string, unknown> {
  const checks = CHECKS.map(([id, run]) => {
    const violations = run(tree);
    return { id, passed: violations.length === 0, violations };
  });
  return { checks, ok: checks.every((check) => check.passed) };
}

function main(argv: readonly string[]): number {
  const tree = argv[2];
  if (!tree || argv.length !== 3) {
    console.error("usage: main.ts <tree-dir>");
    return 2;
  }
  if (!existsSync(join(tree, "AGENTS.md"))) {
    console.error(`error: no AGENTS.md in ${tree}`);
    return 2;
  }
  process.stdout.write(JSON.stringify(validate(tree), null, 2) + "\n");
  return 0;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
