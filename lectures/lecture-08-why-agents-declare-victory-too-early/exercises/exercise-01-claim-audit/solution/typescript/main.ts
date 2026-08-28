// claim-audit exercise, TypeScript solution.
//
// Audits a recorded completion claim against a workspace by re-executing
// every claimed check through the check engine, whatever the claim says
// about how the check was established. The recorded evidence string is
// input to the audit, never a substitute for it: the report's detail is
// always what re-execution said just now. SPEC.md pins the engine, the
// report shape, and the exit codes.

import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

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

interface ClaimCheck {
  id: string;
  status: string;
  basis: string;
  evidence: string;
}

interface Claim {
  done: boolean;
  checks: ClaimCheck[];
}

function fileExists(workspace: string, name: string): boolean {
  const path = join(workspace, name);
  return existsSync(path) && statSync(path).isFile();
}

function readLines(workspace: string, name: string): string[] {
  return readFileSync(join(workspace, name), "utf8").split(/\r?\n/);
}

function readKey(workspace: string, path: string, key: string): string | null {
  for (const line of readLines(workspace, path)) {
    if (line.startsWith(`${key}=`)) return line.slice(key.length + 1).trim();
  }
  return null;
}

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
      if (readKey(workspace, side.path, side.key) === null) {
        return [false, `${side.path} has no ${side.key}= line`];
      }
    }
    const leftValue = readKey(workspace, left.path, left.key);
    const rightValue = readKey(workspace, right.path, right.key);
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

export function audit(workspace: string, claim: Claim) {
  const config = JSON.parse(readFileSync(join(workspace, "checks.json"), "utf8")) as {
    checks: Check[];
  };
  const byId = new Map(config.checks.map((check) => [check.id, check]));
  const reexecution = [];
  let divergences = 0;
  for (const claimed of claim.checks) {
    const check = byId.get(claimed.id) as Check;
    // Every claimed check is re-executed, executed-basis rows included: a
    // recorded pass is a statement about the past, and the workspace may
    // have moved since.
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
  return {
    workspace: workspace.replace(/\/+$/, "").split("/").pop() ?? workspace,
    claim: {
      done: claim.done,
      green: claim.checks.filter((check) => check.status === "pass").length,
      executed: claim.checks.filter((check) => check.basis === "executed").length,
      predicted: claim.checks.filter((check) => check.basis === "predicted").length,
    },
    reexecution,
    verdict: {
      divergences,
      result: divergences === 0 ? "earned" : "premature",
    },
  };
}

function main(argv: readonly string[]): number {
  const workspace = argv[2];
  const claimPath = argv[3];
  if (argv.length !== 4 || !workspace || !claimPath) {
    console.error("usage: main.ts <workspace-dir> <claim-file>");
    return 2;
  }
  if (!existsSync(workspace) || !statSync(workspace).isDirectory() || !fileExists(workspace, "checks.json")) {
    console.error(`error: not a workspace (needs checks.json): ${workspace}`);
    return 2;
  }
  if (!existsSync(claimPath) || !statSync(claimPath).isFile()) {
    console.error(`error: no such claim file: ${claimPath}`);
    return 2;
  }
  const claim = JSON.parse(readFileSync(claimPath, "utf8")) as Claim;
  if (!claim.done) {
    console.error("error: the claim declares no completion; nothing to audit");
    return 2;
  }
  const report = audit(workspace, claim);
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return report.verdict.result === "earned" ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
