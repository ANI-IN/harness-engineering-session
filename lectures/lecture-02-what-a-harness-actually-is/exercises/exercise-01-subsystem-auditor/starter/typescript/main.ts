// subsystem-auditor exercise, TypeScript starter.
//
// Two of the five subsystem audits are implemented (instructions, feedback).
// Your task: implement auditTools, auditEnvironment, and auditState per
// SPEC.md. Run ../../verify.sh --stack=typescript until it exits 0.
// Everything outside those three functions already works.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const SUBSYSTEMS = ["instructions", "tools", "environment", "state", "feedback"] as const;

interface Finding {
  readonly present: boolean;
  readonly evidence: string | null;
}

function finding(present: boolean, evidence: string | null): Finding {
  return { present, evidence: present ? evidence : null };
}

function fileExists(repo: string, name: string): boolean {
  return existsSync(join(repo, name)) && statSync(join(repo, name)).isFile();
}

function auditInstructions(repo: string): Finding {
  for (const name of ["AGENTS.md", "CLAUDE.md"]) {
    if (fileExists(repo, name) && readFileSync(join(repo, name), "utf8").trim()) {
      return finding(true, name);
    }
  }
  return finding(false, null);
}

function auditTools(_repo: string): Finding {
  // Exercise: present when verify.sh exists in the repo; evidence "verify.sh".
  return finding(false, null);
}

function auditEnvironment(_repo: string): Finding {
  // Exercise: present when a manifest AND a runtime pin exist. Check the
  // Python pair (pyproject.toml + .python-version) first, then the Node
  // pair (package.json + .nvmrc); evidence is "<manifest> + <pin>".
  return finding(false, null);
}

function auditState(_repo: string): Finding {
  // Exercise: present only when BOTH feature_list.json and
  // claude-progress.md exist; evidence "feature_list.json + claude-progress.md".
  return finding(false, null);
}

function auditFeedback(repo: string): Finding {
  for (const name of ["AGENTS.md", "CLAUDE.md"]) {
    if (!fileExists(repo, name)) continue;
    const lines = readFileSync(join(repo, name), "utf8").split(/\r?\n/);
    if (lines.some((line) => line.trim().startsWith("- Verification:"))) {
      return finding(true, `Verification line in ${name}`);
    }
  }
  return finding(false, null);
}

const AUDITS: Record<string, (repo: string) => Finding> = {
  instructions: auditInstructions,
  tools: auditTools,
  environment: auditEnvironment,
  state: auditState,
  feedback: auditFeedback,
};

export function auditRepo(repo: string, name: string): Record<string, unknown> {
  const subsystems: Record<string, Finding> = {};
  for (const subsystem of SUBSYSTEMS) {
    const auditor = AUDITS[subsystem];
    if (auditor) subsystems[subsystem] = auditor(repo);
  }
  const missing = SUBSYSTEMS.filter((s) => !subsystems[s]?.present);
  const present = SUBSYSTEMS.length - missing.length;
  return {
    name,
    subsystems,
    score: `${present}/${SUBSYSTEMS.length}`,
    missing,
  };
}

function main(argv: readonly string[]): number {
  const reposDir = argv[2];
  if (!reposDir || argv.length !== 3) {
    console.error("usage: main.ts <repos-dir>");
    return 2;
  }
  if (!existsSync(reposDir) || !statSync(reposDir).isDirectory()) {
    console.error(`error: not a directory: ${reposDir}`);
    return 2;
  }
  const repos = readdirSync(reposDir)
    .filter((entry) => statSync(join(reposDir, entry)).isDirectory())
    .sort();
  const report = {
    repos: repos.map((name) => auditRepo(join(reposDir, name), name)),
    audited: repos.length,
  };
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return 0;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
