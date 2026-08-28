// resume-trace: one build session, one resume session, and the event log
// that decides whether the second one can finish the first one's work.
//
// `build` replays a deterministic scripted session over a workspace. It
// walks a plan, writes key/value settings, leaves a session note, and
// declares done. Under `--observability=structured` the harness also
// appends one structured event per write to `log/events.jsonl`; under
// `--observability=none` it does not. Nothing else about the session
// changes: same plan, same steps, same resulting files, same note.
//
// `resume` is the next session. It replays the build to obtain the
// workspace and the handoff artifacts the build left behind (never the
// build's report: stdout does not survive a session boundary), runs the
// workspace's declared checks, and for every failing check tries to
// attribute the write that broke it and restore the value that write
// overwrote. With the event log it can; without it the overwritten value
// exists nowhere and the repair is impossible, so the workspace stays
// broken and the exit code says so.
//
// All session writes land in an in-memory overlay of the workspace; the
// fixtures on disk are never modified. SPEC.md pins the plan format, the
// check rules, the event shape, and the resume procedure.

import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const INTEGER_RE = /^-?[0-9]+$/;
const SESSION_NOTE = "notes/session-note.md";
const EVENT_LOG = "log/events.jsonl";

interface PlanWrite {
  path: string;
  key: string;
  value: string;
}

interface PlanStep {
  action: string;
  write: PlanWrite;
}

interface Plan {
  task: string;
  steps: PlanStep[];
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

interface Artifacts {
  overlay: Overlay;
  files: string[];
  note: string[];
  log: string[];
  task: string;
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
// modified in memory. The seam where a real harness would write to disk.
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

// One declared health check. Rules are `non-empty` (the key carries a value)
// and `positive-integer` (the value parses as an integer above zero);
// details name the file, the key, and the observed value.
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

// What the session writes about itself. Prose, unstructured, and identical
// under both observability modes: the agent's self-report is the constant
// here, the harness's event log is the variable.
function sessionNote(task: string, steps: number): string[] {
  return [
    "# Session note",
    "",
    `Task: ${task}`,
    `Implemented the plan end to end; ${steps} steps completed.`,
    "No verification was run in this session.",
  ];
}

function workspaceName(workspace: string): string {
  return workspace.replace(/\/+$/, "").split("/").pop() ?? workspace;
}

function readJson(workspace: string, relative: string): unknown {
  return JSON.parse(readFileSync(join(workspace, relative), "utf8"));
}

// The first session. Returns its transcript (stdout, which ends with the
// session) and its artifacts (files, note, log: the only things the next
// session can read).
function runBuild(
  workspace: string,
  observability: string,
): [{ step: number; action: string; outcome: string }[], Artifacts] {
  const plan = readJson(workspace, "plan.json") as Plan;
  const overlay = new Overlay(workspace);
  const events: LogEvent[] = [];
  const transcript: { step: number; action: string; outcome: string }[] = [];

  const emit = (event: string, detail: Record<string, unknown>): void => {
    if (observability !== "structured") return;
    events.push({
      seq: events.length + 1,
      level: "INFO",
      command: "build",
      event,
      detail,
    });
  };

  emit("session/start", { task: plan.task });
  plan.steps.forEach((step, index) => {
    const { path, key, value } = step.write;
    const before = overlay.get(path, key) ?? "";
    overlay.set(path, key, value);
    emit("workspace/write", { step: index + 1, path, key, from: before, to: value });
    transcript.push({
      step: index + 1,
      action: step.action,
      outcome: `${path} ${key}=${value} (was ${before || "unset"})`,
    });
  });
  emit("session/end", { steps: plan.steps.length, declared: "done" });

  const files = [SESSION_NOTE, ...(observability === "structured" ? [EVENT_LOG] : [])];
  files.sort();
  const artifacts: Artifacts = {
    overlay,
    files,
    note: sessionNote(plan.task, plan.steps.length),
    log: events.map((event) => JSON.stringify(event)),
    task: plan.task,
  };
  return [transcript, artifacts];
}

export function buildReport(workspace: string, observability: string) {
  const [transcript, artifacts] = runBuild(workspace, observability);
  return {
    workspace: workspaceName(workspace),
    observability,
    task: artifacts.task,
    transcript,
    handoff: {
      files: artifacts.files,
      session_note: artifacts.note,
      events: artifacts.log.map((line) => JSON.parse(line) as LogEvent),
    },
    declared: "done",
  };
}

// The last recorded write to this exact key in this exact file. Scanning the
// file alone is not enough: a later write to a different key in the same
// file is not what broke this check.
function attribute(events: LogEvent[], path: string, key: string): LogEvent | null {
  for (const event of [...events].reverse()) {
    if (event.event !== "workspace/write") continue;
    const detail = event.detail as unknown as WriteDetail;
    if (detail.path === path && detail.key === key) return event;
  }
  return null;
}

// The second session. It receives the build's artifacts and nothing else,
// diagnoses every failing check, and repairs what it can attribute.
export function resumeReport(workspace: string, observability: string) {
  const [, artifacts] = runBuild(workspace, observability);
  const overlay = artifacts.overlay;
  const events = artifacts.log.map((line) => JSON.parse(line) as LogEvent);
  const checks = (readJson(workspace, "checks.json") as { checks: Check[] }).checks;

  const failing = checks.filter((check) => !runCheck(overlay, check)[0]);
  const diagnosis = [];
  let repaired = 0;
  for (const check of failing) {
    const { path, key } = check;
    const observed = overlay.get(path, key) ?? "";
    const found = attribute(events, path, key);
    let attribution: string;
    let repair: string;
    if (found === null) {
      attribution = `unattributed: the handoff records no write to ${key} in ${path}`;
      repair = "none";
    } else {
      const detail = found.detail as unknown as WriteDetail;
      attribution =
        `event ${found.seq} recorded step ${detail.step} setting ` +
        `${detail.key} in ${detail.path} from ${detail.from} to ${detail.to}`;
      repair = `restore ${detail.key}=${detail.from} in ${detail.path}`;
      overlay.set(path, key, detail.from);
      repaired += 1;
    }
    diagnosis.push({ check: check.id, path, key, observed, attribution, repair });
  }

  const recheck = [];
  let failingAfter = 0;
  for (const check of checks) {
    const [passed, detail] = runCheck(overlay, check);
    if (!passed) failingAfter += 1;
    recheck.push({ id: check.id, status: passed ? "pass" : "fail", detail });
  }

  return {
    workspace: workspaceName(workspace),
    observability,
    handoff: { files: artifacts.files, events_read: events.length },
    diagnosis,
    recheck,
    outcome: {
      failing_before: failing.length,
      repaired,
      failing_after: failingAfter,
      result: failingAfter === 0 ? "resumed" : "stuck",
    },
  };
}

function resolveWorkspace(arg: string): string | null {
  if (!existsSync(arg) || !statSync(arg).isDirectory()) {
    console.error(`error: not a directory: ${arg}`);
    return null;
  }
  for (const required of ["plan.json", "checks.json"]) {
    if (!isFile(join(arg, required))) {
      console.error(`error: not a workspace (no ${required}): ${arg}`);
      return null;
    }
  }
  return arg;
}

function main(argv: readonly string[]): number {
  const usage = "usage: main.ts build|resume <workspace-dir> --observability=structured|none";
  const command = argv[2];
  const target = argv[3];
  const flag = argv[4];
  if (argv.length !== 5 || !target || (command !== "build" && command !== "resume")) {
    console.error(usage);
    return 2;
  }
  if (flag !== "--observability=structured" && flag !== "--observability=none") {
    console.error(usage);
    return 2;
  }
  const observability = flag === "--observability=structured" ? "structured" : "none";
  const workspace = resolveWorkspace(target);
  if (workspace === null) return 2;
  if (command === "build") {
    process.stdout.write(JSON.stringify(buildReport(workspace, observability), null, 2) + "\n");
    return 0;
  }
  const report = resumeReport(workspace, observability);
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return report.outcome.result === "resumed" ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
