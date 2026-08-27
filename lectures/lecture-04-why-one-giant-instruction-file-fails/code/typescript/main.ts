// instruction-stats: measure what an instruction architecture costs.
//
// For each instruction tree (an AGENTS.md entry file plus optional docs/
// topic files), simulate the loading rule (entry always; docs/<topic>.md
// for each task topic when present), compute per-task signal-to-noise, and
// locate hard constraints by zone, flagging the ones buried in the middle
// of long files. SPEC.md pins the formats; expected/ is the grading
// authority.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const RULE_RE = /^- \[([a-z]+)(!?)\] (.+)$/;
const BURIED_MIN_LINES = 20;
const ZONES = ["top", "middle", "bottom"] as const;

interface Rule {
  readonly topic: string;
  readonly hard: boolean;
  readonly text: string;
  readonly line: number;
}

interface FileInfo {
  readonly lines: number;
  readonly rules: readonly Rule[];
}

interface Task {
  readonly id: string;
  readonly topics: readonly string[];
}

function parseFile(path: string): FileInfo {
  let lines = readFileSync(path, "utf8").split(/\r?\n/);
  if (lines.length > 0 && lines[lines.length - 1] === "") {
    lines = lines.slice(0, -1);
  }
  const rules: Rule[] = [];
  lines.forEach((line, index) => {
    const match = line.match(RULE_RE);
    if (match && match[1] && match[3]) {
      rules.push({
        topic: match[1],
        hard: match[2] === "!",
        text: match[3],
        line: index + 1,
      });
    }
  });
  return { lines: lines.length, rules };
}

function zoneOf(line: number, total: number): string {
  if (total === 0) return "top";
  return ZONES[Math.min(Math.floor(((line - 1) * 3) / total), 2)] ?? "top";
}

export function analyzeTree(tree: string, name: string, tasks: readonly Task[]) {
  const entry = parseFile(join(tree, "AGENTS.md"));
  const docs = new Map<string, FileInfo>();
  const docsDir = join(tree, "docs");
  if (existsSync(docsDir) && statSync(docsDir).isDirectory()) {
    for (const file of readdirSync(docsDir).filter((f) => f.endsWith(".md")).sort()) {
      docs.set(file.replace(/\.md$/, ""), parseFile(join(docsDir, file)));
    }
  }

  const taskRows = tasks.map((task) => {
    const loaded: FileInfo[] = [entry];
    for (const topic of task.topics) {
      const doc = docs.get(topic);
      if (doc) loaded.push(doc);
    }
    const loadedLines = loaded.reduce((sum, info) => sum + info.lines, 0);
    const relevant = loaded.reduce(
      (sum, info) => sum + info.rules.filter((rule) => task.topics.includes(rule.topic)).length,
      0,
    );
    return {
      id: task.id,
      loaded_lines: loadedLines,
      relevant_lines: relevant,
      snr: loadedLines > 0 ? relevant / loadedLines : 0,
    };
  });

  const hardConstraints = [];
  const allFiles: [string, FileInfo][] = [
    ["AGENTS.md", entry],
    ...[...docs.keys()].sort().map((stem): [string, FileInfo] => {
      const info = docs.get(stem);
      if (!info) throw new Error("unreachable");
      return [`docs/${stem}.md`, info];
    }),
  ];
  for (const [fileName, info] of allFiles) {
    for (const rule of info.rules) {
      if (!rule.hard) continue;
      const zone = zoneOf(rule.line, info.lines);
      hardConstraints.push({
        text: rule.text,
        file: fileName,
        line: rule.line,
        zone,
        buried: zone === "middle" && info.lines > BURIED_MIN_LINES,
      });
    }
  }

  const totalLines =
    entry.lines + [...docs.values()].reduce((sum, info) => sum + info.lines, 0);
  return {
    name,
    files: 1 + docs.size,
    total_lines: totalLines,
    entry_lines: entry.lines,
    tasks: taskRows,
    mean_snr:
      taskRows.length > 0
        ? taskRows.reduce((sum, row) => sum + row.snr, 0) / taskRows.length
        : 0,
    hard_constraints: hardConstraints,
    buried_hard_constraints: hardConstraints.filter((h) => h.buried).length,
  };
}

function main(argv: readonly string[]): number {
  const treesDir = argv[2];
  const tasksPath = argv[3];
  if (!treesDir || !tasksPath || argv.length !== 4) {
    console.error("usage: main.ts <trees-dir> <tasks.json>");
    return 2;
  }
  if (!existsSync(treesDir) || !statSync(treesDir).isDirectory()) {
    console.error(`error: not a directory: ${treesDir}`);
    return 2;
  }
  let tasks: Task[];
  try {
    tasks = (JSON.parse(readFileSync(tasksPath, "utf8")) as { tasks: Task[] }).tasks;
  } catch (error) {
    console.error(`error: cannot read tasks: ${String(error)}`);
    return 2;
  }

  const trees = readdirSync(treesDir)
    .filter((entry) => statSync(join(treesDir, entry)).isDirectory())
    .sort()
    .map((name) => analyzeTree(join(treesDir, name), name, tasks));
  const report = {
    trees,
    comparison: {
      mean_snr: Object.fromEntries(trees.map((tree) => [tree.name, tree.mean_snr])),
      buried_hard_constraints: Object.fromEntries(
        trees.map((tree) => [tree.name, tree.buried_hard_constraints]),
      ),
    },
  };
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return 0;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
