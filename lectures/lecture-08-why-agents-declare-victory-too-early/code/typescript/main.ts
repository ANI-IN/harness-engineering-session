// claim-gate: the scripted session that declares done, and the evidence
// gate that re-executes its claim.
//
// `session` is the premature declaration itself: a deterministic scripted
// session finishes its implementation steps with a 4-step check budget
// left, executes the checks it can afford (cheapest first, in declared
// order), predicts a pass for every check it cannot, and declares done.
// Everything it ran was green, so the claim is locally honest, and the
// session exits 0 because nothing inside the loop challenges the claim:
// the declaration sticks. `gate` replays that session to obtain the
// claim, then re-executes every claimed check against the workspace and
// reports claim vs check; any divergence is a premature declaration and
// exit 1. SPEC.md pins the check engine, the session policy, and the
// seeded gaps.

import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const CHECK_BUDGET = 4;

const IMPLEMENTATION_STEPS: [string, string][] = [
  ["implement the export writer", "src/export.txt updated"],
  ["add the export unit test", "tests/unit-export.txt updated"],
  ["wire the config read", "src/export.txt reads export_dir from config/app.conf"],
];

interface ValueSide {
  path: string;
  key: string;
}

interface Check {
  id: string;
  layer: string;
  cost: number;
  kind: string;
  path?: string;
  prefix?: string;
  marker?: string;
  left?: ValueSide;
  right?: ValueSide;
}

interface WorkspaceConfig {
  task: string;
  checks: Check[];
}

interface ClaimCheck {
  id: string;
  status: string;
  basis: string;
}

interface SessionEvent {
  step: number;
  action: string;
  outcome: string;
}

function fileExists(workspace: string, name: string): boolean {
  const path = join(workspace, name);
  return existsSync(path) && statSync(path).isFile();
}

function readLines(workspace: string, name: string): string[] {
  return readFileSync(join(workspace, name), "utf8").split(/\r?\n/);
}

function readKeyFromFile(workspace: string, path: string, key: string): string | null {
  for (const line of readLines(workspace, path)) {
    if (line.startsWith(`${key}=`)) return line.slice(key.length + 1).trim();
  }
  return null;
}

// The check engine: one executable probe per declared check. The
// deterministic stand-in for running the real command (the seam where a
// shell would sit); details name the exact evidence or the exact gap.
function executeCheck(workspace: string, check: Check): [boolean, string] {
  if (check.kind === "file-exists") {
    const path = check.path as string;
    if (fileExists(workspace, path)) return [true, `${path} present`];
    return [false, `${path} missing`];
  }
  if (check.kind === "file-has-line") {
    const path = check.path as string;
    const prefix = check.prefix as string;
    if (!fileExists(workspace, path)) return [false, `${path} missing`];
    if (readLines(workspace, path).some((line) => line.startsWith(prefix))) {
      return [true, `${path} has a line starting with ${prefix}`];
    }
    return [false, `${path} has no line starting with ${prefix}`];
  }
  if (check.kind === "file-lacks-marker") {
    const path = check.path as string;
    const marker = check.marker as string;
    if (!fileExists(workspace, path)) return [false, `${path} missing`];
    if (readFileSync(join(workspace, path), "utf8").includes(marker)) {
      return [false, `${path} contains ${marker}`];
    }
    return [true, `${path} carries no ${marker} marker`];
  }
  if (check.kind === "values-agree") {
    const left = check.left as ValueSide;
    const right = check.right as ValueSide;
    for (const side of [left, right]) {
      if (!fileExists(workspace, side.path)) return [false, `${side.path} missing`];
      if (readKeyFromFile(workspace, side.path, side.key) === null) {
        return [false, `${side.path} has no ${side.key}= line`];
      }
    }
    const leftValue = readKeyFromFile(workspace, left.path, left.key);
    const rightValue = readKeyFromFile(workspace, right.path, right.key);
    if (leftValue === rightValue) {
      return [
        true,
        `${left.path} ${left.key}=${leftValue} matches ${right.path} ${right.key}=${rightValue}`,
      ];
    }
    return [
      false,
      `${left.path} ${left.key}=${leftValue} but ${right.path} ${right.key}=${rightValue}`,
    ];
  }
  throw new Error(`unknown check kind: ${check.kind}`);
}

function loadDeclaredChecks(workspace: string): WorkspaceConfig {
  return JSON.parse(readFileSync(join(workspace, "checks.json"), "utf8")) as WorkspaceConfig;
}

function workspaceName(workspace: string): string {
  return workspace.replace(/\/+$/, "").split("/").pop() ?? workspace;
}

// The scripted session (SPEC.md, "The session"). It reaches the completion
// decision with CHECK_BUDGET steps left; a check it cannot afford is
// predicted to pass at zero cost, which is the premature declaration
// mechanism under study.
export function session(workspace: string) {
  const config = loadDeclaredChecks(workspace);
  const events: SessionEvent[] = [];
  let step = 0;

  const record = (action: string, outcome: string): void => {
    step += 1;
    events.push({ step, action, outcome });
  };

  for (const [action, outcome] of IMPLEMENTATION_STEPS) {
    record(action, outcome);
  }

  let remaining = CHECK_BUDGET;
  const claimChecks: ClaimCheck[] = [];
  let executed = 0;
  let predicted = 0;
  let allExecutedPassed = true;
  for (const check of config.checks) {
    if (check.cost <= remaining) {
      remaining -= check.cost;
      const [passed, detail] = executeCheck(workspace, check);
      executed += 1;
      const status = passed ? "pass" : "fail";
      allExecutedPassed = allExecutedPassed && passed;
      record(
        `run check ${check.id} (cost ${check.cost})`,
        `executed: ${status} (${detail}); budget left ${remaining}`,
      );
      claimChecks.push({ id: check.id, status, basis: "executed" });
    } else {
      predicted += 1;
      record(
        `consider check ${check.id} (cost ${check.cost})`,
        `cost exceeds budget left ${remaining}; predicted pass from the code just written`,
      );
      claimChecks.push({ id: check.id, status: "pass", basis: "predicted" });
    }
  }

  const done = allExecutedPassed;
  const green = claimChecks.filter((check) => check.status === "pass").length;
  if (done) {
    record(
      "declare done",
      `claim: ${green}/${claimChecks.length} checks green ` +
        `(${executed} executed, ${predicted} predicted)`,
    );
  } else {
    record("keep working", "an executed check failed; no completion claim");
  }

  return {
    workspace: workspaceName(workspace),
    task: config.task,
    check_budget: CHECK_BUDGET,
    events,
    claim: { done, checks: claimChecks, executed, predicted },
  };
}

// The evidence gate: replays the session to obtain the claim, then
// re-executes every claimed check. The report is claim vs check; the exit
// code is the verdict.
export function gate(workspace: string) {
  const config = loadDeclaredChecks(workspace);
  const claim = session(workspace).claim;
  const byId = new Map(config.checks.map((check) => [check.id, check]));
  const reexecution = [];
  let divergences = 0;
  for (const claimed of claim.checks) {
    const check = byId.get(claimed.id) as Check;
    const [passed, detail] = executeCheck(workspace, check);
    const actual = passed ? "pass" : "fail";
    const diverged = actual !== claimed.status;
    if (diverged) divergences += 1;
    reexecution.push({
      id: claimed.id,
      layer: check.layer,
      claimed: claimed.status,
      basis: claimed.basis,
      actual,
      detail,
      verdict: diverged ? "diverged" : "confirmed",
    });
  }
  const green = claim.checks.filter((check) => check.status === "pass").length;
  return {
    workspace: workspaceName(workspace),
    claim: {
      done: claim.done,
      green,
      executed: claim.executed,
      predicted: claim.predicted,
    },
    reexecution,
    verdict: {
      divergences,
      result: divergences === 0 ? "earned" : "premature",
    },
  };
}

function resolveWorkspace(arg: string): string | null {
  if (!existsSync(arg) || !statSync(arg).isDirectory()) {
    console.error(`error: not a directory: ${arg}`);
    return null;
  }
  if (!fileExists(arg, "checks.json")) {
    console.error(`error: not a workspace (no checks.json): ${arg}`);
    return null;
  }
  return arg;
}

function main(argv: readonly string[]): number {
  const command = argv[2];
  const target = argv[3];
  if (argv.length !== 4 || !target || (command !== "session" && command !== "gate")) {
    console.error("usage: main.ts session <workspace-dir> | main.ts gate <workspace-dir>");
    return 2;
  }
  const workspace = resolveWorkspace(target);
  if (workspace === null) return 2;
  if (command === "session") {
    const report = session(workspace);
    process.stdout.write(JSON.stringify(report, null, 2) + "\n");
    return report.claim.done ? 0 : 1;
  }
  const report = gate(workspace);
  if (!report.claim.done) {
    console.error("error: the scripted session declares no completion here; nothing to audit");
    return 2;
  }
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return report.verdict.result === "earned" ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
