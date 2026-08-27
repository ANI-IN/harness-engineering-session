// fresh-session-answers exercise, TypeScript starter.
//
// All five questions are attempted, but three extractors are naive first
// drafts with a realistic mistake each (see SPEC.md "Starter state"):
// how-organized answers from the instructions file instead of the
// architecture doc, how-to-verify grabs the first line that MENTIONS
// verification instead of the Verification line, and where-are-we returns
// the progress file's heading instead of the Next best step line. Fix the
// three per SPEC.md. Run ../../verify.sh --stack=typescript until it
// exits 0.

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

function lineMentioning(path: string, needle: string): string | null {
  // Naive helper: first line whose text contains the needle (any case).
  if (!existsSync(path)) return null;
  for (const line of readFileSync(path, "utf8").split(/\r?\n/)) {
    if (line.toLowerCase().includes(needle) && line.trim()) return line.trim();
  }
  return null;
}

function rawFirstLine(path: string): string | null {
  // Naive helper: first non-empty line, headings included.
  if (!existsSync(path)) return null;
  for (const line of readFileSync(path, "utf8").split(/\r?\n/)) {
    if (line.trim()) return line.trim();
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
    // Naive draft: answers "how is it organized" from the instructions
    // file's overview line. Exercise: extract the first prose line of
    // docs/ARCHITECTURE.md, source "docs/ARCHITECTURE.md".
    question(
      "how-organized", "How is it organized?",
      entryPath ? firstProseLine(entryPath) : null,
      entryName,
    ),
    question(
      "how-to-run", "How do I run it?",
      entryPath ? taggedLine(entryPath, "Run") : null,
      entryName ? `${entryName} (Run line)` : null,
    ),
    // Naive draft: any line that mentions verification. Prose about
    // verifying is not a verification command. Exercise: extract the
    // "- Verification: <command>" line's value.
    question(
      "how-to-verify", "How do I verify it?",
      entryPath ? lineMentioning(entryPath, "verif") : null,
      entryName ? `${entryName} (Verification line)` : null,
    ),
    // Naive draft: the file's first line, which is its heading.
    // Exercise: extract the "- Next best step: <text>" line's value.
    question(
      "where-are-we", "Where are we now?",
      rawFirstLine(join(repo, "claude-progress.md")),
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
