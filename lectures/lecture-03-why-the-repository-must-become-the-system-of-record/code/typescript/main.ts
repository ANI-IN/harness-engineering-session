// fresh-session-reader: the fresh-session test, mechanized.
//
// Answers the five questions a brand-new agent session must be able to
// answer from repository contents alone, extracting each answer from a
// specific language-neutral artifact per SPEC.md. Exit code 1 when any
// question is unanswered: a fresh session cannot start work on this
// repository without guessing.

import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

interface Question {
  readonly id: string;
  readonly question: string;
  readonly answered: boolean;
  readonly answer: string | null;
  readonly source: string | null;
}

function firstProseLine(path: string): string | null {
  if (!existsSync(path)) return null;
  for (const line of readFileSync(path, "utf8").split(/\r?\n/)) {
    const stripped = line.trim();
    if (stripped && !stripped.startsWith("#")) return stripped;
  }
  return null;
}

function taggedLine(path: string, tag: string): string | null {
  if (!existsSync(path)) return null;
  const escaped = tag.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = readFileSync(path, "utf8").match(new RegExp(`^- ${escaped}: (.+)$`, "m"));
  return match && match[1] ? match[1].trim() : null;
}

function instructionsFile(repo: string): string | null {
  for (const name of ["AGENTS.md", "CLAUDE.md"]) {
    if (existsSync(join(repo, name))) return name;
  }
  return null;
}

function question(
  id: string,
  text: string,
  answer: string | null,
  source: string | null,
): Question {
  return {
    id,
    question: text,
    answered: answer !== null,
    answer,
    source: answer !== null ? source : null,
  };
}

export function readRepo(repo: string): Record<string, unknown> {
  const entryName = instructionsFile(repo);
  const entryPath = entryName ? join(repo, entryName) : null;

  const questions: Question[] = [
    question(
      "what-is-this", "What is this system?",
      entryPath ? firstProseLine(entryPath) : null,
      entryName,
    ),
    question(
      "how-organized", "How is it organized?",
      firstProseLine(join(repo, "docs", "ARCHITECTURE.md")),
      "docs/ARCHITECTURE.md",
    ),
    question(
      "how-to-run", "How do I run it?",
      entryPath ? taggedLine(entryPath, "Run") : null,
      entryName ? `${entryName} (Run line)` : null,
    ),
    question(
      "how-to-verify", "How do I verify it?",
      entryPath ? taggedLine(entryPath, "Verification") : null,
      entryName ? `${entryName} (Verification line)` : null,
    ),
    question(
      "where-are-we", "Where are we now?",
      taggedLine(join(repo, "claude-progress.md"), "Next best step"),
      "claude-progress.md (Next best step line)",
    ),
  ];

  const answered = questions.filter((q) => q.answered).length;
  const total = questions.length;
  return {
    questions,
    answered,
    total,
    visibility_gap: total > 0 ? (total - answered) / total : 0,
    ready: answered === total,
  };
}

function main(argv: readonly string[]): number {
  const repo = argv[2];
  if (!repo || argv.length !== 3) {
    console.error("usage: main.ts <repo-dir>");
    return 2;
  }
  if (!existsSync(repo) || !statSync(repo).isDirectory()) {
    console.error(`error: not a directory: ${repo}`);
    return 2;
  }
  const report = readRepo(repo);
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return report.ready ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
