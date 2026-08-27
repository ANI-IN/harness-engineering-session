// verification-gap exercise, TypeScript starter.
//
// The report plumbing works; the classification logic does not. Your task:
// in classify(), decide whether a run's FIRST claim was backed by an
// earlier passing verification, per ../../SPEC.md. Run
// ../../verify.sh --stack=typescript until it exits 0. You should not need
// to change anything else.

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

interface RunEvent {
  readonly run: string;
  readonly type: string;
  readonly detail: string;
  readonly result?: string;
}

interface RunClassification {
  readonly claimed: boolean;
  readonly verified_before_claim: boolean;
  readonly classification: "verified-done" | "unverified-done" | "no-claim";
}

export function classify(events: readonly RunEvent[]): RunClassification {
  const firstClaimIndex = events.findIndex((e) => e.type === "claim");
  if (firstClaimIndex === -1) {
    return { claimed: false, verified_before_claim: false, classification: "no-claim" };
  }
  // Exercise: a claim counts as verified only when an earlier event
  // (index < firstClaimIndex) is a verification with result "pass".
  // Compute that, set verified_before_claim, and pick the classification:
  // "verified-done" when backed, "unverified-done" when not.
  return {
    claimed: true,
    verified_before_claim: false,
    classification: "unverified-done",
  };
}

export function gapReport(events: readonly RunEvent[]): Record<string, unknown> {
  const order: string[] = [];
  const runs = new Map<string, RunEvent[]>();
  for (const event of events) {
    let entry = runs.get(event.run);
    if (!entry) {
      entry = [];
      runs.set(event.run, entry);
      order.push(event.run);
    }
    entry.push(event);
  }

  const reportRuns = [];
  let claims = 0;
  let verifiedClaims = 0;
  for (const runId of order) {
    const result = classify(runs.get(runId) ?? []);
    reportRuns.push({ id: runId, ...result });
    if (result.claimed) {
      claims += 1;
      if (result.verified_before_claim) verifiedClaims += 1;
    }
  }

  const unverified = claims - verifiedClaims;
  return {
    runs: reportRuns,
    claims,
    verified_claims: verifiedClaims,
    unverified_claims: unverified,
    verification_gap: claims > 0 ? unverified / claims : 0,
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
  process.stdout.write(JSON.stringify(gapReport(events), null, 2) + "\n");
  return 0;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
