// trace-attribution: point each failing check at the recorded write that
// broke it.
//
// The workspace is a session's leavings and the trace is the event log that
// session's harness wrote. For every check that fails now, the audit finds
// the write that put the current value there and names the value it
// overwrote, which is the only thing a repair can be grounded in. A failing
// check whose key never appears in the trace is reported as unattributed:
// the log covered the wrong surface, and for this question that is the same
// as no log at all.

import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const INTEGER_RE = /^-?[0-9]+$/;

interface Check {
  id: string;
  path: string;
  key: string;
  rule: string;
}

interface WriteDetail {
  step: number;
  path: string;
  key: string;
  from: string;
  to: string;
}

interface LogEvent {
  seq: number;
  level: string;
  command: string;
  event: string;
  detail: Record<string, unknown>;
}

function isFile(path: string): boolean {
  return existsSync(path) && statSync(path).isFile();
}

function loadLines(workspace: string, relative: string): string[] | null {
  const path = join(workspace, relative);
  if (!isFile(path)) return null;
  return readFileSync(path, "utf8").split(/\r?\n/);
}

function readKey(lines: string[], key: string): string | null {
  for (const line of lines) {
    if (line.startsWith(`${key}=`)) return line.slice(key.length + 1).trim();
  }
  return null;
}

// One declared health check over the workspace as it is now.
function runCheck(workspace: string, check: Check): [boolean, string] {
  const { path, key, rule } = check;
  const lines = loadLines(workspace, path);
  if (lines === null) return [false, `${path} missing`];
  const value = readKey(lines, key);
  if (value === null) return [false, `${path} has no ${key}= line`];
  if (rule === "non-empty") {
    if (value) return [true, `${path} ${key}=${value} is set`];
    return [false, `${path} ${key} is empty`];
  }
  if (rule === "positive-integer") {
    if (INTEGER_RE.test(value) && Number.parseInt(value, 10) > 0) {
      return [true, `${path} ${key}=${value} is a positive integer`];
    }
    return [false, `${path} ${key}=${value} is not a positive integer`];
  }
  throw new Error(`unknown check rule: ${rule}`);
}

function loadTrace(trace: string): LogEvent[] {
  return readFileSync(trace, "utf8")
    .split(/\r?\n/)
    .filter((line) => line.trim() !== "")
    .map((line) => JSON.parse(line) as LogEvent);
}

// The last recorded write to this exact key in this exact file.
//
// Matching the file alone is not enough. A session touches one settings
// file many times, and the write that landed last is rarely the write that
// broke the check being diagnosed.
function attribute(events: LogEvent[], path: string, key: string): LogEvent | null {
  for (const event of [...events].reverse()) {
    if (event.event !== "workspace/write") continue;
    const detail = event.detail as unknown as WriteDetail;
    if (detail.path === path && detail.key === key) return event;
  }
  return null;
}

function baseName(path: string): string {
  return path.replace(/\/+$/, "").split("/").pop() ?? path;
}

export function audit(workspace: string, trace: string) {
  const checks = (
    JSON.parse(readFileSync(join(workspace, "checks.json"), "utf8")) as { checks: Check[] }
  ).checks;
  const events = loadTrace(trace);
  const diagnosis = [];
  let attributed = 0;
  for (const check of checks) {
    if (runCheck(workspace, check)[0]) continue;
    const { path, key } = check;
    const observed = readKey(loadLines(workspace, path) ?? [], key) ?? "";
    const found = attribute(events, path, key);
    let attribution: string;
    let repair: string;
    if (found === null) {
      attribution = `unattributed: the trace records no write to ${key} in ${path}`;
      repair = "none";
    } else {
      const detail = found.detail as unknown as WriteDetail;
      attribution =
        `event ${found.seq} recorded step ${detail.step} setting ` +
        `${detail.key} in ${detail.path} from ${detail.from} to ${detail.to}`;
      repair = `restore ${detail.key}=${detail.from} in ${detail.path}`;
      attributed += 1;
    }
    diagnosis.push({ check: check.id, path, key, observed, attribution, repair });
  }
  const unattributed = diagnosis.length - attributed;
  return {
    workspace: baseName(workspace),
    handoff: { trace: baseName(trace), events_read: events.length },
    diagnosis,
    outcome: {
      failing: diagnosis.length,
      attributed,
      unattributed,
      result: unattributed === 0 ? "located" : "blind",
    },
  };
}

function main(argv: readonly string[]): number {
  const workspace = argv[2];
  const trace = argv[3];
  if (argv.length !== 4 || !workspace || !trace) {
    console.error("usage: main.ts <workspace-dir> <trace-file>");
    return 2;
  }
  if (
    !existsSync(workspace) ||
    !statSync(workspace).isDirectory() ||
    !isFile(join(workspace, "checks.json"))
  ) {
    console.error(`error: not a workspace (no checks.json): ${workspace}`);
    return 2;
  }
  if (!isFile(trace)) {
    console.error(`error: not a trace file: ${trace}`);
    return 2;
  }
  const report = audit(workspace, trace);
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return report.outcome.result === "located" ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
