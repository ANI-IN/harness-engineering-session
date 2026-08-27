// instruction-walk: demonstrate what an instruction architecture costs.
//
// `walk` is the demo: a budgeted deterministic reader works one task
// against one instruction tree, reading files top-down until the line
// budget runs out, following only the routes it has actually read. The
// failure is behavioral: with a realistic budget the monolith's buried
// hard constraint is never read (exit 1) while the router's is (exit 0).
// `stats` is the supporting evidence: per-task signal-to-noise and
// constraint zones for every tree. SPEC.md pins both; expected/ is the
// grading authority.

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

// The budgeted deterministic reader (SPEC.md, "The reader"). Files are
// read whole-file top-down until the budget runs out; a route is followed
// only if the line naming it was actually read.
export function walkTree(tree: string, treeName: string, task: Task, budget: number) {
  const entry = parseFile(join(tree, "AGENTS.md"));
  let remaining = budget;
  const visited: Array<{ file: string; lines_read: number; lines_total: number }> = [];

  const readFileBudgeted = (name: string, info: FileInfo): number => {
    const linesRead = Math.min(remaining, info.lines);
    remaining -= linesRead;
    visited.push({ file: name, lines_read: linesRead, lines_total: info.lines });
    return linesRead;
  };

  const entryRead = readFileBudgeted("AGENTS.md", entry);
  const entryLines = readFileSync(join(tree, "AGENTS.md"), "utf8")
    .split(/\r?\n/)
    .slice(0, entryRead);
  for (const topic of task.topics) {
    const docPath = join(tree, "docs", `${topic}.md`);
    const routeSeen = entryLines.some((line) => line.includes(`docs/${topic}.md`));
    if (existsSync(docPath) && routeSeen && remaining > 0) {
      readFileBudgeted(`docs/${topic}.md`, parseFile(docPath));
    }
  }

  const readOf = new Map(visited.map((item) => [item.file, item.lines_read]));
  const files: Array<[string, FileInfo]> = [["AGENTS.md", entry]];
  const docsDir = join(tree, "docs");
  if (existsSync(docsDir) && statSync(docsDir).isDirectory()) {
    for (const name of readdirSync(docsDir).sort()) {
      if (name.endsWith(".md")) {
        files.push([`docs/${name}`, parseFile(join(docsDir, name))]);
      }
    }
  }
  const constraints: Array<{ text: string; file: string; line: number; read: boolean }> = [];
  for (const [name, info] of files) {
    for (const rule of info.rules) {
      if (rule.hard) {
        constraints.push({
          text: rule.text,
          file: name,
          line: rule.line,
          read: rule.line <= (readOf.get(name) ?? 0),
        });
      }
    }
  }
  const missed = constraints.filter((constraint) => !constraint.read).length;
  return {
    tree: treeName,
    task: task.id,
    budget,
    files_visited: visited,
    lines_spent: budget - remaining,
    hard_constraints: constraints,
    missed,
  };
}

const USAGE =
  "usage: main.ts walk <tree-dir> <tasks.json> <task-id> --budget N | " +
  "main.ts stats <trees-dir> <tasks.json>";

function loadTasks(tasksPath: string): Task[] | null {
  try {
    return (JSON.parse(readFileSync(tasksPath, "utf8")) as { tasks: Task[] }).tasks;
  } catch {
    return null;
  }
}

function runStats(argv: readonly string[]): number {
  const [treesDir, tasksPath] = argv;
  if (!treesDir || !tasksPath || argv.length !== 2) {
    console.error(USAGE);
    return 2;
  }
  if (!existsSync(treesDir) || !statSync(treesDir).isDirectory()) {
    console.error(`error: not a directory: ${treesDir}`);
    return 2;
  }
  const tasks = loadTasks(tasksPath);
  if (tasks === null) {
    console.error(`error: cannot read tasks: ${tasksPath}`);
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

function runWalk(argv: readonly string[]): number {
  const [tree, tasksPath, taskId, budgetFlag, budgetText] = argv;
  if (
    !tree || !tasksPath || !taskId || budgetFlag !== "--budget" ||
    !budgetText || !/^\d+$/.test(budgetText) || argv.length !== 5
  ) {
    console.error(USAGE);
    return 2;
  }
  if (!existsSync(join(tree, "AGENTS.md"))) {
    console.error(`error: not an instruction tree: ${tree}`);
    return 2;
  }
  const tasks = loadTasks(tasksPath);
  if (tasks === null) {
    console.error(`error: cannot read tasks: ${tasksPath}`);
    return 2;
  }
  const task = tasks.find((entry) => entry.id === taskId);
  if (task === undefined) {
    console.error(`error: no task with id ${taskId}`);
    return 2;
  }
  const treeName = tree.replace(/\/+$/, "").split("/").pop() as string;
  const report = walkTree(tree, treeName, task, Number(budgetText));
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return report.missed > 0 ? 1 : 0;
}

function main(argv: readonly string[]): number {
  if (argv[2] === "stats") {
    return runStats(argv.slice(3));
  }
  if (argv[2] === "walk") {
    return runWalk(argv.slice(3));
  }
  console.error(USAGE);
  return 2;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
