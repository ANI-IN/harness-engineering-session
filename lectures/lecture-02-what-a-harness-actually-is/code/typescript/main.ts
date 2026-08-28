// minimal-harness-loop: one deterministic loop iteration through the five
// subsystems, with single-subsystem ablation.
//
// The harness artifacts live in the workspace directory as ordinary files
// (AGENTS.md, feature_list.json, tools.json, environment.json, clock.json).
// They are language-neutral: the Python track reads the same bytes and must
// produce the same report. `--disable=<subsystem>` removes exactly one
// subsystem and the run degrades in that subsystem's characteristic way.

import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const SUBSYSTEMS = ["instructions", "state", "environment", "tools", "feedback"] as const;
type Subsystem = (typeof SUBSYSTEMS)[number];
const ISO_RE = /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z/;
const US_RE = /\d{2}\/\d{2}\/\d{4}/;

// The convention the workspace declares decides both how a date is rendered
// and what the check accepts. Nothing here may hardcode one of them: if the
// instruction file says MM/DD/YYYY, an agent that writes ISO is wrong, and
// the check has to say so. That is what makes the instructions subsystem
// load-bearing rather than decorative.
interface Convention {
  readonly label: string;
  readonly matches: RegExp;
  readonly validator: RegExp;
  readonly iso: boolean;
}
const CONVENTIONS: readonly Convention[] = [
  { label: "ISO 8601 UTC", matches: /ISO\s*8601/i, validator: ISO_RE, iso: true },
  { label: "MM/DD/YYYY", matches: /MM\/DD\/YYYY|US short/i, validator: US_RE, iso: false },
];

interface Feature {
  readonly id: string;
  readonly status: string;
  readonly depends_on?: readonly string[];
}

interface Step {
  readonly subsystem: string;
  readonly ok: boolean;
  readonly note: string;
}

function load<T>(workspace: string, name: string): T {
  return JSON.parse(readFileSync(join(workspace, name), "utf8")) as T;
}

export function nextFeature(featureList: { features: readonly Feature[] }): string {
  const statuses = new Map(featureList.features.map((f) => [f.id, f.status]));
  for (const feature of featureList.features) {
    if (feature.status !== "not-started") continue;
    const deps = feature.depends_on ?? [];
    if (deps.every((dep) => statuses.get(dep) === "passing")) return feature.id;
  }
  const first = featureList.features[0];
  return first ? first.id : "";
}

export function guessedDate(todayIso: string): string {
  const [year, month, day] = todayIso.slice(0, 10).split("-");
  return `${month}/${day}/${year}`;
}

/** The convention this workspace requires, read from the instruction file. */
export function declaredConvention(
  workspace: string,
): { convention: Convention; declared: string } | null {
  const path = join(workspace, "AGENTS.md");
  if (!existsSync(path) || !statSync(path).isFile()) return null;
  const match = readFileSync(path, "utf8").match(/^- Convention: (.+)$/m);
  if (!match || match[1] === undefined) return null;
  const declared = match[1].trim();
  const convention = CONVENTIONS.find((entry) => entry.matches.test(declared));
  return convention ? { convention, declared } : null;
}

export function runLoop(workspace: string, disabled: Subsystem | null): Record<string, unknown> {
  const today = load<{ today: string }>(workspace, "clock.json").today;
  const steps: Step[] = [];

  // What the workspace requires. The checker reads this whether or not the
  // agent did, which is the whole point of a separate feedback subsystem.
  const required = declaredConvention(workspace);

  // 1. instructions: the convention comes from AGENTS.md, or gets guessed.
  let convention: string;
  let rendered: string;
  if (disabled === "instructions" || required === null) {
    convention = "MM/DD/YYYY (guessed)";
    rendered = guessedDate(today);
    steps.push({
      subsystem: "instructions", ok: false,
      note: "disabled: no AGENTS.md; guessing convention MM/DD/YYYY",
    });
  } else {
    convention = required.convention.label;
    rendered = required.convention.iso ? today : guessedDate(today);
    steps.push({
      subsystem: "instructions", ok: true,
      note: `read convention from AGENTS.md: ${required.declared}`,
    });
  }

  // 2. state: pick the next feature from feature_list.json, or start over.
  let feature: string;
  if (disabled === "state") {
    feature = "stamp-header";
    steps.push({
      subsystem: "state", ok: false,
      note: "disabled: no feature list; starting from stamp-header",
    });
  } else {
    feature = nextFeature(load(workspace, "feature_list.json"));
    steps.push({
      subsystem: "state", ok: true,
      note: `feature_list.json: next feature is ${feature}`,
    });
  }

  // 3. environment: the formatter dependency must be present to render.
  const envOk =
    disabled !== "environment" &&
    load<{ dependencies: Record<string, string> }>(workspace, "environment.json")
      .dependencies["formatter"] === "installed";
  steps.push({
    subsystem: "environment", ok: envOk,
    note: envOk ? "formatter dependency installed" : "disabled: formatter unavailable",
  });

  // 4. tools: writing the artifact needs the write_file tool.
  const toolsOk =
    disabled !== "tools" &&
    load<{ allowed: string[] }>(workspace, "tools.json").allowed.includes("write_file");
  const written = envOk && toolsOk;
  let toolsNote: string;
  if (!toolsOk) toolsNote = "disabled: write_file not permitted";
  else if (!envOk) toolsNote = "skipped: nothing to write (environment failure)";
  else toolsNote = "write_file: artifact written";
  steps.push({ subsystem: "tools", ok: toolsOk && envOk, note: toolsNote });

  const content = written
    ? feature === "format-dates"
      ? `date: ${rendered}`
      : `header: notes v1 (${rendered})`
    : null;

  // 5. feedback: run the check, unless disabled or there is nothing to check.
  let checkRan = false;
  let checkPassed = false;
  let feedbackOk: boolean;
  let feedbackNote: string;
  if (disabled === "feedback") {
    feedbackOk = false;
    feedbackNote = "disabled: completion claimed without running the check";
  } else if (!written) {
    feedbackOk = false;
    feedbackNote = "skipped: no artifact to check";
  } else {
    checkRan = true;
    checkPassed = (required ? required.convention.validator : ISO_RE).test(content ?? "");
    feedbackOk = true;
    feedbackNote = checkPassed
      ? "run_check date-format: pass"
      : "run_check date-format: FAIL (convention violation caught)";
  }
  steps.push({ subsystem: "feedback", ok: feedbackOk, note: feedbackNote });

  // Outcome and issues.
  let outcome: string;
  let issues: string[];
  if (disabled === "tools" || (!written && disabled !== "environment")) {
    outcome = "blocked";
    issues = ["write_file not permitted; work product could not be written"];
  } else if (disabled === "environment") {
    outcome = "error";
    issues = ["formatter dependency unavailable; date rendering failed"];
  } else if (disabled === "feedback") {
    outcome = "claimed-unverified";
    issues = ["completion claimed without running run_check date-format"];
  } else if (checkRan && !checkPassed) {
    outcome = "failed-verification";
    issues = [
      `convention violation: wrote ${rendered} where ` +
        `${required ? required.convention.label : "ISO 8601 UTC"} is ` +
        "required (caught by run_check)",
    ];
  } else if (feature !== "format-dates") {
    outcome = "completed-redundant";
    issues = [
      "re-implemented stamp-header, already passing in feature_list.json; " +
        "format-dates remains not-started",
    ];
  } else {
    outcome = "completed-verified";
    issues = [];
  }

  return {
    disabled,
    feature,
    convention,
    steps,
    artifact: { written, content },
    outcome,
    issues,
  };
}

export function ablationTable(workspace: string): string {
  const lines = ["disabled | outcome | issues"];
  for (const disabled of [null, ...SUBSYSTEMS] as (Subsystem | null)[]) {
    const report = runLoop(workspace, disabled);
    const label = disabled ?? "(none)";
    const issues = report.issues as string[];
    lines.push(`${label} | ${report.outcome} | ${issues.length}`);
  }
  return lines.join("\n");
}

function main(argv: readonly string[]): number {
  const args = argv.slice(2);
  let disabled: Subsystem | null = null;
  let table = false;
  const positional: string[] = [];
  for (const arg of args) {
    if (arg.startsWith("--disable=")) {
      const name = arg.split("=", 2)[1] ?? "";
      if (!(SUBSYSTEMS as readonly string[]).includes(name)) {
        console.error(`error: unknown subsystem '${name}'`);
        return 2;
      }
      disabled = name as Subsystem;
    } else if (arg === "--ablation-table") {
      table = true;
    } else {
      positional.push(arg);
    }
  }
  const workspace = positional[0];
  if (!workspace || positional.length !== 1) {
    console.error("usage: main.ts <workspace-dir> [--disable=<subsystem> | --ablation-table]");
    return 2;
  }
  if (!existsSync(workspace) || !statSync(workspace).isDirectory()) {
    console.error(`error: workspace not found: ${workspace}`);
    return 2;
  }

  if (table) {
    process.stdout.write(ablationTable(workspace) + "\n");
  } else {
    process.stdout.write(JSON.stringify(runLoop(workspace, disabled), null, 2) + "\n");
  }
  return 0;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
