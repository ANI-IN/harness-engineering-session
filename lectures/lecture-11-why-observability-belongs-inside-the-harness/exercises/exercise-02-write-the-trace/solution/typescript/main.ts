// write-the-trace: the harness side of observability.
//
// The session writes settings into an in-memory overlay of the workspace
// and the harness records one `workspace/write` event per change. The
// event's `from` is what makes the log worth keeping: it is the only place
// the overwritten value survives, so it has to be the value the session was
// holding at that moment, not the value the file started the session with.
//
// The second half of the program is the consumer, complete and unchanged:
// it runs the workspace's declared checks against the finished overlay and
// attributes each failure to the last recorded write to that key. A log
// with the wrong `from` still attributes, and still proposes a repair; the
// repair just restores the wrong value.

import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const INTEGER_RE = /^-?[0-9]+$/;

interface PlanWrite {
  path: string;
  key: string;
  value: string;
}

interface Plan {
  task: string;
  steps: { action: string; write: PlanWrite }[];
}

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

function writeKey(lines: string[], key: string, value: string): void {
  const index = lines.findIndex((line) => line.startsWith(`${key}=`));
  if (index >= 0) {
    lines[index] = `${key}=${value}`;
    return;
  }
  lines.push(`${key}=${value}`);
}

// The workspace as the session sees it: files loaded on first touch and
// modified in memory until the session ends.
class Overlay {
  private readonly files = new Map<string, string[]>();

  constructor(private readonly workspace: string) {}

  lines(relative: string): string[] | null {
    if (!this.files.has(relative)) {
      const loaded = loadLines(this.workspace, relative);
      if (loaded === null) return null;
      this.files.set(relative, loaded);
    }
    return this.files.get(relative) as string[];
  }

  get(relative: string, key: string): string | null {
    const lines = this.lines(relative);
    return lines === null ? null : readKey(lines, key);
  }

  set(relative: string, key: string, value: string): void {
    if (this.lines(relative) === null) this.files.set(relative, []);
    writeKey(this.files.get(relative) as string[], key, value);
  }
}

function runCheck(overlay: Overlay, check: Check): [boolean, string] {
  const { path, key, rule } = check;
  const lines = overlay.lines(path);
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

function workspaceName(workspace: string): string {
  return workspace.replace(/\/+$/, "").split("/").pop() ?? workspace;
}

function readJson(workspace: string, relative: string): unknown {
  return JSON.parse(readFileSync(join(workspace, relative), "utf8"));
}

// Replay the plan and record the trace as the harness would.
function runSession(workspace: string): [LogEvent[], Overlay] {
  const plan = readJson(workspace, "plan.json") as Plan;
  const overlay = new Overlay(workspace);
  const events: LogEvent[] = [];

  const emit = (event: string, detail: Record<string, unknown>): void => {
    events.push({ seq: events.length + 1, level: "INFO", command: "build", event, detail });
  };

  emit("session/start", { task: plan.task });
  plan.steps.forEach((step, index) => {
    const { path, key, value } = step.write;
    const before = overlay.get(path, key) ?? "";
    overlay.set(path, key, value);
    emit("workspace/write", { step: index + 1, path, key, from: before, to: value });
  });
  emit("session/end", { steps: plan.steps.length, declared: "done" });
  return [events, overlay];
}

// The last recorded write to this exact key in this exact file.
function attribute(events: LogEvent[], path: string, key: string): LogEvent | null {
  for (const event of [...events].reverse()) {
    if (event.event !== "workspace/write") continue;
    const detail = event.detail as unknown as WriteDetail;
    if (detail.path === path && detail.key === key) return event;
  }
  return null;
}

export function report(workspace: string) {
  const [events, overlay] = runSession(workspace);
  const checks = (readJson(workspace, "checks.json") as { checks: Check[] }).checks;
  const repairPlan = [];
  let attributed = 0;
  for (const check of checks) {
    const [passed, failure] = runCheck(overlay, check);
    if (passed) continue;
    const { path, key } = check;
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
    repairPlan.push({ check: check.id, failure, attribution, repair });
  }
  const unattributed = repairPlan.length - attributed;
  return {
    workspace: workspaceName(workspace),
    events,
    repair_plan: repairPlan,
    outcome: {
      failing: repairPlan.length,
      attributed,
      unattributed,
      result: unattributed === 0 ? "located" : "blind",
    },
  };
}

function main(argv: readonly string[]): number {
  const workspace = argv[2];
  if (argv.length !== 3 || !workspace) {
    console.error("usage: main.ts <workspace-dir>");
    return 2;
  }
  if (!existsSync(workspace) || !statSync(workspace).isDirectory()) {
    console.error(`error: not a directory: ${workspace}`);
    return 2;
  }
  for (const required of ["plan.json", "checks.json"]) {
    if (!isFile(join(workspace, required))) {
      console.error(`error: not a workspace (no ${required}): ${workspace}`);
      return 2;
    }
  }
  const result = report(workspace);
  process.stdout.write(JSON.stringify(result, null, 2) + "\n");
  return result.outcome.result === "located" ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
