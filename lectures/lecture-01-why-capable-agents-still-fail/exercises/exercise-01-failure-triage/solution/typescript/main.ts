// failure-triage exercise, TypeScript solution.
//
// All five attribution rules implemented. Each rule inspects one event (plus
// the events before it in the same run) and returns {subsystem, rule} or
// null; the first event matching any rule attributes the run. Rule semantics
// and precedence are pinned by ../../SPEC.md.

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

interface RunEvent {
  readonly run: string;
  readonly type: string;
  readonly detail: string;
  readonly result?: string;
}

const SUBSYSTEMS = ["instructions", "tools", "environment", "state", "feedback"] as const;
// Signals match whole words: a bare substring test reads `version` inside
// `conversion` and `subversion`.
const TOOL_SIGNALS = [/\bcommand not found\b/, /\bpermission denied\b/];
const ENVIRONMENT_SIGNALS = [
  /\bModuleNotFoundError\b/,
  /\bCannot find module\b/,
  /\bversion\b/,
];

export function attributeEvent(
  event: RunEvent,
  prior: readonly RunEvent[],
): { subsystem: string; rule: string } | null {
  if (event.type === "agent_question") {
    return { subsystem: "instructions", rule: "asked-for-repo-fact" };
  }
  if (event.type === "shell_error" && TOOL_SIGNALS.some((s) => s.test(event.detail))) {
    return { subsystem: "tools", rule: "command-unavailable" };
  }
  if (event.type === "shell_error" && ENVIRONMENT_SIGNALS.some((s) => s.test(event.detail))) {
    return { subsystem: "environment", rule: "dependency-or-runtime-missing" };
  }
  if (event.type === "rework") {
    return { subsystem: "state", rule: "repeated-prior-work" };
  }
  if (
    event.type === "claim" &&
    !prior.some((p) => p.type === "verification" && p.result === "pass")
  ) {
    return { subsystem: "feedback", rule: "claim-without-passing-verification" };
  }
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
