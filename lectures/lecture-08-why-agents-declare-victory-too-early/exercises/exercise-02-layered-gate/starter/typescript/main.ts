// layered-gate exercise, TypeScript starter.
//
// The gate runs every declared check, groups the results into the three
// layers, and names the first failing layer in its verdict, but one naive
// decision remains (see SPEC.md "Starter state"): layers below a failing
// one are still executed and reported as if they meant something. Make
// the gate stop at the first failing layer, reporting later checks as
// not-reached, then run ../../verify.sh --stack=typescript until it
// exits 0.

import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const LAYERS = ["static", "tests", "system"];

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

interface Row {
  id: string;
  status: string;
  detail: string;
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

export function runLayers(workspace: string) {
  const config = JSON.parse(readFileSync(join(workspace, "checks.json"), "utf8")) as {
    checks: Check[];
  };
  const layers = [];
  let stoppedAt: string | null = null;
  for (const layer of LAYERS) {
    const declared = config.checks.filter((check) => check.layer === layer);
    // Naive draft: run every layer so the report is complete, and let the
    // verdict name where a stricter gate would have stopped. Exercise:
    // once a layer fails, later layers must not execute; report their
    // checks as not-reached, gated by the failing layer.
    const rows: Row[] = declared.map((check) => {
      const [passed, detail] = executeCheck(workspace, check);
      return { id: check.id, status: passed ? "pass" : "fail", detail };
    });
    const status = rows.every((row) => row.status === "pass") ? "passed" : "failed";
    if (status === "failed" && stoppedAt === null) stoppedAt = layer;
    layers.push({ layer, status, checks: rows });
  }
  return {
    workspace: workspace.replace(/\/+$/, "").split("/").pop() ?? workspace,
    layers,
    verdict: {
      stopped_at: stoppedAt,
      result: stoppedAt === null ? "done" : "not-done",
    },
  };
}

function main(argv: readonly string[]): number {
  const workspace = argv[2];
  if (argv.length !== 3 || !workspace) {
    console.error("usage: main.ts <workspace-dir>");
    return 2;
  }
  if (!existsSync(workspace) || !statSync(workspace).isDirectory() || !fileExists(workspace, "checks.json")) {
    console.error(`error: not a workspace (needs checks.json): ${workspace}`);
    return 2;
  }
  const report = runLayers(workspace);
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return report.verdict.result === "done" ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
