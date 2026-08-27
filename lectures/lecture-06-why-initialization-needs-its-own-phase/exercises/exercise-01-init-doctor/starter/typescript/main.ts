// init-doctor exercise, TypeScript starter.
//
// All four checks run, but three are naive first drafts that stop at
// existence (see SPEC.md "Starter state"): dependencies-pinned accepts a
// manifest without its runtime pin, init-script accepts any init.sh file,
// and progress-artifact accepts any progress file. Fix the three per
// SPEC.md; verification-command is already correct. Run
// ../../verify.sh --stack=typescript until it exits 0.

import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const PAIRS: [string, string][] = [
  ["pyproject.toml", ".python-version"],
  ["package.json", ".nvmrc"],
];

type CheckResult = [boolean, string];

function fileExists(repo: string, name: string): boolean {
  return existsSync(join(repo, name)) && statSync(join(repo, name)).isFile();
}

function checkDependenciesPinned(repo: string): CheckResult {
  // Naive draft: a manifest without its runtime pin reproduces the
  // dependency tree on the wrong interpreter. Exercise: every manifest
  // present must have its pin; detail names pairs or the missing pin.
  const found = PAIRS.filter(([manifest]) => fileExists(repo, manifest)).map(
    ([manifest]) => manifest,
  );
  if (found.length === 0) return [false, "no dependency manifest found"];
  return [true, found.join("; ")];
}

function checkInitScript(repo: string): CheckResult {
  // Naive draft: a file named init.sh is not a working init phase.
  // Exercise: it must also be executable and enable strict mode
  // (set -euo pipefail); detail names whichever property is missing.
  if (fileExists(repo, "init.sh")) return [true, "init.sh present"];
  return [false, "init.sh missing"];
}

function checkVerificationCommand(repo: string): CheckResult {
  for (const name of ["AGENTS.md", "CLAUDE.md"]) {
    if (!fileExists(repo, name)) continue;
    const match = readFileSync(join(repo, name), "utf8").match(/^- Verification: (.+)$/m);
    if (match && match[1]) return [true, `${name}: ${match[1].trim()}`];
  }
  return [false, "no Verification line in AGENTS.md or CLAUDE.md"];
}

function checkProgressArtifact(repo: string): CheckResult {
  // Naive draft: a progress file without a Next best step line leaves the
  // next session guessing anyway. Exercise: require the tagged line.
  if (fileExists(repo, "claude-progress.md")) {
    return [true, "claude-progress.md present"];
  }
  return [false, "claude-progress.md missing"];
}

const CHECKS: [string, (repo: string) => CheckResult][] = [
  ["dependencies-pinned", checkDependenciesPinned],
  ["init-script", checkInitScript],
  ["verification-command", checkVerificationCommand],
  ["progress-artifact", checkProgressArtifact],
];

export function doctor(repo: string): { checks: object[]; ready: boolean } {
  const checks = CHECKS.map(([id, run]) => {
    const [passed, detail] = run(repo);
    return { id, passed, detail };
  });
  return { checks, ready: checks.every((check) => check.passed) };
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
  const report = doctor(repo);
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return report.ready ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
