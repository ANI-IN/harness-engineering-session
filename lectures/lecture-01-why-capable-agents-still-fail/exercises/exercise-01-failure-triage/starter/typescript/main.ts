// failure-triage exercise, TypeScript starter.
//
// Two of the five attribution rules are implemented (instructions, tools).
// Your task: implement the remaining three in attributeEvent, exactly as
// ../../SPEC.md defines them:
//
//   environment  "dependency-or-runtime-missing"
//   state        "repeated-prior-work"
//   feedback     "claim-without-passing-verification"
//
// Run ../../verify.sh --stack=typescript until it exits 0. Everything
// outside attributeEvent already works; you should not need to change it.

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

interface RunEvent {
  readonly run: string;
  readonly type: string;
  readonly detail: string;
  readonly result?: string;
}

const SUBSYSTEMS = ["instructions", "tools", "environment", "state", "feedback"] as const;
const TOOL_SIGNALS = ["command not found", "permission denied"];
export const ENVIRONMENT_SIGNALS = ["ModuleNotFoundError", "Cannot find module", "version"];

export function attributeEvent(
  event: RunEvent,
  _prior: readonly RunEvent[],
): { subsystem: string; rule: string } | null {
  if (event.type === "agent_question") {
    return { subsystem: "instructions", rule: "asked-for-repo-fact" };
  }
  if (event.type === "shell_error" && TOOL_SIGNALS.some((s) => event.detail.includes(s))) {
    return { subsystem: "tools", rule: "command-unavailable" };
  }
  // Exercise: rule "dependency-or-runtime-missing" (environment).
  //   A shell_error whose detail contains one of ENVIRONMENT_SIGNALS.
  // Exercise: rule "repeated-prior-work" (state).
  //   Any rework event.
  // Exercise: rule "claim-without-passing-verification" (feedback).
  //   A claim event with no earlier verification event whose result is
  //   "pass" in the same run; `_prior` holds the earlier events.
  return null;
}

export function triage(events: readonly RunEvent[]): Record<string, unknown> {
  const order: string[] = [];
  const runs = new Map<string, { task: string | null; events: RunEvent[] }>();
  for (const event of events) {
    let entry = runs.get(event.run);
    if (!entry) {
      entry = { task: null, events: [] };
      runs.set(event.run, entry);
      order.push(event.run);
    }
    if (event.type === "task" && entry.task === null) entry.task = event.detail;
    entry.events.push(event);
  }

  const summary: Record<string, number> = { unattributed: 0 };
  for (const subsystem of SUBSYSTEMS) summary[subsystem] = 0;
  const reportRuns = [];

  for (const runId of order) {
    const entry = runs.get(runId);
    if (!entry) continue;
    let found: { subsystem: string; rule: string; event: RunEvent } | null = null;
    for (let index = 0; index < entry.events.length; index += 1) {
      const event = entry.events[index];
      if (!event) continue;
      const match = attributeEvent(event, entry.events.slice(0, index));
      if (match) {
        found = { ...match, event };
        break;
      }
    }
    const subsystem = found ? found.subsystem : "unattributed";
    summary[subsystem] = (summary[subsystem] ?? 0) + 1;
    reportRuns.push({
      id: runId,
      task: entry.task,
      subsystem,
      rule: found ? found.rule : null,
      evidence: found ? `${found.event.type}: "${found.event.detail}"` : null,
    });
  }

  const total = order.length;
  const failures = total - (summary.unattributed ?? 0);
  return {
    runs: reportRuns,
    summary,
    total_runs: total,
    harness_failure_rate: total > 0 ? failures / total : 0,
  };
}

export function parseTranscript(text: string): RunEvent[] {
  const events: RunEvent[] = [];
  const lines = text.split(/\r?\n/);
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (!line || !line.trim()) continue;
    let event: RunEvent;
    try {
      event = JSON.parse(line) as RunEvent;
    } catch (error) {
      throw new Error(`malformed transcript at line ${index + 1}: ${String(error)}`, {
        cause: error,
      });
    }
    for (const field of ["run", "type", "detail"] as const) {
      if (!(field in event)) {
        throw new Error(`malformed transcript at line ${index + 1}: missing '${field}'`);
      }
    }
    events.push(event);
  }
  return events;
}

function main(argv: readonly string[]): number {
  const path = argv[2];
  if (!path || argv.length !== 3) {
    console.error("usage: main.ts <transcript.jsonl>");
    return 2;
  }
  let text: string;
  try {
    text = readFileSync(path, "utf8");
  } catch (error) {
    console.error(`error: cannot read transcript: ${String(error)}`);
    return 2;
  }
  let events: RunEvent[];
  try {
    events = parseTranscript(text);
  } catch (error) {
    console.error(`error: ${error instanceof Error ? error.message : String(error)}`);
    return 1;
  }
  process.stdout.write(JSON.stringify(triage(events), null, 2) + "\n");
  return 0;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
