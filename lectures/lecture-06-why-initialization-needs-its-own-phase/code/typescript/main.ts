// init-check: the startup-readiness doctor.
//
// Runs the four readiness checks a fresh session depends on, in order, and
// delivers a verdict: exit 0 when every later session can start from a
// known-good state, exit 1 when initialization still owes something. All
// checks are file-based and language-neutral; SPEC.md pins each rule and
// the seeded symptoms in the broken fixture.

import { accessSync, constants, existsSync, readFileSync, statSync } from "node:fs";
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
  const found: string[] = [];
  const missing: string[] = [];
  for (const [manifest, pin] of PAIRS) {
    if (fileExists(repo, manifest)) {
      if (fileExists(repo, pin)) found.push(`${manifest} + ${pin}`);
      else missing.push(`${manifest} present but ${pin} missing`);
    }
  }
  if (missing.length > 0) return [false, missing.join("; ")];
  if (found.length === 0) return [false, "no dependency manifest found"];
  return [true, found.join("; ")];
}

function checkInitScript(repo: string): CheckResult {
  const script = join(repo, "init.sh");
  if (!fileExists(repo, "init.sh")) return [false, "init.sh missing"];
  try {
    accessSync(script, constants.X_OK);
  } catch {
    return [false, "init.sh is not executable"];
  }
  if (!readFileSync(script, "utf8").includes("set -euo pipefail")) {
    return [false, "init.sh does not enable strict mode (set -euo pipefail)"];
  }
  return [true, "init.sh executable with strict mode"];
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
  if (!fileExists(repo, "claude-progress.md")) {
    return [false, "claude-progress.md missing"];
  }
  const text = readFileSync(join(repo, "claude-progress.md"), "utf8");
  if (!/^- Next best step: .+$/m.test(text)) {
    return [false, "claude-progress.md has no Next best step line"];
  }
  return [true, "claude-progress.md with a Next best step line"];
}

const CHECKS: [string, (repo: string) => CheckResult][] = [
  ["dependencies-pinned", checkDependenciesPinned],
  ["init-script", checkInitScript],
  ["verification-command", checkVerificationCommand],
  ["progress-artifact", checkProgressArtifact],
];

interface Check {
  id: string;
  passed: boolean;
  detail: string;
}

export function doctor(repo: string): { checks: Check[]; ready: boolean } {
  const checks = CHECKS.map(([id, run]) => {
    const [passed, detail] = run(repo);
    return { id, passed, detail };
  });
  return { checks, ready: checks.every((check) => check.passed) };
}

const STEP_BUDGET = 12;
const FEATURE_STEPS = 5;

// The scripted session (SPEC.md, "The replay"). Costs derive from the
// same four checks the doctor runs; nothing here re-inspects files.
export function replay(repo: string) {
  const verdict = new Map(doctor(repo).checks.map((check) => [check.id, check]));
  const events: Array<{ step: number; action: string; outcome: string }> = [];
  let remaining = STEP_BUDGET;

  const spend = (action: string, outcome: string): boolean => {
    if (remaining <= 0) {
      return false;
    }
    remaining -= 1;
    events.push({ step: STEP_BUDGET - remaining, action, outcome });
    return true;
  };

  let overhead = 0;
  if (verdict.get("progress-artifact")?.passed) {
    spend("read the progress log", "resume point found; no re-derivation");
  } else {
    spend("read the progress log", "missing; the session starts by guessing");
    spend("re-derive project state", "scan the repository structure");
    spend("re-derive project state", "reconstruct decisions already made once");
    overhead += 2;
  }
  if (verdict.get("dependencies-pinned")?.passed) {
    spend("install dependencies", "pinned interpreter; install clean");
  } else {
    spend("install dependencies", "wrong interpreter; ModuleNotFoundError mid-install");
    spend("pin and reinstall", "environment rebuilt by hand");
    overhead += 1;
  }
  const strictInit = verdict.get("init-script")?.passed ?? false;
  spend(
    "run init.sh",
    strictInit
      ? "environment verified strictly"
      : "exited 0 over a half-built environment (no strict mode)",
  );

  let completed = true;
  for (let step = 1; step <= FEATURE_STEPS; step += 1) {
    if (!spend(`feature step ${step}`, "progress on the export feature")) {
      completed = false;
      break;
    }
    if (step === 2 && !strictInit) {
      let ok = spend(
        "feature test fails mysteriously",
        "traced back to the half-built environment init.sh hid",
      );
      ok = ok && spend("rebuild the environment", "the loud failure init.sh owed us");
      overhead += 2;
      if (!ok) {
        completed = false;
        break;
      }
    }
  }

  let verified = false;
  if (completed) {
    if (verdict.get("verification-command")?.passed) {
      const command = verdict.get("verification-command")?.detail ?? "";
      verified = spend(`run the verification command (${command})`, "pass");
      completed = verified;
    } else {
      spend("claim done", "no verification command recorded; the claim is unbacked");
    }
  }

  return {
    repo: repo.replace(/\/+$/, "").split("/").pop() ?? repo,
    budget: STEP_BUDGET,
    events,
    steps_spent: STEP_BUDGET - remaining,
    setup_overhead: overhead,
    feature_completed: completed,
    verified,
  };
}

function main(argv: readonly string[]): number {
  if (argv.length === 4 && argv[2] === "replay") {
    const repo = argv[3] as string;
    if (!existsSync(repo) || !statSync(repo).isDirectory()) {
      console.error(`error: not a directory: ${repo}`);
      return 2;
    }
    const report = replay(repo);
    process.stdout.write(JSON.stringify(report, null, 2) + "\n");
    return report.feature_completed && report.verified ? 0 : 1;
  }
  const repo = argv[2];
  if (!repo || argv.length !== 3) {
    console.error("usage: main.ts <repo-dir> | main.ts replay <repo-dir>");
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
